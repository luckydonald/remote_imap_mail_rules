"""The pydantic model of a rule file: rules, their locations, the condition expression tree and the actions.

Most fields are `Templatable`: instead of a plain value they may hold a `Var`, which a `Template` fills in.
`concrete()` resolves all of that, the evaluator only ever sees the result.
"""

from collections.abc import Mapping
from typing import Annotated, Any, Literal, Self
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


class Var(Strict):
    """A replaceable field of a template, filled from the `variables` (or `defaults`) of the template instance. YAML shorthand: `!var name`."""

    var: str = Field(min_length=1)
# end class


type Templatable[T] = T | Var


def is_var_reference(value: Any) -> bool:
    return isinstance(value, dict) and set(value) == {"var"}
# end def


def bind(value: Any, variables: Mapping[str, Any]) -> Any:
    """Resolves variable references in the raw data of `variables` / `defaults` against an outer scope."""
    if is_var_reference(value):
        return lookup(value["var"], variables)
    # end if
    if isinstance(value, dict):
        return {key: bind(item, variables) for key, item in value.items()}
    # end if
    if isinstance(value, list):
        return [bind(item, variables) for item in value]
    # end if
    return value
# end def


def lookup(name: str, variables: Mapping[str, Any]) -> Any:
    if name not in variables:
        raise ValueError(f"variable `{name}` has no value, set it in `variables` of the template or give the template a default")
    # end if
    return variables[name]
# end def


def used_variables(value: Any) -> set[str]:
    """Names of the variables a value needs from the scope it is in. A nested template needs only what its own `variables` refer to."""
    if isinstance(value, Var):
        return {value.var}
    # end if
    if is_var_reference(value):
        return {value["var"]}
    # end if
    if isinstance(value, Template):
        return used_variables(value.variables)
    # end if
    if isinstance(value, Strict):
        return set().union(*(used_variables(getattr(value, name)) for name in type(value).model_fields))
    # end if
    if isinstance(value, dict):
        return set().union(*(used_variables(item) for item in value.values()))
    # end if
    if isinstance(value, (list, tuple)):
        return set().union(*(used_variables(item) for item in value))
    # end if
    return set()
# end def


def substitute(value: Any, variables: Mapping[str, Any]) -> Any:
    if isinstance(value, Var):
        return lookup(value.var, variables)
    # end if
    if isinstance(value, Concrete):
        return value.concrete(variables)
    # end if
    if isinstance(value, list):
        return [substitute(item, variables) for item in value]
    # end if
    if isinstance(value, tuple):
        return tuple(substitute(item, variables) for item in value)
    # end if
    return value
# end def


class Concrete(Strict):
    """Base of everything that can hold a `Var`. `concrete()` returns the same thing with all variables replaced and validated again."""

    def concrete(self, variables: Mapping[str, Any] | None = None) -> Self:
        data = {name: substitute(getattr(self, name), variables or {}) for name in type(self).model_fields}
        return type(self).model_validate(data)
    # end def
# end class


class TextCondition(Concrete):
    """Compares a text field. `case_sensitive` is available for every operator."""

    type: Literal["text"] = "text"
    field: Templatable[TextField]
    operator: Templatable[TextOperator]
    value: Templatable[str | list[str]]
    case_sensitive: Templatable[bool] = False
    quantifier: Templatable[Quantifier] = Quantifier.any

    @model_validator(mode="after")
    def check_value(self) -> "TextCondition":
        if isinstance(self.operator, Var) or isinstance(self.value, Var):
            return self
        # end if
        if self.operator == TextOperator.in_ and not isinstance(self.value, list):
            raise ValueError("operator `in` needs a list of values")
        # end if
        if self.operator != TextOperator.in_ and not isinstance(self.value, str):
            raise ValueError(f"operator `{self.operator}` needs a single string value")
        # end if
        return self
    # end def
# end class


