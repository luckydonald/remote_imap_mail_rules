"""The pydantic model of a rule file: rules, their locations, the condition expression tree and the actions."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .fields import (
    AddressField,
    AddressPart,
    BoolField,
    CompareOperator,
    DateField,
    NumberField,
    PresenceOperator,
    Quantifier,
    TextField,
    TextOperator,
)
from .values import TimeValue


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
# end class


class TextCondition(Strict):
    """Compares a text field. `case_sensitive` is available for every operator."""

    type: Literal["text"] = "text"
    field: TextField
    operator: TextOperator
    value: str | list[str]
    case_sensitive: bool = False
    quantifier: Quantifier = Quantifier.any

    @model_validator(mode="after")
    def check_value(self) -> "TextCondition":
        if self.operator == TextOperator.in_ and not isinstance(self.value, list):
            raise ValueError("operator `in` needs a list of values")
        # end if
        if self.operator != TextOperator.in_ and not isinstance(self.value, str):
            raise ValueError(f"operator `{self.operator}` needs a single string value")
        # end if
        return self
    # end def
# end class


class HeaderCondition(Strict):
    """Compares any header by name, for fields without a dedicated entry. Multiple headers of that name are quantified."""

    type: Literal["header"] = "header"
    name: str = Field(min_length=1)
    operator: TextOperator
    value: str | list[str]
    case_sensitive: bool = False
    quantifier: Quantifier = Quantifier.any

    @model_validator(mode="after")
    def check_value(self) -> "HeaderCondition":
        if self.operator == TextOperator.in_ and not isinstance(self.value, list):
            raise ValueError("operator `in` needs a list of values")
        # end if
        if self.operator != TextOperator.in_ and not isinstance(self.value, str):
            raise ValueError(f"operator `{self.operator}` needs a single string value")
        # end if
        return self
    # end def
# end class


class AddressCondition(Strict):
    """Compares an address field, at the granularity given by `part`."""

    type: Literal["address"] = "address"
    field: AddressField
    part: AddressPart = AddressPart.address
    operator: TextOperator
    value: str | list[str]
    case_sensitive: bool = False
    quantifier: Quantifier = Quantifier.any

    @model_validator(mode="after")
    def check_value(self) -> "AddressCondition":
        if self.operator == TextOperator.in_ and not isinstance(self.value, list):
            raise ValueError("operator `in` needs a list of values")
        # end if
        if self.operator != TextOperator.in_ and not isinstance(self.value, str):
            raise ValueError(f"operator `{self.operator}` needs a single string value")
        # end if
        return self
    # end def
# end class


class NumberCondition(Strict):
    type: Literal["number"] = "number"
    field: NumberField
    operator: CompareOperator
    value: float | tuple[float, float]
    quantifier: Quantifier = Quantifier.any

    @model_validator(mode="after")
    def check_value(self) -> "NumberCondition":
        if self.operator == CompareOperator.between and not isinstance(self.value, tuple):
            raise ValueError("operator `between` needs a [low, high] pair")
        # end if
        if self.operator != CompareOperator.between and isinstance(self.value, tuple):
            raise ValueError(f"operator `{self.operator}` needs a single number")
        # end if
        return self
    # end def
# end class


class DateCondition(Strict):
    """Compares a date. A relative value `7d` is the moment 7 days before now."""

    type: Literal["date"] = "date"
    field: DateField
    operator: CompareOperator
    value: TimeValue | tuple[TimeValue, TimeValue]

    @model_validator(mode="after")
    def check_value(self) -> "DateCondition":
        if self.operator == CompareOperator.between and not isinstance(self.value, tuple):
            raise ValueError("operator `between` needs a [low, high] pair")
        # end if
        if self.operator != CompareOperator.between and isinstance(self.value, tuple):
            raise ValueError(f"operator `{self.operator}` needs a single date")
        # end if
        return self
    # end def
# end class


class BoolCondition(Strict):
    type: Literal["bool"] = "bool"
    field: BoolField
    value: bool = True
    quantifier: Quantifier = Quantifier.any
# end class


class PresenceCondition(Strict):
    """Tests whether a field or header is there (`exists`) or there but without content (`empty`)."""

    type: Literal["presence"] = "presence"
    field: TextField | AddressField | NumberField | DateField | BoolField | None = None
    header: str | None = Field(default=None, min_length=1)
    operator: PresenceOperator = PresenceOperator.exists
    value: bool = True

    @model_validator(mode="after")
    def check_target(self) -> "PresenceCondition":
        if (self.field is None) == (self.header is None):
            raise ValueError("exactly one of `field` and `header` is needed")
        # end if
        return self
    # end def
# end class


class AllExpression(Strict):
    """AND: true if every nested expression is true."""

    type: Literal["all"] = "all"
    conditions: list["Expression"] = Field(min_length=1)
# end class


class AnyExpression(Strict):
    """OR: true if at least one nested expression is true."""

    type: Literal["any"] = "any"
    conditions: list["Expression"] = Field(min_length=1)
# end class


class NotExpression(Strict):
    type: Literal["not"] = "not"
    condition: "Expression"
# end class


Expression = Annotated[
    AllExpression
    | AnyExpression
    | NotExpression
    | TextCondition
    | HeaderCondition
    | AddressCondition
    | NumberCondition
    | DateCondition
    | BoolCondition
    | PresenceCondition,
    Field(discriminator="type"),
]

AllExpression.model_rebuild()
AnyExpression.model_rebuild()
NotExpression.model_rebuild()


class Location(Strict):
    """Where a rule applies. The account is referenced by its immutable id, never by its changeable name."""

    account_id: UUID
    folder: str = "INBOX"
    recursive: bool = False
# end class


class MoveAction(Strict):
    type: Literal["move"] = "move"
    folder: str
    account_id: UUID | None = Field(default=None, description="Target account; the mail's own account if unset.")
# end class


class MarkReadAction(Strict):
    type: Literal["mark_read"] = "mark_read"
# end class


class MarkUnreadAction(Strict):
    type: Literal["mark_unread"] = "mark_unread"
# end class


class FlagAction(Strict):
    type: Literal["flag"] = "flag"
    value: bool = True
# end class


class KeywordAction(Strict):
    type: Literal["keyword"] = "keyword"
    keyword: str = Field(min_length=1)
    value: bool = True
# end class


Action = Annotated[
    MoveAction | MarkReadAction | MarkUnreadAction | FlagAction | KeywordAction,
    Field(discriminator="type"),
]


class Rule(Strict):
    name: str = Field(min_length=1)
    enabled: bool = True
    locations: list[Location] = Field(min_length=1)
    when: Expression
    actions: list[Action] = Field(default_factory=list, description="Parsed only; nothing executes them yet.")
# end class


class RuleFile(Strict):
    schema_: str | None = Field(default=None, alias="$schema")
    rules: list[Rule] = Field(default_factory=list)
# end class
