"""A route that always fails, to check that errors reach Sentry or Bugsink. Behind the login like the rest of `/api`."""

from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def sample_error() -> None:
    raise RuntimeError("backend sample error for Sentry/Bugsink verification")
# end def
