"""Shared support for models that can contain template variables."""

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
# end class


class Var(Strict):
    """A replaceable field of a template, filled from the `variables` (or `defaults`) of the template instance. YAML shorthand: `!var name`."""

    var: str = Field(min_length=1)
# end class


type Templatable[T, V = Var] = T | V


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


def concretize(model: "Concrete", variables: Mapping[str, Any] | None) -> Any:
    """Replaces the variables in the fields of `model` and validates again. The subclasses narrow the return type to their `[Never]` form."""
    data = {name: substitute(getattr(model, name), variables or {}) for name in type(model).model_fields}
    return type(model).model_validate(data)
# end def


class Concrete(Strict):
    """Base of everything that can hold a `Var`.

    The classes with fields are generic in `V`: `Rule` is `Rule[Var]`, the form that is parsed and may hold variables.
    `concrete()` returns the `[Never]` form, where `Templatable[T, Never]` is just `T`, so a type checker sees no `Var` and no `Template` anymore.
    """

    def concrete(self, variables: Mapping[str, Any] | None = None) -> Any:
        return concretize(self, variables)
    # end def
# end class
