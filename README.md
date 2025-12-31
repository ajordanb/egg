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
