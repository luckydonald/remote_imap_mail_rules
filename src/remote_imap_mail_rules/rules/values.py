"""Date and time values of rule conditions."""

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal, Never

from pydantic import Field, field_validator

from .base import Concrete, Templatable, Var, substitute

DURATION_PATTERN = r"^(\d+)([smhdw])$"
DURATION_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
type Duration = Annotated[str, Field(pattern=DURATION_PATTERN, description="A number and a unit: s, m, h, d or w.")]


class AbsoluteTime[V = Var](Concrete):
    """A fixed point in time. Naive datetimes are taken as UTC."""

    relative: Literal[False] = False
    value: Templatable[datetime, V]

    def resolve(self: "AbsoluteTime[Never]", now: datetime) -> datetime:
        if self.value.tzinfo is None:
            return self.value.replace(tzinfo=UTC)
        # end if
        return self.value
    # end def
# end class


class RelativeDuration[V = Var](Concrete):
    """A moment this long before now, e.g. `7d`: `date_received lt 7d` means received more than a week ago."""

    relative: Literal[True]
    value: Templatable[Duration, V]

    @field_validator("value")
    @classmethod
    def normalize(cls, value: str | V) -> str | V:
        return value.strip().lower() if isinstance(value, str) else value
    # end def

    def resolve(self: "RelativeDuration[Never]", now: datetime) -> datetime:
        amount, unit = int(self.value[:-1]), self.value[-1]
        return now - timedelta(seconds=amount * DURATION_SECONDS[unit])
    # end def
# end class


class VariableTime[V = Var](Concrete):
    """A time whose kind is chosen by a template variable."""

    relative: V
    value: Templatable[datetime | str, V]

    def concrete(self, variables: Mapping[str, Any] | None = None) -> AbsoluteTime[Never] | RelativeDuration[Never]:
        scope = variables or {}
        relative = substitute(self.relative, scope)
        if not isinstance(relative, bool):
            raise ValueError("date variable `relative` needs a boolean")
        # end if
        model = RelativeDuration if relative else AbsoluteTime
        return model.model_validate({"relative": relative, "value": substitute(self.value, scope)})
    # end def
# end class


type TimeValue[V = Var] = AbsoluteTime[V] | RelativeDuration[V] | VariableTime[V]
