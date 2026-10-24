"""Tests for the command console state: history, special commands, multi-line blocks."""

import sys

import pytest

from modelly.viz.console.html import format_command_html, format_output_html
from modelly.viz.console.interpreter import CaptureOutput, InteractiveConsole
from modelly.viz.console.manager import ConsoleEntry, ConsoleManager
from modelly.viz.utils import update_counter


class _Input:
    """Records what the console writes back into the input field."""

    def __init__(self):
        self.values = []

    def __call__(self, text):
        self.values.append(text)

    @property
    def last(self):
        return self.values[-1]


@pytest.fixture
def console():
    """Console."""
    return ConsoleManager(model="the-model", additional_imports={"answer": 42})


def run(console, *lines):
    """Run."""
    setter = _Input()
    for line in lines:
        console.execute_code(line, setter)
    return setter


def test_locals_hold_model_and_imports(console):
    """Locals hold model and imports."""
    assert console.locals_dict == {"model": "the-model", "answer": 42}
    run(console, "print(model, answer)")
    entry = console.get_entries()[-1]
    assert entry.output == "the-model 42\n"
    assert not entry.is_error


def test_no_model_no_imports_gives_empty_locals():
    """No model no imports gives empty locals."""
    assert ConsoleManager().locals_dict == {}


def test_single_line_output_and_input_cleared(console):
    """Single line output and input cleared."""
    setter = run(console, "1 + 2")
    assert setter.last == ""
    [entry] = console.get_entries()
    assert entry.command == "1 + 2"
    assert entry.output == "3\n"
    assert entry.is_continuation is False


def test_single_line_error_is_flagged(console):
    """Single line error is flagged."""
    run(console, "1 / 0")
    entry = console.get_entries()[-1]
    assert entry.is_error
    assert "ZeroDivisionError" in entry.output


def test_running_a_line_forces_an_update(console):
    """Running a line forces an update."""
    before = update_counter.value
    run(console, "x = 1")
    assert update_counter.value == before + 1


def test_multiline_block_completed_by_empty_line(console):
    """Multiline block completed by empty line."""
    run(console, "for i in range(2):", "    print(i)", "")
    entries = console.get_entries()
    assert len(entries) == 1
    block = entries[0]
    assert block.command == "for i in range(2):\n    print(i)"
    assert block.output == "0\n1\n"
    assert not block.is_continuation
    assert console.buffer == []


def test_multiline_block_with_error(console):
    """Multiline block with error."""
    run(console, "if True:", "    raise ValueError('boom')", "")
    block = console.get_entries()[-1]
    assert block.is_error
    assert "ValueError: boom" in block.output


def test_continuation_entries_while_buffering(console):
    """Continuation entries while buffering."""
    run(console, "def f():", "    return 5")
    entries = console.get_entries()
    assert [e.is_continuation for e in entries] == [True, True]
    assert console.buffer == ["def f():", "    return 5"]


def test_block_closed_by_a_complete_line():
    """A line that completes a buffered block replaces its continuation entries."""
    console = ConsoleManager()
    run(console, "x = (1 +")
    assert console.buffer == ["x = (1 +"]
    run(console, "2)")
    entries = console.get_entries()
    assert len(entries) == 1
    assert entries[0].command == "x = (1 +\n2)"
    assert not entries[0].is_continuation
    assert console.buffer == []
    assert console.console.locals["x"] == 3


def test_empty_line_without_buffer_adds_blank_entry(console):
    """Empty line without buffer adds blank entry."""
    run(console, "   ")
    [entry] = console.get_entries()
    assert entry.command == ""
    assert entry.output == ""


def test_tips_command(console):
    """Tips command."""
    run(console, "tips")
    entry = console.get_entries()[-1]
    assert entry.command == "[tips]"
    assert "cls" in entry.output
    assert "history" in entry.output


def test_history_when_empty(console):
    """History when empty."""
    run(console, "history")
    entry = console.get_entries()[-1]
    assert entry.command == "[history]"
    assert entry.output == "No history"


def test_history_lists_commands_but_hides_special_ones(console):
    """History lists commands but hides special ones."""
    run(console, "a = 1", "print('hi')", "tips", "", "history")
    output = console.get_entries()[-1].output
    assert "Command: a = 1" in output
    assert "Output: None" in output
    assert "Command: print('hi')" in output
    assert "Output: hi" in output
    assert "[tips]" not in output


