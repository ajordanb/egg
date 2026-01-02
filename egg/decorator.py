from typing import Callable, TypeVar
import asyncio
import functools

from egg.exceptions import EggHatchingError
from egg.hatcher import Hatcher
from egg.util import get_type_hints_and_signature, build_available_values_from_args_kwargs, \
    extract_eggs, is_egg

T = TypeVar("T")


def hatch_eggs(func: Callable[..., T]) -> Callable[..., T]:
    """
    Decorator that resolves Egg dependencies.

    Works with both async and sync functions.

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
        Wrapper that hatches eggs before calling func.
    """

    hints, sig = get_type_hints_and_signature(func)
    param_names = list(sig.parameters.keys())

    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        available = build_available_values_from_args_kwargs(args, kwargs, param_names)
        hatcher = Hatcher(available)

        for name in sig.parameters:
            if name in kwargs or name in available:
                continue

            eggs = extract_eggs(hints.get(name))
            if eggs is None and is_egg(sig.parameters[name].default):
                eggs = sig.parameters[name].default
            if eggs is not None:
                try:
                    kwargs[name] = await hatcher.hatch(eggs)
                except Exception as e:
                    raise EggHatchingError(f"Failed to hatch '{name}': {e}") from e

        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        return func(*args, **kwargs)

    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        return asyncio.run(async_wrapper(*args, **kwargs))

    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper