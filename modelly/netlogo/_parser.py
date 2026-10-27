"""Reading a NetLogo code tab: declarations first, then each procedure's commands.

A command outside the subset does not stop the translation: the parser skips to the
end of its line (and past any block it opens), and records it as ``untranslated``
with the reason, so the translated model shows the line and the report lists it.
"""

from __future__ import annotations

from modelly.netlogo._expressions import Cursor, Vocabulary, parse_expr
from modelly.netlogo._syntax import (
    BLOCK_COMMANDS,
    COMMANDS,
    CREATE_TURTLES,
    DISPLAY,
    Expr,
    Procedure,
    Program,
    Stmt,
    Token,
    UntranslatableError,
    tokenize,
)

__all__ = ["parse_program"]

OWN = "-own"
# A declaration parsed as a list of names: keyword -> the Program list it fills.
NAME_LISTS = {
    "globals": "globals",
    "turtles-own": "turtle_vars",
    "patches-own": "patch_vars",
}


def creator(word: str, vocabulary: Vocabulary) -> tuple[str, str] | None:
    """``(kind, breed)`` of a turtle-creating command, ``breed`` empty for plain turtles."""
    if word in CREATE_TURTLES:
        return "create", ""
    for kind in ("create", "hatch", "sprout"):
        if word == kind and kind != "create":
            return kind, ""
        breed = word.removeprefix(kind + "-")
        if breed != word and breed in vocabulary.breeds:
            return kind, breed
    return None


def arguments(cursor: Cursor, count: int) -> tuple[Expr, ...]:
    """``count`` inputs of a command: each a whole reporter, operators included."""
    return tuple(parse_expr(cursor) for _ in range(count))


def block(cursor: Cursor) -> tuple[Stmt, ...]:
    """A ``[ ... ]`` block of commands."""
    cursor.expect("[")
    body = statements(cursor, "]")
    cursor.expect("]")
    return body


def optional_block(cursor: Cursor) -> tuple[tuple[Stmt, ...], ...]:
    """The block after a creating command, when there is one."""
    return (block(cursor),) if cursor.peek() == "[" else ()


def assignment(cursor: Cursor, kind: str, line: int) -> Stmt:
    """``set name value`` or ``let name value``."""
    name = cursor.take().word
    if kind == "let":
        cursor.locals.add(name)
    elif not cursor.vocabulary.is_variable(name, cursor.locals):
        raise UntranslatableError(f"set of an unknown variable {name!r}")
    return Stmt(kind, name, (parse_expr(cursor),), line=line)


def statement(cursor: Cursor) -> Stmt:
    """One command and its inputs and blocks.

    Raises:
        UntranslatableError: for a command outside the subset.
    """
    line = cursor.line()
    word = cursor.take().word
    if word in ("set", "let"):
        return assignment(cursor, word, line)
    if word in BLOCK_COMMANDS:
        count, blocks = BLOCK_COMMANDS[word]
        args = arguments(cursor, count)
        found = tuple(block(cursor) for _ in range(blocks))
        return Stmt(word, args=args, blocks=found, line=line)
    if word == "report":
        return Stmt("report", args=(parse_expr(cursor),), line=line)
    created = creator(word, cursor.vocabulary)
    if created:
        amount = (parse_expr(cursor),)
        return Stmt(created[0], created[1], amount, optional_block(cursor), line=line)
    return command(cursor, word, line)


def command(cursor: Cursor, word: str, line: int) -> Stmt:
    """A primitive command, a display command or a call of a user procedure.

    Raises:
        UntranslatableError: for a command outside the subset.
    """
    procedures = cursor.vocabulary.procedures
    if word in COMMANDS:
        return Stmt("command", word, arguments(cursor, COMMANDS[word]), line=line)
    if word in DISPLAY:
        return Stmt("display", word, arguments(cursor, DISPLAY[word]), line=line)
    if word in procedures and not procedures[word][1]:
        return Stmt("call", word, arguments(cursor, procedures[word][0]), line=line)
    raise UntranslatableError(f"unknown command {word!r}")


