"""Tests for reading NetLogo: tokens, the interface tab and the code tab."""

from modelly.netlogo._interface import World, parse_interface
from modelly.netlogo._parser import parse_program
from modelly.netlogo._syntax import Expr, tokenize
from tests.netlogo.shared import bundled


def body(code: str, sliders=()):
    """The parsed body of the procedure ``to p ... end`` around ``code``."""
    program, _ = parse_program(f"globals [g]\nto p\n{code}\nend", list(sliders))
    return program.procedures["p"].body


def test_tokenize_drops_comments_and_keeps_strings():
    """Comments go, strings keep their case and semicolons, words are lower-cased."""
    tokens = tokenize('Set X 1 ; a comment\nshow "a;B"')
    assert [t.word for t in tokens] == ["set", "x", "1", "show", '"a;B"']
    assert [t.line for t in tokens] == [1, 1, 1, 2, 2]


def test_prefix_reporters_bind_tighter_than_arithmetic():
    """``random 10 + 1`` is ``(random 10) + 1``; ``with`` binds into ``count``."""
    (stmt,) = body("set g random 10 + 1")
    assert stmt.args[0] == Expr(
        "op", "+", (Expr("call", "random", (Expr("num", 10),)), Expr("num", 1))
    )
    (stmt,) = body("set g count patches with [pxcor > 0] * 2")
    counted = stmt.args[0].args[0]
    assert counted.value == "count" and counted.args[0].value == "with"


def test_blocks_and_declarations():
    """Breeds, own variables, procedures with inputs and nested blocks are read."""
    code = (
        "breed [wolves wolf]\nturtles-own [energy]\nwolves-own [hunger]\n"
        "to go\n  ask wolves [ ifelse energy > 0 [ fd 1 ] [ die ] ]\n  tick\nend\n"
        "to-report double [x]\n  report x * 2\nend"
    )
    program, skipped = parse_program(code, [])
    assert skipped == []
    assert program.breeds == {"wolves": "wolf"}
    assert program.breed_vars == {"wolves": ["hunger"]}
    ask, tick = program.procedures["go"].body
    assert ask.kind == "ask" and ask.blocks[0][0].kind == "ifelse"
    assert tick.kind == "command" and tick.name == "tick"
    assert program.procedures["double"].params == ["x"]


def test_unsupported_command_is_skipped_to_the_end_of_its_line():
    """An unknown primitive becomes ``untranslated``; the next line is read."""
    stmts = body("layout-circle turtles 5\nset g 1\nask patches [ diffuse g 0.5 ]")
    assert [s.kind for s in stmts] == ["untranslated", "set", "ask"]
    assert "layout-circle" in stmts[0].name and stmts[0].line == 3
    inner = stmts[2].blocks[0]
    assert [s.kind for s in inner] == ["untranslated"]


def test_unknown_reporter_and_declaration_are_reported():
    """An unknown reporter fails its statement; an unknown declaration is listed."""
    stmts = body("set g distance one-of turtles")
    assert stmts[0].kind == "untranslated" and "distance" in stmts[0].name
    _, skipped = parse_program("extensions [gis]\nto p\nend", [])
    assert len(skipped) == 1 and "extensions" in skipped[0].name


def test_interface_sliders_switches_and_world():
    """Sliders become int or float fields, switches bools, the view the world."""
    interface = parse_interface(bundled("wolf_sheep").split("@#$#@#$#@")[1])
    fields = {f.name: (f.kind, f.default) for f in interface.fields}
    assert fields["initial-number-sheep"] == ("int", 100)
    assert fields["grass?"] == ("bool", True)
    assert interface.world == World(-25, 25, -25, 25, wrap=True)
    fire = parse_interface(bundled("fire").split("@#$#@#$#@")[1])
    assert fire.world == World(-125, 125, -125, 125, wrap=False)
    assert [f.name for f in fire.fields] == ["density"]


def test_float_slider_and_skipped_widgets():
    """A slider with a fractional step is a float; a chooser is listed as skipped."""
    text = (
        "SLIDER\n1\n2\n3\n4\nrate\nrate\n0\n1\n0.25\n0.05\n1\nNIL\nHORIZONTAL\n\n"
        'CHOOSER\n1\n2\n3\n4\nmode\nmode\n"a" "b"\n0\n'
    )
    interface = parse_interface(text)
    assert [(f.name, f.kind, f.default) for f in interface.fields] == [
        ("rate", "float", 0.25)
    ]
    assert interface.skipped == ["CHOOSER mode"]
    assert parse_interface("").world == World()