class HeaderCondition(Concrete):
    """Compares any header by name, for fields without a dedicated entry. Multiple headers of that name are quantified."""

    type: Literal["header"] = "header"
    name: Templatable[Annotated[str, Field(min_length=1)]]
    operator: Templatable[TextOperator]
    value: Templatable[str | list[str]]
    case_sensitive: Templatable[bool] = False
    quantifier: Templatable[Quantifier] = Quantifier.any

    @model_validator(mode="after")
    def check_value(self) -> "HeaderCondition":
        if isinstance(self.operator, Var) or isinstance(self.value, Var):
            return self
        # end if
        if self.operator == TextOperator.in_ and not isinstance(self.value, list):
            raise ValueError("operator `in` needs a list of values")
        # end if
        if self.operator != TextOperator.in_ and not isinstance(self.value, str):
            raise ValueError(f"operator `{self.operator}` needs a single string value")
        # end if
        return self
    # end def
# end class


class AddressCondition(Concrete):
    """Compares an address field, at the granularity given by `part`."""

    type: Literal["address"] = "address"
    field: Templatable[AddressField]
    part: Templatable[AddressPart] = AddressPart.address
    operator: Templatable[TextOperator]
    value: Templatable[str | list[str]]
    case_sensitive: Templatable[bool] = False
    quantifier: Templatable[Quantifier] = Quantifier.any

    @model_validator(mode="after")
    def check_value(self) -> "AddressCondition":
        if isinstance(self.operator, Var) or isinstance(self.value, Var):
            return self
        # end if
        if self.operator == TextOperator.in_ and not isinstance(self.value, list):
            raise ValueError("operator `in` needs a list of values")
        # end if
        if self.operator != TextOperator.in_ and not isinstance(self.value, str):
            raise ValueError(f"operator `{self.operator}` needs a single string value")
        # end if
        return self
    # end def
# end class


class NumberCondition(Concrete):
    type: Literal["number"] = "number"
    field: Templatable[NumberField]
    operator: Templatable[CompareOperator]
    value: Templatable[float | tuple[float, float]]
    quantifier: Templatable[Quantifier] = Quantifier.any

    @model_validator(mode="after")
    def check_value(self) -> "NumberCondition":
        if isinstance(self.operator, Var) or isinstance(self.value, Var):
            return self
        # end if
        if self.operator == CompareOperator.between and not isinstance(self.value, tuple):
            raise ValueError("operator `between` needs a [low, high] pair")
        # end if
        if self.operator != CompareOperator.between and isinstance(self.value, tuple):
            raise ValueError(f"operator `{self.operator}` needs a single number")
        # end if
        return self
    # end def
# end class


class DateCondition(Concrete):
    """Compares a date. A relative value `7d` is the moment 7 days before now."""

    type: Literal["date"] = "date"
    field: Templatable[DateField]
    operator: Templatable[CompareOperator]
    value: Templatable[TimeValue | tuple[TimeValue, TimeValue]]

    @model_validator(mode="after")
    def check_value(self) -> "DateCondition":
        if isinstance(self.operator, Var) or isinstance(self.value, Var):
            return self
        # end if
        if self.operator == CompareOperator.between and not isinstance(self.value, tuple):
            raise ValueError("operator `between` needs a [low, high] pair")
        # end if
        if self.operator != CompareOperator.between and isinstance(self.value, tuple):
            raise ValueError(f"operator `{self.operator}` needs a single date")
        # end if
        return self
    # end def
# end class


class BoolCondition(Concrete):
    type: Literal["bool"] = "bool"
    field: Templatable[BoolField]
    value: Templatable[bool] = True
    quantifier: Templatable[Quantifier] = Quantifier.any
# end class


class PresenceCondition(Concrete):
    """Tests whether a field or header is there (`exists`) or there but without content (`empty`)."""

    type: Literal["presence"] = "presence"
    field: Templatable[TextField | AddressField | NumberField | DateField | BoolField] | None = None
    header: Templatable[Annotated[str, Field(min_length=1)]] | None = None
    operator: Templatable[PresenceOperator] = PresenceOperator.exists
    value: Templatable[bool] = True

    @model_validator(mode="after")
    def check_target(self) -> "PresenceCondition":
        if (self.field is None) == (self.header is None):
            raise ValueError("exactly one of `field` and `header` is needed")
        # end if
        return self
    # end def
# end class


