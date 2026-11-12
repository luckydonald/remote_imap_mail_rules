"""An `MCPServer` whose tools each need scopes of the calling token: hidden from `tools/list` and refused on `tools/call` without them."""

from collections.abc import Callable
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import CallToolResult, InputRequiredResult, Tool as MCPTool

from .scopes import Scope
from .tokens import current_caller


class ScopedServer(MCPServer):
    required: dict[str, frozenset[Scope]]

    def scoped_tool[F: Callable[..., Any]](self, *scopes: Scope, description: str | None = None) -> Callable[[F], F]:
        """Registers the function as a tool that needs all of `scopes`."""
        if not hasattr(self, "required"):
            self.required = {}
        # end if

        def decorator(function: F) -> F:
            self.required[function.__name__] = frozenset(scopes)
            self.tool(description=description)(function)
            return function
        # end def

        return decorator
    # end def

    def allowed(self, name: str) -> bool:
        caller = current_caller.get()
        needed = getattr(self, "required", {}).get(name)
        return caller is not None and needed is not None and needed <= caller.scopes
    # end def

    async def list_tools(self) -> list[MCPTool]:
        return [tool for tool in await super().list_tools() if self.allowed(tool.name)]
    # end def

    async def call_tool(self, name: str, arguments: dict[str, Any], context: Any = None) -> CallToolResult | InputRequiredResult:
        if not self.allowed(name):
            needed = ", ".join(sorted(scope.value for scope in getattr(self, "required", {}).get(name, ()))) or "an unknown tool"
            raise ToolError(f"This token may not use {name}: it needs the scope(s) {needed}.")
        # end if
        return await super().call_tool(name, arguments, context)
    # end def
# end class
