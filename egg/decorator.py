from typing import Callable, TypeVar
import functools

from egg.exceptions import EggHatchingError
from egg.hatcher import Hatcher
from egg.util import get_type_hints_and_signature, build_available_values_from_args_kwargs, \
    extract_eggs, is_egg

T = TypeVar("T")


def hatch_eggs(func: Callable[..., T]) -> Callable[..., T]:
    """
         Decorator that resolves Egg dependencies.

         Example:
             @hatch_eggs
             async def initialize(
                 tenant_name: str,
                 client: Httpx.AsyncClient = Egg(get_client),
             ):
                 # client is resolved automatically
                 ...


        Args:
            func: Function with Egg Dependency in param defaults or Annotated hints.
        Returns:
            Async wrapper that hatches eggs before calling func.
         """

    hints, sig = get_type_hints_and_signature(func)
    param_names = list(sig.parameters.keys())

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        available = build_available_values_from_args_kwargs(args, kwargs, param_names)
        hatcher = Hatcher(available)

        for name in sig.parameters:
            if name in kwargs:
                continue

            eggs = extract_eggs(hints.get(name))
            if eggs is None and is_egg(sig.parameters[name].default):
                eggs = sig.parameters[name].default
            if eggs is not None:
                try:
                    kwargs[name] = await hatcher.hatch(eggs)
                except Exception as e:
                    raise EggHatchingError(f"Failed to hatch '{name}': {e}") from e

        return await func(*args, **kwargs)

    return wrapper