"""Loading rule files."""

from pathlib import Path

import yaml

from .models import RuleFile


class RuleLoader(yaml.SafeLoader):
    """`yaml.SafeLoader` plus the shorthand `!var name` for `{var: name}`."""
# end class


def construct_var(loader: yaml.SafeLoader, node: yaml.ScalarNode) -> dict[str, str]:
    return {"var": str(loader.construct_scalar(node))}
# end def


RuleLoader.add_constructor("!var", construct_var)


def parse_rules(text: str) -> RuleFile:
    """Parses, validates and resolves the templates, so the result holds no `Var` or `Template`."""
    data = yaml.load(text, Loader=RuleLoader)  # noqa: S506, a SafeLoader subclass
    return RuleFile.model_validate(data if data is not None else {}).concrete()
# end def


def load_rules(path: Path) -> RuleFile:
    return parse_rules(path.read_text(encoding="utf-8"))
# end def
