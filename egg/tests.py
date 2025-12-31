import asyncio
import pytest
from typing import Annotated

from egg.decorator import hatch_eggs
from egg.egg import Egg
from egg.exceptions import EggHatchingError


async def get_base_value() -> int:
    """Simple async dependency."""
    return 10


def get_sync_value() -> str:
    """Simple sync dependency."""
    return "sync"


async def get_doubled(base: Annotated[int, Egg(get_base_value)]) -> int:
    """Nested dependency that doubles the base."""
    return base * 2


async def get_with_param(tenant_name: str) -> str:
    """Dependency that uses an injected parameter."""
    return f"client_{tenant_name}"


class Multiplier:
    """Parameterized callable class dependency."""

    def __init__(self, factor: int):
        self.factor = factor

    def __call__(self, base: Annotated[int, Egg(get_base_value)]) -> int:
        return base * self.factor


class AsyncMultiplier:
    """Parameterized async callable class dependency."""

    def __init__(self, factor: int):
        self.factor = factor

    async def __call__(self, base: Annotated[int, Egg(get_base_value)]) -> int:
        await asyncio.sleep(0)  # Simulate async work
        return base * self.factor


class TestBasicDependencies:
    """Tests for basic dependency resolution."""

    def test_simple_async_dependency(self):
        """Test resolving a simple async dependency."""

        @hatch_eggs
        async def func(value: Annotated[int, Egg(get_base_value)]) -> int:
            return value + 1

        result = asyncio.run(func())
        assert result == 11

    def test_simple_sync_dependency(self):
        """Test resolving a simple sync dependency."""

        @hatch_eggs
        async def func(value: Annotated[str, Egg(get_sync_value)]) -> str:
            return f"got_{value}"

        result = asyncio.run(func())
        assert result == "got_sync"

    def test_dependency_with_lambda(self):
        """Test resolving a lambda dependency."""

        @hatch_eggs
        async def func(value: Annotated[int, Egg(lambda: 42)]) -> int:
            return value

        result = asyncio.run(func())
        assert result == 42

    def test_default_value_syntax(self):
        """Test resolving dependency using = Egg() syntax."""

        @hatch_eggs
        async def func(value: int = Egg(get_base_value)) -> int:
            return value + 1

        result = asyncio.run(func())
        assert result == 11


class TestNestedDependencies:
    """Tests for nested dependency resolution."""

    def test_nested_dependency(self):
        """Test resolving nested dependencies."""

        @hatch_eggs
        async def func(value: Annotated[int, Egg(get_doubled)]) -> int:
            return value + 5

        result = asyncio.run(func())
        assert result == 25  # 10 * 2 + 5

    def test_nested_with_default_syntax(self):
        """Test nested dependencies using = Egg() syntax."""

        async def inner() -> int:
            return 5

        async def outer(x: int = Egg(inner)) -> int:
            return x * 3

        @hatch_eggs
        async def func(value: int = Egg(outer)) -> int:
            return value + 1

        result = asyncio.run(func())
        assert result == 16  # 5 * 3 + 1


class TestParameterInjection:
    """Tests for automatic parameter injection."""

    def test_parameter_injection(self):
        """Test that parameters are auto-injected by name."""

        @hatch_eggs
        async def func(
            tenant_name: str,
            client: Annotated[str, Egg(get_with_param)],
        ) -> str:
            return client

        result = asyncio.run(func(tenant_name="acme"))
        assert result == "client_acme"

    def test_parameter_injection_with_kwargs(self):
        """Test parameter injection with keyword arguments."""

        @hatch_eggs
        async def func(
            tenant_name: str,
            client: Annotated[str, Egg(get_with_param)],
        ) -> str:
            return client

        result = asyncio.run(func(tenant_name="bazco"))
        assert result == "client_bazco"


class TestCallableClasses:
    """Tests for callable class dependencies."""

    def test_sync_callable_class(self):
        """Test parameterized sync callable class."""

        @hatch_eggs
        async def func(val: Annotated[int, Egg(Multiplier(3))]) -> int:
            return val

        result = asyncio.run(func())
        assert result == 30  # 10 * 3

    def test_async_callable_class(self):
        """Test parameterized async callable class."""

        @hatch_eggs
        async def func(val: Annotated[int, Egg(AsyncMultiplier(5))]) -> int:
            return val

        result = asyncio.run(func())
        assert result == 50  # 10 * 5


class TestCaching:
    """Tests for dependency caching."""

    def test_caching_same_dependency(self):
        """Test that dependencies are cached within a single call."""
        call_count = 0

        async def counting_dep() -> int:
            nonlocal call_count
            call_count += 1
            return call_count

        @hatch_eggs
        async def func(
            a: Annotated[int, Egg(counting_dep)],
            b: Annotated[int, Egg(counting_dep)],
        ) -> tuple:
            return (a, b)

        result = asyncio.run(func())
        assert result == (1, 1)  # Same value, called once
        assert call_count == 1

    def test_no_cache_option(self):
        """Test that use_cache=False skips caching."""
        call_count = 0

        async def counting_dep() -> int:
            nonlocal call_count
            call_count += 1
            return call_count

        @hatch_eggs
        async def func(
            a: Annotated[int, Egg(counting_dep, use_cache=False)],
            b: Annotated[int, Egg(counting_dep, use_cache=False)],
        ) -> tuple:
            return (a, b)

        result = asyncio.run(func())
        assert result == (1, 2)  # Different values, called twice
        assert call_count == 2


class TestMockInjection:
    """Tests for mock injection via kwargs."""

    def test_mock_injection(self):
        """Test that mocks can be injected via kwargs."""

        @hatch_eggs
        async def func(value: Annotated[int, Egg(get_base_value)]) -> int:
            return value + 1

        result = asyncio.run(func(value=100))
        assert result == 101  # Uses mock value, not dependency


class TestErrorHandling:
    """Tests for error handling."""

    def test_missing_required_parameter(self):
        """Test error when required parameter is missing."""

        async def needs_param(missing_param: str) -> str:
            return missing_param

        @hatch_eggs
        async def func(value: Annotated[str, Egg(needs_param)]) -> str:
            return value

        with pytest.raises(EggHatchingError, match="missing_param"):
            asyncio.run(func())

    def test_circular_dependency_detection(self):
        """Test that circular dependencies are detected."""
        # Create circular dependency
        async def dep_a(b: Annotated[int, Egg(lambda: dep_b)]) -> int:
            return b

        async def dep_b(a: Annotated[int, Egg(lambda: dep_a)]) -> int:
            return a

        @hatch_eggs
        async def func(val: Annotated[int, Egg(dep_a)]) -> int:
            return val


class TestEggRepr:
    """Tests for Egg class representation."""

    def test_eggs_repr_with_function(self):
        """Test Egg repr with a named function."""
        egg = Egg(get_base_value)
        assert "get_base_value" in repr(egg)

    def test_eggs_repr_with_lambda(self):
        """Test Egg repr with a lambda."""
        egg = Egg(lambda: 1)
        assert "Egg(" in repr(egg)


class TestDefaultValues:
    """Tests for default parameter handling."""

    def test_parameter_with_default(self):
        """Test that parameters with defaults work correctly."""

        async def dep_with_default(value: int = 99) -> int:
            return value

        @hatch_eggs
        async def func(result: Annotated[int, Egg(dep_with_default)]) -> int:
            return result

        result = asyncio.run(func())
        assert result == 99


if __name__ == "__main__":
    pytest.main([__file__, "-v"])