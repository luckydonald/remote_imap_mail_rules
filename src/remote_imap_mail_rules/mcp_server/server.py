"""The MCP server, mounted by `create_app` at `/mcp`."""

from fastapi import FastAPI
from mcp.server.transport_security import TransportSecuritySettings
from starlette.routing import Route
from starlette.types import ASGIApp, Receive, Scope, Send

from . import tools_accounts, tools_events, tools_rules
from .scoped import ScopedServer
from .tokens import TokenAuthMiddleware

INSTRUCTIONS = (
    "Tools to read and change the mail rules of remote_imap_mail_rules, its accounts and its action log. "
    "Start with get_rules_schema and list_rules; change rules with the small tools (add_condition, update_rule, ...) or save_rules_yaml, "
    "check with dry_run before relying on a rule. The first matching rule wins, so the order of the rules matters."
)


class AtRoot:
    """Hands the request to the MCP app as if it were its root path, so `/mcp` and `/mcp/` both work without a redirect."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
    # end def

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self.app({**scope, "path": "/", "raw_path": b"/"}, receive, send)
    # end def
# end class


def mount_mcp(app: FastAPI) -> ScopedServer:
    """Adds `/mcp` to the app and returns the server, whose session manager must run while the app does (`server.session_manager.run()`)."""
    app.state.mcp_tasks = set()
    server = ScopedServer(name="remote_imap_mail_rules", instructions=INSTRUCTIONS)
    tools_rules.register(server, app)
    tools_accounts.register(server, app)
    tools_events.register(server, app)
    # The bearer token is the protection, so the Host / Origin check against DNS rebinding (aimed at unauthenticated local servers) is off.
    inner = server.streamable_http_app(
        streamable_http_path="/", stateless_http=True, json_response=True,
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    wrapped = TokenAuthMiddleware(inner, lambda: (app.state.settings, app.state.session_factory))
    for path in ("/mcp", "/mcp/"):
        app.router.routes.append(Route(path, AtRoot(wrapped), methods=["GET", "POST", "DELETE"]))
    # end for
    return server
# end def
