# Egg

Lightweight async dependency injection framework for Python.

## Installation

Requires Python >= 3.12

```bash
uv sync
# or
pip install -e .
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

## How It Works

1. **Decoration**: The `@hatch_eggs` decorator wraps your async function
2. **Inspection**: At call time, it inspects type hints (`Annotated[T, Egg(...)]`) and default values (`= Egg(...)`) to find dependencies
3. **Resolution**: For each `Egg`, the dependency function is called. If that function also has `Egg` parameters, they're resolved first (recursive)
4. **Caching**: Results are cached by default—calling the same dependency twice returns the cached value
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
