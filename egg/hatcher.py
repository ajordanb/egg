from __future__ import annotations

import inspect
from typing import Any, Callable, TypeVar


from egg.egg import Egg
from egg.exceptions import EggHatchingError
from egg.util import callable_name, is_egg, invoke, get_type_hints_and_signature, extract_eggs

T = TypeVar("T")



class Hatcher:
    """
    Egg Hatcher. Hatches Egg() annotations into their values.

    Handles caching, circular dependency detection, and recursive resolution.

    It takes one parameter:

    Args:
        available: dictionary of available values to resolve eggs from.

    """

    __slots__ = ("available", "cache", "resolving")

    def __init__(self, available: dict[str, Any]):
        self.available = available
        self.cache: dict[Callable, Any] = {}
        self.resolving: set[Callable] = set()

    def is_circular_dependency(self, dep_func: Callable) -> bool:
        return dep_func in self.resolving

    def is_cached(self, egg: Egg) -> bool:
        return egg.use_cache and egg.dependency in self.cache

    def maybe_add_to_cache(self, egg: Egg, value: Any) -> None:
        if egg.use_cache:
            self.cache[egg.dependency] = value

    async def hatch(self, egg: Egg) -> Any:
        """Hatch an Egg to its value."""
        dep_func = egg.dependency

        if self.is_circular_dependency(dep_func):
            raise EggHatchingError(f"Circular dependency: {callable_name(dep_func)}")

        if self.is_cached(egg):
            return self.cache[dep_func]

        self.resolving.add(dep_func)
        try:
            kwargs = await self.build_callable_kwargs(dep_func)
            result = await invoke(dep_func, kwargs)
            self.maybe_add_to_cache(egg, result)
            return result
        finally:
            self.resolving.discard(dep_func)

    async def build_callable_kwargs(self, func: Callable) -> dict[str, Any]:
        """Build kwargs for a callable, resolving any nested Egg."""
        hints, sig = get_type_hints_and_signature(func)
        kwargs: dict[str, Any] = {}

        for name, param in sig.parameters.items():
            if name in ("self", "cls"):
                continue

            eggs = extract_eggs(hints.get(name))
            if eggs is None and is_egg(param.default):
                eggs = param.default

            if eggs is not None:
                value = await self.hatch(eggs)
                kwargs[name] = value
                self.available[name] = value

            elif name in self.available:
                kwargs[name] = self.available[name]

            elif param.default is inspect.Parameter.empty:
                raise EggHatchingError(
                    f"Missing '{name}' for {callable_name(func)}. "
                    f"Available: {list(self.available.keys())}"
                )
            # else: has default, skip

        return kwargs