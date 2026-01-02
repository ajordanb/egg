import asyncio
import inspect
import logging
from typing import Annotated, Any, Callable, get_args, get_origin, get_type_hints

from egg.egg import Egg

logger = logging.getLogger(__name__)


def callable_name(func: Callable) -> str:
    return getattr(func, "__name__", repr(func))

def is_egg(item: Any) -> bool:
    return isinstance(item, Egg)

def extract_eggs(hint: Any) -> Egg | None:
    """Extract Egg from an Annotated type hint, if present."""
    if hint is not None and get_origin(hint) is Annotated:
        for arg in get_args(hint)[1:]:
            if is_egg(arg):
                return arg
    return None

def get_type_hints_and_signature(func: Callable) -> tuple[dict, inspect.Signature]:
    """Get type hints and signature for a callable (function or class with __call__)."""
    target = func.__call__ if (hasattr(func, "__call__") and not inspect.isfunction(func)) else func

    try:
        hints = get_type_hints(target, include_extras=True)
    except TypeError:
        logger.warning(f"Failed to get type hints for {callable_name(func)}")
        hints = {}

    return hints, inspect.signature(target)




async def invoke(func: Callable, kwargs: dict[str, Any]) -> Any:
    """Invoke a callable (sync or async) with kwargs."""
    if asyncio.iscoroutinefunction(func):
        return await func(**kwargs)
    if hasattr(func, "__call__") and asyncio.iscoroutinefunction(func.__call__):
        return await func(**kwargs)
    return func(**kwargs)


def build_available_values_from_args_kwargs(args: tuple[Any, ...], kwargs: dict[str, Any], param_names: list) -> dict[str, Any]:
    """Build available values from args and kwargs."""
    available = {param_names[i]: arg for i, arg in enumerate(args) if i < len(param_names)}
    available.update(kwargs)
    return available