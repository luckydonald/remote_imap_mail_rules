"""What follows a saved rules text, whoever saved it (the editor's `PUT`, an MCP tool): the watcher picks the new rules up, git commits them."""

from fastapi import FastAPI


async def after_rules_saved(app: FastAPI) -> None:
    await app.state.watcher.restart()
    await app.state.git.auto()
# end def
