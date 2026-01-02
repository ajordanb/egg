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


def is_generator_function(func: Callable) -> bool:
    """Check if callable is a sync generator function."""
    if inspect.isgeneratorfunction(func):
        return True
    if hasattr(func, "__call__") and inspect.isgeneratorfunction(func.__call__):
        return True
    return False


def is_async_generator_function(func: Callable) -> bool:
    """Check if callable is an async generator function."""
    if inspect.isasyncgenfunction(func):
        return True
    if hasattr(func, "__call__") and inspect.isasyncgenfunction(func.__call__):
        return True
    return False


async def invoke_and_get_cleanup(func: Callable, kwargs: dict[str, Any]) -> tuple[Any, Any]:
    """
    Invoke a callable and return (value, cleanup_generator).

    For regular callables, cleanup_generator is None.
    For generator-based dependencies, cleanup_generator is the generator
    that needs to be closed after the decorated function completes.
    """
    # Async generator: get first yielded value, return generator for cleanup
    if is_async_generator_function(func):
        generator = func(**kwargs)
        value = await generator.__anext__()
        return value, generator

    # Sync generator: get first yielded value, return generator for cleanup
    if is_generator_function(func):
        generator = func(**kwargs)
        value = next(generator)
        return value, generator

    # Regular async callable
    if asyncio.iscoroutinefunction(func):
        return await func(**kwargs), None
    if hasattr(func, "__call__") and asyncio.iscoroutinefunction(func.__call__):
        return await func(**kwargs), None

    # Regular sync callable
    return func(**kwargs), None


def run_sync_cleanup(generator) -> None:
    """Run sync generator cleanup, handling StopIteration internally."""
    try:
        next(generator)
    except StopIteration:
        pass


async def close_generator(generator: Any, timeout: float = 30.0) -> None:
    """Close a generator with timeout protection."""
    if generator is None:
        return

    try:
        if inspect.isasyncgen(generator):
            try:
                await asyncio.wait_for(generator.__anext__(), timeout=timeout)
            except StopAsyncIteration:
                pass
        else:
            await asyncio.wait_for(
                asyncio.to_thread(run_sync_cleanup, generator),
                timeout=timeout
            )
    except asyncio.TimeoutError:
        logger.warning(f"Cleanup timed out after {timeout}s")
    except Exception as e:
        logger.warning(f"Error during cleanup: {e}")


def build_available_values_from_args_kwargs(args: tuple[Any, ...], kwargs: dict[str, Any], param_names: list) -> dict[str, Any]:
    """Build available values from args and kwargs."""
    available = {param_names[i]: arg for i, arg in enumerate(args) if i < len(param_names)}
    available.update(kwargs)
    return available