def skip(cursor: Cursor, reason: str) -> Stmt:
    """Skip the rest of the line and any block it opens; record what was skipped."""
    line, depth = cursor.line(), 0
    while cursor.peek() is not None:
        word = cursor.tokens[cursor.position]
        if word.line != line and depth == 0:
            break
        if word.word == "]" and depth == 0:
            break
        depth += {"[": 1, "]": -1}.get(word.word, 0)
        cursor.position += 1
    return Stmt("untranslated", reason, line=line)


def statements(cursor: Cursor, closing: str | None = None) -> tuple[Stmt, ...]:
    """Commands up to ``closing`` (or the end); a bad one becomes ``untranslated``."""
    found = []
    while cursor.peek() is not None and cursor.peek() != closing:
        start = cursor.position
        try:
            found.append(statement(cursor))
        except UntranslatableError as error:
            cursor.position = start
            found.append(skip(cursor, str(error)))
    return tuple(found)


def names(cursor: Cursor) -> list[str]:
    """The words of a ``[ a b c ]`` declaration."""
    cursor.expect("[")
    found = []
    while cursor.peek() not in ("]", None):
        found.append(cursor.take().word)
    cursor.expect("]")
    return found


def procedure(cursor: Cursor, reporter: bool, line: int) -> Procedure:
    """The header of a ``to`` or ``to-report`` procedure and the tokens of its body."""
    name = cursor.take().word
    params = names(cursor) if cursor.peek() == "[" else []
    body: list[Token] = []
    while cursor.peek() not in ("end", None):
        body.append(cursor.take())
    cursor.expect("end")
    return Procedure(name, params, reporter, line, tokens=body)


def declaration(cursor: Cursor, program: Program, skipped: list[Stmt]) -> None:
    """Read one top-level declaration into ``program``; record one it does not know."""
    line = cursor.line()
    word = cursor.take().word
    if word in NAME_LISTS:
        getattr(program, NAME_LISTS[word]).extend(names(cursor))
    elif word == "breed":
        plural, singular = names(cursor)
        program.breeds[plural] = singular
    elif word.endswith(OWN) and word != "links-own":
        program.breed_vars[word.removesuffix(OWN)] = names(cursor)
    elif word in ("to", "to-report"):
        found = procedure(cursor, word == "to-report", line)
        program.procedures[found.name] = found
    else:
        if cursor.peek() == "[":
            names(cursor)
        skipped.append(Stmt("untranslated", f"declaration {word!r}", line=line))


def parse_program(code: str, sliders: list[str]) -> tuple[Program, list[Stmt]]:
    """The program of a code tab, and the top-level declarations it could not read.

    ``sliders`` are the interface's variable names: globals the code may read.
    """
    program = Program(lines=code.splitlines())
    skipped: list[Stmt] = []
    cursor = Cursor(tokenize(code), Vocabulary())
    while cursor.peek() is not None:
        try:
            declaration(cursor, program, skipped)
        except (UntranslatableError, ValueError):
            skipped.append(
                Stmt(
                    "untranslated",
                    "a declaration that does not parse",
                    line=cursor.line(),
                )
            )
    vocabulary = vocabulary_of(program, sliders)
    for found in program.procedures.values():
        body = Cursor(found.tokens, vocabulary)
        body.locals.update(found.params)
        found.body = statements(body)
    return program, skipped


def vocabulary_of(program: Program, sliders: list[str]) -> Vocabulary:
    """The names the procedures of ``program`` may use."""
    variables = {*program.globals, *sliders, *program.patch_vars}
    variables |= program.turtle_variables()
    procedures = {
        p.name: (len(p.params), p.reporter) for p in program.procedures.values()
    }
    return Vocabulary(variables, dict(program.breeds), procedures)
