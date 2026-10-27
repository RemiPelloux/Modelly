"""Reading NetLogo reporters: a cursor over the tokens and a precedence parser.

NetLogo separates nothing: ``random 10 + 1`` is read by knowing that ``random`` takes
one input and binds tighter than ``+``. The ``Vocabulary`` holds every name the code
tab declares, so an unknown word is reported instead of being read as a variable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from modelly.netlogo._syntax import (
    ARGUMENT_BINDING,
    INFIX,
    REPORTERS,
    Expr,
    Token,
    UntranslatableError,
)
from modelly.netlogo.colors import NAMES as COLOR_NAMES

__all__ = ["PATCH_BUILTINS", "TURTLE_BUILTINS", "Cursor", "Vocabulary", "parse_expr"]

# Variables every turtle and every patch has; the read-only ones cannot be ``set``.
TURTLE_BUILTINS = frozenset(
    {"color", "heading", "shape", "size", "label", "label-color", "hidden?"}
    | {"pen-size", "pen-mode", "xcor", "ycor", "who"}
)
PATCH_BUILTINS = frozenset({"pcolor", "plabel", "plabel-color", "pxcor", "pycor"})
HERE = "-here"
NO_BINDING = -1  # a word that is not an infix operator


@dataclass
class Vocabulary:
    """The names a NetLogo program may use, and the arity of its procedures."""

    variables: set[str] = field(default_factory=set)
    breeds: dict[str, str] = field(default_factory=dict)  # plural -> singular
    procedures: dict[str, tuple[int, bool]] = field(default_factory=dict)

    def is_agentset(self, word: str) -> bool:
        """Whether ``word`` names a breed or the turtles of a breed on this patch."""
        return word in self.breeds or (
            word.endswith(HERE) and word.removesuffix(HERE) in self.breeds
        )

    def is_variable(self, word: str, local: set[str]) -> bool:
        """Whether ``word`` is a declared, built-in or local variable, or a color."""
        return (
            word in self.variables
            or word in local
            or word in TURTLE_BUILTINS
            or word in PATCH_BUILTINS
            or word in COLOR_NAMES
        )


class Cursor:
    """A position in the tokens of one procedure, and the locals seen so far."""

    def __init__(self, tokens: list[Token], vocabulary: Vocabulary) -> None:
        """Start before the first token, with no locals."""
        self.tokens = tokens
        self.vocabulary = vocabulary
        self.position = 0
        self.locals: set[str] = set()

    def peek(self) -> str | None:
        """The next word, or None at the end."""
        if self.position >= len(self.tokens):
            return None
        return self.tokens[self.position].word

    def take(self) -> Token:
        """The next token, consumed.

        Raises:
            UntranslatableError: at the end of the tokens.
        """
        if self.position >= len(self.tokens):
            raise UntranslatableError("the procedure ends in the middle of a statement")
        token = self.tokens[self.position]
        self.position += 1
        return token

    def expect(self, word: str) -> None:
        """Consume ``word``.

        Raises:
            UntranslatableError: when the next word is another one.
        """
        found = self.take().word
        if found != word:
            raise UntranslatableError(f"expected {word!r}, found {found!r}")

    def line(self) -> int:
        """The source line of the next token (of the last one at the end)."""
        index = min(self.position, len(self.tokens) - 1)
        return self.tokens[index].line if self.tokens else 0


def literal(word: str) -> Expr | None:
    """A number or string literal, or None when ``word`` is neither."""
    if word.startswith('"'):
        return Expr("str", word[1:-1])
    if not any(char.isdigit() for char in word[:2]):
        return None  # float() would also read "inf" and "nan"
    try:
        value = float(word)
    except ValueError:
        return None
    return Expr("num", int(value) if value.is_integer() and "." not in word else value)


def inputs(cursor: Cursor, count: int) -> tuple[Expr, ...]:
    """``count`` inputs of a prefix reporter or command."""
    return tuple(parse_expr(cursor, ARGUMENT_BINDING) for _ in range(count))


def parse_primary(cursor: Cursor) -> Expr:
    """A literal, a parenthesised reporter, a reporter call or a variable.

    Raises:
        UntranslatableError: for a word outside the subset.
    """
    word = cursor.take().word
    found = literal(word)
    if found is not None:
        return found
    if word == "(":
        inner = parse_expr(cursor)
        cursor.expect(")")
        return inner
    vocabulary = cursor.vocabulary
    if word in REPORTERS:
        return Expr("call", word, inputs(cursor, REPORTERS[word]))
    if word in vocabulary.procedures and vocabulary.procedures[word][1]:
        return Expr("proc", word, inputs(cursor, vocabulary.procedures[word][0]))
    if vocabulary.is_agentset(word):
        return Expr("call", word)
    if vocabulary.is_variable(word, cursor.locals):
        return Expr("name", word)
    raise UntranslatableError(f"unknown reporter {word!r}")


def parse_expr(cursor: Cursor, binding: int = 0) -> Expr:
    """A reporter, reading infix operators that bind at least as tight as ``binding``."""
    left = parse_primary(cursor)
    while True:
        operator = cursor.peek()
        if operator is None or INFIX.get(operator, NO_BINDING) < binding:
            return left
        cursor.take()
        if operator == "with":
            cursor.expect("[")
            right = parse_expr(cursor)
            cursor.expect("]")
        else:
            right = parse_expr(cursor, INFIX[operator] + 1)
        left = Expr("op", operator, (left, right))