def test_cls_clears_history_but_keeps_variables(console):
    """Cls clears history but keeps variables."""
    run(console, "value = 7", "history")
    console.history_index = 0
    run(console, "cls")
    assert console.get_entries() == []
    assert console.history_index == -1
    assert console.current_input == ""
    run(console, "print(value)")
    assert console.get_entries()[-1].output == "7\n"


def test_prev_command_on_empty_history_does_nothing(console):
    """Prev command on empty history does nothing."""
    setter = _Input()
    console.prev_command("draft", setter)
    assert setter.values == []
    assert console.history_index == -1


def test_history_navigation_up_and_down(console):
    """History navigation up and down."""
    run(console, "a = 1", "b = 2", "c = 3")
    setter = _Input()
    console.prev_command("draft", setter)
    assert setter.last == "c = 3"
    assert console.current_input == "draft"
    console.prev_command("ignored", setter)
    assert setter.last == "b = 2"
    console.prev_command("ignored", setter)
    console.prev_command("ignored", setter)  # stays at the oldest entry
    assert setter.last == "a = 1"
    assert console.history_index == 0
    console.next_command(setter)
    assert setter.last == "b = 2"
    console.next_command(setter)
    console.next_command(setter)  # past the end restores the draft
    assert setter.last == "draft"
    assert console.history_index == -1


def test_next_command_outside_navigation_does_nothing(console):
    """Next command outside navigation does nothing."""
    run(console, "a = 1")
    setter = _Input()
    console.next_command(setter)
    assert setter.values == []


def test_console_entry_repr():
    """Console entry repr."""
    entry = ConsoleEntry("cmd", "out", True, False)
    assert repr(entry) == "ConsoleEntry(cmd, out, True, False)"


def test_capture_output_restores_streams_and_clears():
    """Capture output restores streams and clears."""
    capture = CaptureOutput()
    old_out, old_err = sys.stdout, sys.stderr
    with capture:
        print("hello")
        print("oops", file=sys.stderr)
    assert sys.stdout is old_out
    assert sys.stderr is old_err
    assert capture.get_output() == ("hello\n", "oops\n")
    assert capture.get_output() == ("", "")


def test_interactive_console_push_reports_more_and_output():
    """Interactive console push reports more and output."""
    interp = InteractiveConsole({"n": 3})
    more, (out, err) = interp.push("n * 2")
    assert (more, out, err) == (False, "6\n", "")
    more, _ = interp.push("if n:")
    assert more is True
    more, (out, _) = interp.push("    print('yes')")
    assert more is True
    more, (out, _) = interp.push("")
    assert (more, out) == (False, "yes\n")


def test_interactive_console_default_locals():
    """Interactive console default locals."""
    interp = InteractiveConsole()
    assert interp.locals == {}


def test_format_command_html_first_line_and_continuations():
    """Format command html first line and continuations."""
    entry = ConsoleEntry(command=">>> for i in x:\n..:     pass")
    html = format_command_html(entry)
    assert "#2196F3" in html
    assert "&gt;&gt;&gt;" not in html
    assert html.count("..: ") == 1
    assert "<span>for i in x:</span>" in html
    assert "<span>    pass</span>" in html
    assert "<br>" in html


def test_format_command_html_continuation_prompt():
    """Format command html continuation prompt."""
    html = format_command_html(ConsoleEntry(command="x", is_continuation=True))
    assert "#6c757d" in html
    assert "#2196F3" not in html


def test_format_output_html_empty():
    """Format output html empty."""
    assert format_output_html(ConsoleEntry(command="x")) == "</div>"


def test_format_output_html_escapes_and_styles():
    """Format output html escapes and styles."""
    ok = format_output_html(ConsoleEntry(command="x", output="<a & b>\nz"))
    assert "&lt;a&nbsp;&amp;&nbsp;b&gt;<br>z" in ok
    assert "#2196F3" in ok
    assert "color: #ff3860;" not in ok
    err = format_output_html(ConsoleEntry(command="x", output="bad", is_error=True))
    assert "color: #ff3860;" in err
