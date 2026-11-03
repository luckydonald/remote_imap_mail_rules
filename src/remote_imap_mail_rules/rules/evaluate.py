"""Evaluates a rule expression tree against a mail."""

from datetime import UTC, datetime
from typing import Never

from ..mail import Mail
from .extract import address_values, bool_values, date_value, header_values, number_values, text_values
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
)
from .models import (
    AddressCondition,
    AllExpression,
    AnyExpression,
    BoolCondition,
    DateCondition,
    Expression,
    HeaderCondition,
    NotExpression,
    NumberCondition,
    PresenceCondition,
    TextCondition,
)
from .operators import compare_any, compare_text
from .values import AbsoluteTime, RelativeDuration


def quantify(results: list[bool], quantifier: Quantifier) -> bool:
    """Combines per-value results. No values at all is a missing field, which is false for every quantifier."""
    if not results:
        return False
    # end if
    match quantifier:
        case Quantifier.any:
            return any(results)
        case Quantifier.all:
            return all(results)
        case Quantifier.none:
            return not any(results)
    # end match
    return False
# end def


async def text_field_values(mail: Mail, field: TextField) -> list[str] | None:
    if field in {TextField.body_text, TextField.body_html}:
        bodies = await mail.load_bodies()
        return text_values(mail, field, bodies.text, bodies.html)
    # end if
    return text_values(mail, field, None, None)
# end def


def resolve_time(value: AbsoluteTime | RelativeDuration, now: datetime) -> datetime:
    return value.resolve(now)
# end def


def aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value
# end def


async def evaluate_presence(condition: PresenceCondition[Never], mail: Mail) -> bool:
    values: list | None
    if condition.header is not None:
        values = header_values(mail, condition.header)
    else:
        field = condition.field
        if isinstance(field, TextField):
            values = await text_field_values(mail, field)
        elif isinstance(field, AddressField):
            values = address_values(mail, field, AddressPart.address)
        elif isinstance(field, NumberField):
            values = number_values(mail, field)
        elif isinstance(field, DateField):
            date = date_value(mail, field)
            values = [date] if date is not None else None
        elif isinstance(field, BoolField):
            values = bool_values(mail, field)
        else:
            values = None
        # end if
    # end if
    present = values is not None
    if condition.operator == PresenceOperator.exists:
        return present == condition.value
    # end if
    if not present:
        return False
    # end if
    is_empty = all(value == "" for value in values)
    return is_empty == condition.value
# end def


async def evaluate(expression: Expression[Never], mail: Mail, now: datetime | None = None) -> bool:
    """True if the mail matches. `now` is the reference for relative durations."""
    now = now or datetime.now(UTC)
    match expression:
        case AllExpression():
            for child in expression.conditions:
                if not await evaluate(child, mail, now):
                    return False
                # end if
            # end for
            return True
        case AnyExpression():
            for child in expression.conditions:
                if await evaluate(child, mail, now):
                    return True
                # end if
            # end for
            return False
        case NotExpression():
            return not await evaluate(expression.condition, mail, now)
        case TextCondition():
            texts = await text_field_values(mail, expression.field)
            return evaluate_texts(texts, expression)
        case HeaderCondition():
            return evaluate_texts(header_values(mail, expression.name), expression)
        case AddressCondition():
            return evaluate_texts(address_values(mail, expression.field, expression.part), expression)
        case NumberCondition():
            numbers = number_values(mail, expression.field)
            if numbers is None:
                return False
            # end if
            return quantify([compare_any(expression.operator, number, expression.value) for number in numbers], expression.quantifier)
        case DateCondition():
            return evaluate_date(expression, mail, now)
        case BoolCondition():
            booleans = bool_values(mail, expression.field)
            if booleans is None:
                return False
            # end if
            return quantify([flag == expression.value for flag in booleans], expression.quantifier)
        case PresenceCondition():
            return await evaluate_presence(expression, mail)
    # end match
    raise ValueError(f"unsupported expression {expression!r}")
# end def


def evaluate_texts(texts: list[str] | None, condition: TextCondition[Never] | HeaderCondition[Never] | AddressCondition[Never]) -> bool:
    if texts is None:
        return False
    # end if
    results = [compare_text(condition.operator, text, condition.value, condition.case_sensitive) for text in texts]
    return quantify(results, condition.quantifier)
# end def


def evaluate_date(condition: DateCondition[Never], mail: Mail, now: datetime) -> bool:
    actual = date_value(mail, condition.field)
    if actual is None:
        return False
    # end if
    expected = condition.value
    if isinstance(expected, tuple):
        resolved = tuple(sorted(aware(resolve_time(item, now)) for item in expected))
    else:
        resolved = aware(resolve_time(expected, now))
    # end if
    if condition.operator == CompareOperator.between and not isinstance(resolved, tuple):
        return False
    # end if
    return compare_any(condition.operator, aware(actual), resolved)
# end def