class AllExpression(Concrete):
    """AND: true if every nested expression is true."""

    type: Literal["all"] = "all"
    conditions: list["Expression"] = Field(min_length=1)
# end class


class AnyExpression(Concrete):
    """OR: true if at least one nested expression is true."""

    type: Literal["any"] = "any"
    conditions: list["Expression"] = Field(min_length=1)
# end class


class NotExpression(Concrete):
    type: Literal["not"] = "not"
    condition: "Expression"
# end class


class TemplateDefinition(Strict):
    """A reusable expression under the root `templates`. Its `Var`s may stay unfilled, `defaults` fill some of them."""

    type: Literal["template"] = "template"
    defaults: dict[str, Any] = Field(default_factory=dict, description="Values for variables an instance does not set.")
    content: "Expression"
# end class


class Template[C](Concrete):
    """Use of a template: the `content` with every `Var` replaced by `variables`, else `defaults`. Instance it with `<<: *anchor`."""

    type: Literal["template"] = "template"
    defaults: dict[str, Any] = Field(default_factory=dict, description="Values for variables `variables` does not set.")
    variables: dict[str, Any] = Field(default_factory=dict, description="Values of the template's variables, by name.")
    content: C

    @model_validator(mode="after")
    def check_variables(self) -> Self:
        needed = used_variables(self.content)
        missing = needed - self.variables.keys() - self.defaults.keys()
        if missing:
            raise ValueError(f"template variables without value or default: {', '.join(sorted(missing))}")
        # end if
        unknown = self.variables.keys() - needed
        if unknown:
            raise ValueError(f"template has no such variables: {', '.join(sorted(unknown))}")
        # end if
        return self
    # end def

    def concrete(self, variables: Mapping[str, Any] | None = None) -> Any:
        """Unlike other models this is replaced by its (resolved) content, not by a copy of itself."""
        scope = {**self.defaults, **bind(self.variables, variables or {})}
        return self.content.concrete(scope)
    # end def
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
    | PresenceCondition
    | Template["Expression"],
    Field(discriminator="type"),
]

TemplateDefinition.model_rebuild()
Template.model_rebuild()
AllExpression.model_rebuild()
AnyExpression.model_rebuild()
NotExpression.model_rebuild()


class Location(Concrete):
    """Where a rule applies. The account is referenced by its immutable id, never by its changeable name."""

    account_id: Templatable[UUID]
    folder: Templatable[str] = "INBOX"
    recursive: Templatable[bool] = False
# end class


class MoveAction(Concrete):
    type: Literal["move"] = "move"
    folder: Templatable[str]
    account_id: Templatable[UUID] | None = Field(default=None, description="Target account; the mail's own account if unset.")
# end class


class MarkReadAction(Concrete):
    type: Literal["mark_read"] = "mark_read"
# end class


class MarkUnreadAction(Concrete):
    type: Literal["mark_unread"] = "mark_unread"
# end class


class FlagAction(Concrete):
    type: Literal["flag"] = "flag"
    value: Templatable[bool] = True
# end class


class KeywordAction(Concrete):
    type: Literal["keyword"] = "keyword"
    keyword: Templatable[Annotated[str, Field(min_length=1)]]
    value: Templatable[bool] = True
# end class


Action = Annotated[
    MoveAction | MarkReadAction | MarkUnreadAction | FlagAction | KeywordAction,
    Field(discriminator="type"),
]


class Rule(Concrete):
    name: str = Field(min_length=1)
    enabled: Templatable[bool] = True
    locations: list[Location] = Field(min_length=1)
    when: Expression
    actions: list[Action] = Field(default_factory=list, description="Parsed only; nothing executes them yet.")
# end class


class RuleFile(Concrete):
    schema_: str | None = Field(default=None, alias="$schema")
    templates: dict[str, TemplateDefinition] = Field(default_factory=dict, description="Reusable expressions, used with `<<: *anchor`.")
    rules: list[Rule] = Field(default_factory=list)

    def concrete(self, variables: Mapping[str, Any] | None = None) -> Self:
        return super().concrete(variables).model_copy(update={"templates": {}})
    # end def
# end class
