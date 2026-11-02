"""Date and time values of rule conditions: either a fixed datetime or a duration relative to now."""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

DURATION_PATTERN = r"^(\d+)([smhdw])$"
DURATION_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}


class AbsoluteTime(BaseModel):
    """A fixed point in time. Naive datetimes are taken as UTC."""

    relative: Literal[False] = False
    value: datetime

    def resolve(self, now: datetime) -> datetime:
        if self.value.tzinfo is None:
            return self.value.replace(tzinfo=UTC)
        # end if
        return self.value
    # end def
# end class


class RelativeDuration(BaseModel):
    """A moment this long before now, e.g. `7d`: `date_received lt 7d` means received more than a week ago."""

    relative: Literal[True]
    value: str = Field(pattern=DURATION_PATTERN, description="A number and a unit: s, m, h, d or w.")

    @field_validator("value")
    @classmethod
    def normalize(cls, value: str) -> str:
        return value.strip().lower()
    # end def

    def resolve(self, now: datetime) -> datetime:
        amount, unit = int(self.value[:-1]), self.value[-1]
        return now - timedelta(seconds=amount * DURATION_SECONDS[unit])
    # end def
# end class


TimeValue = Annotated[AbsoluteTime | RelativeDuration, Field(discriminator="relative")]
