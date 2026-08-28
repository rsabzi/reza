"""Small general-purpose tools available in every installation."""

from typing import Any

from .registry import ToolContext, register_tool


@register_tool("echo", "Return the supplied value.", requires_approval=False)
def echo(_context: ToolContext, value: Any) -> dict[str, Any]:
    return {"value": value}
