"""Logging config for `uvicorn.run()` that keeps the application's own loggers working."""

from typing import Any


def get_log_config(level: str = "INFO") -> dict[str, Any]:
    """`disable_existing_loggers` is off, otherwise uvicorn silences every logger created before it starts."""
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {"plain": {"format": "%(asctime)s %(levelname)-8s %(name)s: %(message)s"}},
        "handlers": {"stdout": {"class": "logging.StreamHandler", "formatter": "plain", "stream": "ext://sys.stdout"}},
        "loggers": {
            "uvicorn": {"handlers": ["stdout"], "level": level, "propagate": False},
            "uvicorn.error": {"level": level},
            "uvicorn.access": {"handlers": ["stdout"], "level": level, "propagate": False},
        },
        "root": {"handlers": ["stdout"], "level": level},
    }
# end def
