"""Framework-agnostic, decorator-based tool registry."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, TypeVar

ToolFunction = Callable[..., Any]
F = TypeVar("F", bound=ToolFunction)


@dataclass(frozen=True, slots=True)
class RegisteredTool:
    name: str
    description: str
    requires_approval: bool
    function: ToolFunction


@dataclass(slots=True)
class ToolContext:
    """Execution context passed to tools without coupling the registry to FastAPI."""

    db: Any
    task: Any
    step: Any


_registry: dict[str, RegisteredTool] = {}


def register_tool(
    name: str,
    description: str,
    *,
    requires_approval: bool = False,
) -> Callable[[F], F]:
    """Register a function as an agent tool.

    Re-registering the same name intentionally replaces the prior definition, which
    keeps application reloads and isolated tests deterministic.
    """

    normalized = name.strip()
    if not normalized:
        raise ValueError("Tool name must not be blank")

    def decorator(function: F) -> F:
        _registry[normalized] = RegisteredTool(
            name=normalized,
            description=description.strip(),
            requires_approval=requires_approval,
            function=function,
        )
        return function

    return decorator


def get_tool(name: str) -> RegisteredTool | None:
    return _registry.get(name)


def list_registered_tools() -> tuple[RegisteredTool, ...]:
    return tuple(sorted(_registry.values(), key=lambda item: item.name))


def registry_snapshot() -> Mapping[str, RegisteredTool]:
    return dict(_registry)


class ToolArgumentError(ValueError):
    """Arguments cannot be bound to a registered tool's function signature."""


def validate_tool_arguments(tool: RegisteredTool, arguments: dict[str, Any]) -> None:
    try:
        inspect.signature(tool.function).bind(None, **arguments)
    except TypeError as exc:
        raise ToolArgumentError(f"Invalid arguments for tool '{tool.name}': {exc}") from exc


async def call_tool(tool: RegisteredTool, context: ToolContext, arguments: dict[str, Any]) -> Any:
    """Validate and call sync or async tool functions through one safe interface."""

    validate_tool_arguments(tool, arguments)
    value = tool.function(context, **arguments)
    if inspect.isawaitable(value):
        return await value
    return value
