"""Keeps the YAML examples of `rules/README.md` valid."""

import re
from pathlib import Path

import pytest
import yaml
from pydantic import TypeAdapter

from remote_imap_mail_rules.rules.models import Action, Expression, RuleFile

README = Path(__file__).resolve().parents[1] / "rules" / "README.md"
BLOCKS = [block for block in re.findall(r"```yaml\n(.*?)```", README.read_text(encoding="utf-8"), re.S) if "name: ...\n" not in block]


@pytest.mark.parametrize("block", BLOCKS, ids=[block.strip().splitlines()[0][:40] for block in BLOCKS])
def test_readme_example_is_valid(block: str) -> None:
    data = yaml.safe_load(block)
    if isinstance(data, dict) and "rules" in data:
        RuleFile.model_validate(data).concrete()
    elif isinstance(data, dict) and set(data) == {"when"}:
        TypeAdapter(Expression).validate_python(data["when"])
    elif isinstance(data, dict) and set(data) == {"actions"}:
        [TypeAdapter(Action).validate_python(item) for item in data["actions"]]
    elif isinstance(data, dict) and "type" in data:
        TypeAdapter(Expression).validate_python(data)
    elif isinstance(data, list):
        [TypeAdapter(Expression).validate_python(item) for item in data]
    else:
        pytest.fail(f"unrecognized example shape: {block[:60]!r}")
    # end if
# end def
