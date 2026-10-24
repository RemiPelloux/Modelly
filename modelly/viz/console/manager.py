"""Console state for the command console: history entries and code execution."""

from collections.abc import Callable
from dataclasses import dataclass

from modelly.viz.console.interpreter import InteractiveConsole
from modelly.viz.utils import force_update

_TIPS_TEXT = "Available Console Commands:\n1. Press Enter to execute a command\n2. Type 'cls' to clear the console screen (it doesn't delete past variables and functions)\n3. Type 'history' to view previous commands\n4. Press Enter on an empty line to complete a multiline block\n5. Use proper indentation for multiline blocks\n6. The console will show '..: ' for continuation lines"
_HIDDEN_HISTORY_COMMANDS = ("[history]", "[tips]", "")


@dataclass
class ConsoleEntry:
    """A class to store command console entries.

    Attributes:
        command (str): The command entered
        output (str): The output of the command
        is_error (bool): Whether the entry represents an error
        is_continuation (bool): Whether the entry is a continuation of previous command
    """

    command: str
    output: str = ""
    is_error: bool = False
    is_continuation: bool = False

    def __repr__(self):
        """Return a string representation of the ConsoleEntry."""
        return f"ConsoleEntry({self.command}, {self.output}, {self.is_error}, {self.is_continuation})"


class ConsoleManager:
    """A console manager for executing Python code interactively.

    This class provides functionality to execute Python code in an interactive console environment,
    maintain command history, and handle multi-line code blocks.

    Attributes:
        locals_dict (dict): Dictionary containing local variables available to the console
        console (InteractiveConsole): Python's interactive console instance
        buffer (list): Buffer for storing multi-line code blocks
        history (list[ConsoleEntry]): List of console entries containing commands and their outputs
    Special Commands:
        1. `history` : Shows the command history
        2. `cls` : Clears the console screen
        3. `tips` : Shows available console commands and usage tips
    Example:
        >>> console = ConsoleManager(model=my_model)
        >>> console.execute_code("print('hello world')", set_input_callback)
    """

    def __init__(self, model=None, additional_imports=None):
        """Initialize the console manager with the provided model and imports."""
        # Create locals dictionary with model and imports
        locals_dict = {}
        if model is not None:
            locals_dict["model"] = model
        if additional_imports:
            locals_dict.update(additional_imports)

        self.locals_dict = locals_dict
        self.console = InteractiveConsole(locals_dict)
        self.buffer = []
        self.history: list[ConsoleEntry] = []
        self.history_index = -1
        self.current_input = ""

    def execute_code(
        self, code_line: str, set_input_text: Callable[[str], None]
    ) -> None:
        """Execute the provided code line and update the console history."""
        # Custom Commands: history, clear and tips
        if code_line == "history":
            self._show_history()
        elif code_line == "cls":
            self.clear_console()
        elif code_line == "tips":
            self._append_entry("[tips]", _TIPS_TEXT)
        elif not code_line.strip():
            self._handle_empty_line()
        else:
            self._run_line(code_line)
        set_input_text("")

    def _append_entry(self, command: str, output: str) -> None:
        """Append a completed, non-error entry to the history."""
        self.history.append(
            ConsoleEntry(
                command=command,
                output=output,
                is_error=False,
                is_continuation=False,
            )
        )

    def _show_history(self) -> None:
        """Append an entry listing the previous commands and their outputs."""
        # Get the current history except the custom commands
        cur_his = [
            (
                f"Command: {entry.command}, \nOutput: {entry.output if entry.output else None}\n"
            )
            for entry in self.history
            if entry.command not in _HIDDEN_HISTORY_COMMANDS
        ]
        self._append_entry("[history]", "\n".join(cur_his) if cur_his else "No history")

    def _drop_continuations(self) -> None:
        """Remove the redundant continuation entries of the buffered block."""
        for _ in range(len(self.buffer) - 1):
            self.history.pop()

    def _complete_block(self, full_code: str, output: str, error: str) -> None:
        """Turn the last history entry into the completed multi-line block."""
        if self.history:
            self.history[-1].command = full_code
            self.history[-1].output = error if error else output
            self.history[-1].is_error = bool(error)
            self.history[-1].is_continuation = False
        self.buffer = []

    def _handle_empty_line(self) -> None:
        """Complete the buffered block, or add a blank entry when nothing is buffered."""
        if not self.buffer:
            # Empty line with no buffer - just add a blank entry
            self.history.append(ConsoleEntry(command=""))
            return
        full_code = "\n".join(self.buffer)
        _more, (output, error) = self.console.push("")
        self._drop_continuations()
        self._complete_block(full_code, output, error)

    def _buffer_line(self, code_line: str) -> None:
        """Buffer the start or continuation of a multi-line block."""
        self.buffer.append(code_line)
        self.history.append(
            ConsoleEntry(
                command=code_line,
                output="",  # Don't show partial output for incomplete blocks
                is_error=False,
                is_continuation=True,
            )
        )

    def _run_line(self, code_line: str) -> None:
        """Execute one line, buffering it when it opens or continues a block."""
        more, (output, error) = self.console.push(code_line)

        # Force update to display any changes to the model
        force_update()

        if more:
            self._buffer_line(code_line)
        elif not self.buffer:
            # Normal single-line command
            self.history.append(
                ConsoleEntry(
                    command=code_line,
                    output=error if error else output,
                    is_error=bool(error),
                    is_continuation=False,
                )
            )
        else:
            self._drop_continuations()
            self.buffer.append(code_line)
            self._complete_block("\n".join(self.buffer), output, error)

    def clear_console(self) -> None:
        """Clear the console history and reset the console state."""
        self.history.clear()
        self.buffer.clear()
        self.history_index = -1
        self.current_input = ""
        # Reset the console while maintaining the locals dictionary
        self.console = InteractiveConsole(self.locals_dict)

    def get_entries(self) -> list[ConsoleEntry]:
        """Get the list of console entries."""
        return self.history

    def prev_command(
        self, current_text: str, set_input_text: Callable[[str], None]
    ) -> None:
        """Navigate to previous command in history."""
        if not self.history:
            return

        # Save the current input
        if self.history_index == -1:
            self.current_input = current_text

        # Move up in history
        if self.history_index == -1:
            self.history_index = len(self.history) - 1
        elif self.history_index > 0:
            self.history_index -= 1

        # Set text to the historical command
        if 0 <= self.history_index < len(self.history):
            set_input_text(self.history[self.history_index].command)

    def next_command(self, set_input_text: Callable[[str], None]) -> None:
        """Navigate to next command in history."""
        if self.history_index == -1:
            return  # Not in history navigation mode

        # Move down in history
        self.history_index += 1

        # If we've moved past the end of history, restore the saved input
        if self.history_index >= len(self.history):
            self.history_index = -1
            set_input_text(self.current_input)
        else:
            set_input_text(self.history[self.history_index].command)
