from __future__ import annotations

from typing import  Callable, TypeVar


T = TypeVar("T")


class Egg:
    """
    An Egg is a wrapper for a Dependency.

    The callable's params get matched by name from the available context.

    Nesting works. Cached by default.

    It takes two parameters:

    Args:
        dependency: a callable that returns a value.
        use_cache: whether to cache the value returned by the callable.
    """

    __slots__ = ("dependency", "use_cache")

    def __init__(self,
                 dependency: Callable[..., T],
                 *,
                 use_cache: bool = True) -> None:
        self.dependency = dependency
        self.use_cache = use_cache

    def __repr__(self) -> str:
        name = getattr(self.dependency, "__name__", repr(self.dependency))
        return f"Egg({name})"






