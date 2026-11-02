"""Loading rule files."""

from pathlib import Path

import yaml

from .models import RuleFile


def parse_rules(text: str) -> RuleFile:
    data = yaml.safe_load(text)
    return RuleFile.model_validate(data if data is not None else {})
# end def


def load_rules(path: Path) -> RuleFile:
    return parse_rules(path.read_text(encoding="utf-8"))
# end def
