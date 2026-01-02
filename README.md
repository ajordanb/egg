# Egg

Lightweight async dependency injection framework for Python. Inspired by [FastAPI's Depends](https://fastapi.tiangolo.com/learn/), but framework-agnostic.

## Installation

Requires Python >= 3.10

```bash
pip install injegg
# or
uv add injegg
```

## Usage

Wrap dependencies in `Egg()` and use the `@hatch_eggs` decorator to auto-resolve them.

### Using Annotated type hints

```python
import asyncio
from typing import Annotated
from egg import Egg, hatch_eggs

async def get_client():
    return "http_client"

@hatch_eggs
async def main(client: Annotated[str, Egg(get_client)]):
    print(client)  # "http_client"

asyncio.run(main())
```

### Using default parameter syntax

```python
@hatch_eggs
async def main(client: str = Egg(get_client)):
    print(client)  # "http_client"
```

### Injecting into class methods

```python
class UserService:
    @hatch_eggs
    async def get_user(self, db: Annotated[Database, Egg(get_database)]):
        return await db.query("SELECT * FROM users")

service = UserService()
asyncio.run(service.get_user())
```

### Nested dependencies

Dependencies can depend on other dependencies. They resolve in the correct order.

```python
async def get_config():
    return {"db_url": "postgres://localhost/mydb"}

async def get_database(config: Annotated[dict, Egg(get_config)]):
    return Database(config["db_url"])

async def get_user_repo(db: Annotated[Database, Egg(get_database)]):
    return UserRepository(db)

@hatch_eggs
async def main(repo: Annotated[UserRepository, Egg(get_user_repo)]):
    users = await repo.find_all()
    print(users)

asyncio.run(main())
```

### Multiple dependencies

```python
@hatch_eggs
async def handler(
    db: Annotated[Database, Egg(get_database)],
    cache: Annotated[Cache, Egg(get_cache)],
    logger: Annotated[Logger, Egg(get_logger)],
):
    logger.info("Fetching data")
    data = await cache.get("key") or await db.query("...")
    return data
```

## Dependencies

A dependency is any callable. Parameters are resolved by name from context.

### Supported types

```python
# Async function
async def get_client():
    return AsyncClient()

# Sync function
def get_config():
    return load_config()

# Class instance with __call__
class TokenProvider:
    def __init__(self, secret: str):
        self.secret = secret

    async def __call__(self, user_id: str):
        return generate_token(user_id, self.secret)

# Usage: pass config at instantiation, user_id comes from context
token_provider = TokenProvider(secret="abc123")

@hatch_eggs
async def handler(
    user_id: str,
    token: Annotated[str, Egg(token_provider)],  # calls token_provider(user_id=...)
):
    ...
```

### Generators for cleanup

Use generators to run cleanup code after the decorated function completes:

```python
async def get_database():
    db = await Database.connect()
    try:
        yield db  # Value injected here
    finally:
        await db.close()  # Runs after decorated function completes

@hatch_eggs
async def handler(db: Annotated[Database, Egg(get_database)]):
    await db.query("SELECT ...")
# ← db.close() called here automatically
```

Cleanup runs even if the decorated function raises an exception. Multiple generators clean up in reverse order (LIFO).

## How It Works

1. **Decoration**: The `@hatch_eggs` decorator wraps your async function
2. **Inspection**: At call time, it inspects type hints (`Annotated[T, Egg(...)]`) and default values (`= Egg(...)`) to find dependencies
3. **Resolution**: For each `Egg`, the dependency function is called. If that function also has `Egg` parameters, they're resolved first (recursive)
4. **Caching**: Results are cached within a single call—the same dependency used twice resolves once. Cache resets between calls (no global singletons)
5. **Injection**: Resolved values replace the `Egg` markers and your function is called with the real dependencies

```
@hatch_eggs
async def main(db: Annotated[Database, Egg(get_db)]):
                                        ↓
                              calls get_db()
                                        ↓
                              caches result
                                        ↓
                              main(db=<Database>)
```

### Auto-injection from context

Once a dependency is resolved, it's added to the available context by parameter name. Nested dependencies can then receive it automatically without an `Egg()` wrapper—just match the parameter name:

```python
async def get_database():
    return Database("postgres://localhost/mydb")

# No Egg() needed—"db" is auto-injected from context
async def get_user_repo(db):
    return UserRepository(db)

@hatch_eggs
async def main(
    db: Annotated[Database, Egg(get_database)],        # resolved first, added to context as "db"
    repo: Annotated[UserRepository, Egg(get_user_repo)]  # get_user_repo receives "db" automatically
):
    users = await repo.find_all()
```

This enables implicit wiring—dependencies don't need to know how their own dependencies are created.

### Forwarding caller arguments to dependencies

Arguments passed by the caller are also available for injection into dependencies:

```python
async def get_api_client(config_id: str):
    config = await load_config(config_id)
    return AsyncClient(base_url=config["api_url"])

@hatch_eggs
async def create(config_id: str, api_client: AsyncClient = Egg(get_api_client)):
    return await api_client.post("/resources")

# config_id is passed to create(), then auto-injected into get_api_client()
await create(config_id="production")
```

The flow:
1. `create("production")` is called with `config_id="production"`
2. `config_id` is added to the available context
3. `get_api_client` needs `config_id`—it's auto-injected from context
4. `create` receives the fully configured `api_client`

Circular dependencies are detected and raise `EggHatchingError`.

### Parameter order matters

Dependencies resolve in parameter order. If a dependency relies on auto-injection from context, the injected value must be resolved first:

```python
# ✅ Works: db resolves first, then repo receives it via auto-injection
@hatch_eggs
async def handler(
    db: Annotated[Database, Egg(get_database)],
    repo: Annotated[UserRepo, Egg(get_user_repo)],  # get_user_repo(db) works
):
    ...

# ❌ Fails: repo needs db, but db isn't in context yet
@hatch_eggs
async def handler(
    repo: Annotated[UserRepo, Egg(get_user_repo)],  # get_user_repo(db) fails
    db: Annotated[Database, Egg(get_database)],
):
    ...
```

To avoid this, use explicit `Egg()` wrappers in your dependency instead of relying on auto-injection.

## Use Cases

### Testing with mocks

Easily swap dependencies in tests by passing them directly—no patching needed:

```python
@hatch_eggs
async def process_payment(gateway: PaymentGateway = Egg(get_payment_gateway)):
    return await gateway.charge(100)

# In tests: bypass the Egg by passing the dependency directly
async def test_process_payment():
    mock_gateway = MockPaymentGateway()
    result = await process_payment(gateway=mock_gateway)
    assert result.success
```

### Background jobs and scripts

Clean dependency setup for CLI tools, background workers, or one-off scripts:

```python
@hatch_eggs
async def run_sync_job(
    tenant_id: str,
    db: Annotated[Database, Egg(get_database)],
    api: Annotated[ExternalAPI, Egg(get_external_api)],
):
    records = await api.fetch_updates(tenant_id)
    await db.bulk_upsert(records)

# Simple invocation with just the business parameter
asyncio.run(run_sync_job(tenant_id="acme-corp"))
```

## Contributing

1. Fork the repository
2. Clone your fork and install dependencies:
   ```bash
   git clone https://github.com/your-username/egg.git
   cd egg
   uv sync
   ```
3. Make your changes
4. Run tests:
   ```bash
   pytest egg/tests.py -v
   ```
5. Submit a pull request

## License

MIT
