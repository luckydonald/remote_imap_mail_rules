"""Pure comparison functions of the rule operators."""

import fnmatch
import re

from .fields import CompareOperator, TextOperator


def compare_text(operator: TextOperator, actual: str, expected: str | list[str], case_sensitive: bool) -> bool:
    if operator == TextOperator.regex:
        assert isinstance(expected, str)
        return re.search(expected, actual, 0 if case_sensitive else re.IGNORECASE) is not None
    # end if
    if not case_sensitive:
        actual = actual.casefold()
        expected = [item.casefold() for item in expected] if isinstance(expected, list) else expected.casefold()
    # end if
    if operator == TextOperator.in_:
        assert isinstance(expected, list)
        return actual in expected
    # end if
    assert isinstance(expected, str)
    match operator:
        case TextOperator.equals:
            return actual == expected
        case TextOperator.contains:
            return expected in actual
        case TextOperator.startswith:
            return actual.startswith(expected)
        case TextOperator.endswith:
            return actual.endswith(expected)
        case TextOperator.glob:
            return fnmatch.fnmatchcase(actual, expected)
    # end match
    raise ValueError(f"unsupported text operator {operator}")
# end def


def compare_any(operator: CompareOperator, actual, expected) -> bool:  # noqa: ANN001 - numbers and datetimes alike
    if operator == CompareOperator.between:
        low, high = expected
        return low <= actual <= high
    # end if
    match operator:
        case CompareOperator.eq:
            return actual == expected
        case CompareOperator.ne:
            return actual != expected
        case CompareOperator.lt:
            return actual < expected
        case CompareOperator.gt:
            return actual > expected
        case CompareOperator.gte:
            return actual >= expected
        case CompareOperator.lte:
            return actual <= expected
    # end match
    raise ValueError(f"unsupported operator {operator}")
# end def
