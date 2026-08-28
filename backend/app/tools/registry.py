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
    schema: dict[str, Any] | None = None

    def declaration(self) -> dict[str, Any]:
        """Interactions API function declaration; schema from registration or signature."""

        parameters = self.schema or schema_from_signature(self.function)
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": parameters,
        }


@dataclass(slots=True)
class ToolContext:
    """Execution context passed to tools without coupling the registry to FastAPI."""

    db: Any
    task: Any
    step: Any
    call_id: str | None = None
    action_run: Any = None


_registry: dict[str, RegisteredTool] = {}


def register_tool(
    name: str,
    description: str,
    *,
    requires_approval: bool = False,
    schema: dict[str, Any] | None = None,
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
            schema=schema,
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


def _json_type_for(annotation: Any) -> str:

    if annotation in (int,):
        return "integer"
    if annotation in (float,):
        return "number"
    if annotation in (bool,):
        return "boolean"
    if annotation in (list,):
        return "array"
    if annotation in (dict,):
        return "object"
    return "string"


def schema_from_signature(function: ToolFunction) -> dict[str, Any]:
    """Build a JSON schema from a tool's signature when no schema was registered."""

    signature = inspect.signature(function)
    properties: dict[str, Any] = {}
    required: list[str] = []
    for name, parameter in signature.parameters.items():
        if name in {"context", "self", "args", "kwargs"}:
            continue
        if parameter.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        annotation = parameter.annotation
        origin = getattr(annotation, "__origin__", None)
        if origin is not None and str(origin) == "typing.Optional":
            annotation = annotation.__args__[0]
        schema_item: dict[str, Any] = {"type": _json_type_for(annotation)}
        description = getattr(annotation, "__doc__", None)
        if description:
            schema_item["description"] = description
        properties[name] = schema_item
        if parameter.default is inspect.Parameter.empty:
            required.append(name)
    return {"type": "object", "properties": properties, "required": required}


async def call_tool(tool: RegisteredTool, context: ToolContext, arguments: dict[str, Any]) -> Any:
    """Validate and call sync or async tool functions through one safe interface."""

    validate_tool_arguments(tool, arguments)
    value = tool.function(context, **arguments)
    if inspect.isawaitable(value):
        return await value
    return value
