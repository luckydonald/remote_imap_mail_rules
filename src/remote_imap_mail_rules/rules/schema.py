"""Generates the JSON schema of the rule file, modelled after `scripts/sync_todos.py`.

    uv run python -m remote_imap_mail_rules.rules.schema --write-schema
    uv run python -m remote_imap_mail_rules.rules.schema --check
"""

import argparse
import json
import sys
from pathlib import Path

from .models import RuleFile

SCHEMA_PATH = Path(__file__).resolve().parents[3] / "schemas" / "rules.schema.json"


def schema_text() -> str:
    body = RuleFile.model_json_schema(by_alias=True)
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": SCHEMA_PATH.name,
        "title": "Mail rules",
        **body,
    }
    return json.dumps(schema, indent=2, ensure_ascii=False) + "\n"
# end def


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write-schema", action="store_true", help="Write the schema file.")
    group.add_argument("--check", action="store_true", help="Fail if the schema file is outdated.")
    args = parser.parse_args(argv)
    text = schema_text()
    if args.write_schema:
        SCHEMA_PATH.parent.mkdir(parents=True, exist_ok=True)
        SCHEMA_PATH.write_text(text, encoding="utf-8")
        return 0
    # end if
    if not SCHEMA_PATH.exists() or SCHEMA_PATH.read_text(encoding="utf-8") != text:
        print(f"{SCHEMA_PATH} is outdated, run with --write-schema.", file=sys.stderr)
        return 1
    # end if
    return 0
# end def


if __name__ == "__main__":
    sys.exit(main())
# end if
