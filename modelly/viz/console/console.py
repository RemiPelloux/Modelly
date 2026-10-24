"""A command console interface for interactive Python code execution in the browser.

This module provides a set of classes and functions to create an interactive Python console
that can be embedded in a web browser. It supports command history, multi-line code blocks,
and special commands for console management.

Notes:
    - The console supports multi-line code blocks with proper indentation
    - Output is captured and displayed with appropriate formatting
    - Error messages are displayed in red with distinct styling
    - The console maintains a history of commands and their outputs
"""

import solara
from solara.components.input import use_change

from modelly.viz.console.html import format_command_html, format_output_html
from modelly.viz.console.interpreter import CaptureOutput, InteractiveConsole
from modelly.viz.console.manager import ConsoleEntry, ConsoleManager

__all__ = [
    "CaptureOutput",
    "CommandConsole",
    "ConsoleEntry",
    "ConsoleInput",
    "ConsoleManager",
    "InteractiveConsole",
    "format_command_html",
    "format_output_html",
]

_INPUT_FIELD_PROPS = {
    "flat": True,
    "hide_details": True,
    "dense": True,
    "height": "auto",
    "background_color": "transparent",
    "style_": "font-family: monospace; border: none; box-shadow: none; padding: 0; margin: 0; background-color: transparent; color: #000; flex-grow: 1;",
    "placeholder": "",
    "solo": False,
    "filled": False,
    "outlined": False,
    "id": "console-input",
    "attributes": {
        "spellcheck": "false",
        "autocomplete": "off",
    },
}
_CONSOLE_STYLE = {
    "height": "300px",
    "overflow-y": "auto",
    "gap": "0px",
    "box-shadow": "inset 0 0 10px rgba(0,0,0,0.1)",
    "border": "3px solid #e0e0e0",
    "border-radius": "6px",
    "padding": "8px",
}
_INPUT_ROW_STYLE = {"align-items": "center", "margin": "0", "width": "94.5%"}


@solara.component
def ConsoleInput(on_submit, on_up, on_down):
    """A solara component for handling console input."""
    input_text, set_input_text = solara.use_state("")

    def handle_submit(*ignore_args):
        on_submit(input_text, set_input_text)

    def handle_up(*ignore_args):
        on_up(input_text, set_input_text)

    def handle_down(*ignore_args):
        on_down(set_input_text)

    input_elem = solara.v.TextField(
        v_model=input_text, on_v_model=set_input_text, **_INPUT_FIELD_PROPS
    )

    # Bind key events with the input element
    use_change(input_elem, handle_submit, update_events=["keypress.enter"])
    use_change(input_elem, handle_up, update_events=["keyup.38"])  # 38 -> Up arrow
    use_change(
        input_elem, handle_down, update_events=["keydown.40"]
    )  # 40 -> Down arrow

    return input_elem


def _render_entries(console_entries) -> None:
    """Render the history entries with auto-scrolling."""
    with solara.v.ScrollYTransition(group=True):
        for entry in console_entries:
            with solara.Div():
                command_html = format_command_html(entry)
                output_html = format_output_html(entry)
                solara.Markdown(command_html + output_html)


def _make_console_handlers(console_ref, refresh, set_refresh):
    """Build the submit, history-up and history-down callbacks of the console input."""

    def handle_code_execution(code, set_input_text):
        console_ref.current.execute_code(code, set_input_text)
        set_refresh(refresh + 1)

    def handle_up(current_text, set_input_text):
        console_ref.current.prev_command(current_text, set_input_text)
        set_refresh(refresh + 1)

    def handle_down(set_input_text):
        console_ref.current.next_command(set_input_text)
        set_refresh(refresh + 1)

    return handle_code_execution, handle_up, handle_down


@solara.component
def CommandConsole(model=None, additional_imports=None):
    """A solara component for executing Python code interactively in the browser."""
    console_ref = solara.use_ref(None)
    if console_ref.current is None:
        console_ref.current = ConsoleManager(
            model=model, additional_imports=additional_imports
        )

    # State to trigger re-renders
    refresh, set_refresh = solara.use_state(0)
    handle_code_execution, handle_up, handle_down = _make_console_handlers(
        console_ref, refresh, set_refresh
    )

    with solara.Column(style=_CONSOLE_STYLE):
        _render_entries(console_ref.current.get_entries())
        # Input row that adapts to content above it
        with solara.Row(style=_INPUT_ROW_STYLE):
            solara.Text(">>> ", style={"color": "#0066cc"})
            ConsoleInput(
                on_submit=handle_code_execution, on_up=handle_up, on_down=handle_down
            )

    solara.Markdown(
        "*Type 'tips' for usage instructions.*",
        style="font-size: 0.8em; color: #666;",
    )
