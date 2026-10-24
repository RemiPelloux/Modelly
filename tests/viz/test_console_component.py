"""Tests for the CommandConsole solara component, driven through its input field."""

import ipyvue
import ipyvuetify as vw
import solara

from modelly.viz.console.console import CommandConsole, ConsoleInput


def _markdown_text(rc):
    """The rendered HTML of every Markdown block, joined."""
    return " ".join(w.template for w in rc.find(ipyvue.VueTemplate).widgets)


def _type(field, text, event="keypress.enter"):
    field.v_model = text
    field.fire_event(event, None)


def test_command_console_executes_and_renders_entries():
    """Command console executes and renders entries."""
    _, rc = solara.render(
        CommandConsole(model="M", additional_imports={"k": 4}), handle_error=False
    )
    field = rc.find(vw.TextField).widget
    assert field.v_model == ""
    assert "Type 'tips' for usage instructions." in _markdown_text(rc)

    _type(field, "print(model * k)")
    assert rc.find(vw.TextField).widget.v_model == ""
    text = _markdown_text(rc)
    assert "<span>print(model * k)</span>" in text
    assert "MMMM<br>" in text

    _type(rc.find(vw.TextField).widget, "cls")
    assert "print(model * k)" not in _markdown_text(rc)


def test_command_console_history_navigation_with_arrow_keys():
    """Command console history navigation with arrow keys."""
    _, rc = solara.render(CommandConsole(), handle_error=False)
    field = rc.find(vw.TextField).widget
    _type(field, "a = 1")
    _type(field, "b = 2")
    field = rc.find(vw.TextField).widget
    field.v_model = "draft"
    field.fire_event("keyup.38", None)
    assert rc.find(vw.TextField).widget.v_model == "b = 2"
    rc.find(vw.TextField).widget.fire_event("keyup.38", None)
    assert rc.find(vw.TextField).widget.v_model == "a = 1"
    rc.find(vw.TextField).widget.fire_event("keydown.40", None)
    assert rc.find(vw.TextField).widget.v_model == "b = 2"
    rc.find(vw.TextField).widget.fire_event("keydown.40", None)
    assert rc.find(vw.TextField).widget.v_model == "draft"


def test_console_input_calls_back_with_text_and_setter():
    """Console input calls back with text and setter."""
    calls = []

    def on_submit(text, set_text):
        calls.append(("submit", text))
        set_text("")

    def on_up(text, set_text):
        calls.append(("up", text))
        set_text("previous")

    def on_down(set_text):
        calls.append(("down",))
        set_text("next")

    _, rc = solara.render(
        ConsoleInput(on_submit=on_submit, on_up=on_up, on_down=on_down),
        handle_error=False,
    )
    field = rc.find(vw.TextField).widget
    assert field.attributes == {"spellcheck": "false", "autocomplete": "off"}
    field.v_model = "x = 1"
    field.fire_event("keypress.enter", None)
    assert rc.find(vw.TextField).widget.v_model == ""
    rc.find(vw.TextField).widget.fire_event("keyup.38", None)
    assert rc.find(vw.TextField).widget.v_model == "previous"
    rc.find(vw.TextField).widget.fire_event("keydown.40", None)
    assert rc.find(vw.TextField).widget.v_model == "next"
    assert calls == [("submit", "x = 1"), ("up", ""), ("down",)]
