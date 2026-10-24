"""The local JSON-schema subset and reading JSON out of a reply."""

import re

import pytest

from modelly.llm import SchemaError, parse_json, validate

PERSON = {
    "type": "object",
    "required": ["name", "age"],
    "additionalProperties": False,
    "properties": {
        "name": {"type": "string", "minLength": 1, "maxLength": 5},
        "age": {"type": "integer", "minimum": 0, "maximum": 120},
        "tags": {"type": "array", "items": {"enum": ["a", "b"]}, "maxItems": 2},
        "score": {"type": ["number", "null"]},
    },
}


@pytest.mark.parametrize(
    "value",
    [
        {"name": "Ann", "age": 30},
        {"name": "Bo", "age": 0, "tags": ["a", "b"], "score": 1.5},
        {"name": "Cy", "age": 120, "score": None},
    ],
)
def test_valid_values_pass(value):
    """A matching value comes back unchanged."""
    assert validate(value, PERSON) == value


@pytest.mark.parametrize(
    ("value", "where"),
    [
        ({"name": "Ann"}, "missing required property 'age'"),
        ({"name": "Ann", "age": "30"}, "$.age: expected integer"),
        ({"name": "Ann", "age": True}, "$.age: expected integer"),
        ({"name": "Ann", "age": -1}, "$.age: -1 is below the minimum"),
        ({"name": "Ann", "age": 121}, "above the maximum"),
        ({"name": "", "age": 1}, "shorter than minLength"),
        ({"name": "Annabel", "age": 1}, "longer than maxLength"),
        ({"name": "A", "age": 1, "tags": ["c"]}, "$.tags[0]: 'c' is not one of"),
        ({"name": "A", "age": 1, "tags": ["a", "a", "a"]}, "more items than maxItems"),
        ({"name": "A", "age": 1, "extra": 1}, "unexpected property 'extra'"),
        ({"name": "A", "age": 1, "score": "x"}, "expected number or null"),
        (["not", "an", "object"], "expected object"),
    ],
)
def test_invalid_values_say_where(value, where):
    """The error names the path and the broken keyword."""
    with pytest.raises(SchemaError, match=re.escape(where)):
        validate(value, PERSON)


def test_unsupported_keywords_are_refused():
    """A schema keyword the validator does not know is an error, not silently ignored."""
    with pytest.raises(ValueError, match="pattern"):
        validate("x", {"type": "string", "pattern": "^x$"})
    with pytest.raises(ValueError, match="unsupported type"):
        validate("x", {"type": "text"})


def test_min_items_and_number_bounds():
    """MinItems on arrays; minimum applies to numbers only."""
    with pytest.raises(SchemaError, match="fewer items"):
        validate([], {"type": "array", "minItems": 1})
    assert validate("abc", {"minimum": 5}) == "abc"


@pytest.mark.parametrize(
    "text",
    [
        '{"opinion": "agree"}',
        '```json\n{"opinion": "agree"}\n```',
        'Sure! Here it is: {"opinion": "agree"} Hope that helps.',
        '  \n{"opinion": "agree"}\n',
    ],
)
def test_parse_json_finds_the_value(text):
    """Plain, fenced or surrounded by prose."""
    assert parse_json(text) == {"opinion": "agree"}


def test_parse_json_without_json():
    """Prose alone is a schema error, so it can be repaired."""
    with pytest.raises(SchemaError, match="no JSON"):
        parse_json("I agree, mostly {sort of")
