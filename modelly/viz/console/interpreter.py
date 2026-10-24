"""An interactive Python interpreter whose stdout and stderr are captured."""

import code
import io
import sys


class CaptureOutput:
    """A context manager for capturing stdout and stderr output.

    This class provides a way to capture output that would normally be printed
    to stdout and stderr during the execution of code within its context.
    """

    def __init__(self):
        """Initialize the CaptureOutput context manager with empty string buffers."""
        self.stdout = io.StringIO()
        self.stderr = io.StringIO()
        self._old_stdout = None
        self._old_stderr = None

    def __enter__(self):
        """Set up the context manager by redirecting stdout and stderr.

        Returns:
            self: The context manager instance
        """
        self._old_stdout = sys.stdout
        self._old_stderr = sys.stderr
        sys.stdout = self.stdout
        sys.stderr = self.stderr
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Restore the original stdout and stderr when exiting the context."""
        sys.stdout = self._old_stdout
        sys.stderr = self._old_stderr

    def get_output(self):
        """Retrieve and clear the captured output.

        Returns:
            tuple: A pair of strings (stdout_output, stderr_output)
        """
        output = self.stdout.getvalue()
        error = self.stderr.getvalue()
        self.stdout.seek(0)
        self.stdout.truncate(0)
        self.stderr.seek(0)
        self.stderr.truncate(0)
        return output, error


class InteractiveConsole(code.InteractiveConsole):
    """A custom interactive Python console with output capturing capabilities.

    This class extends code.InteractiveConsole to provide output capturing functionality
    when executing Python code interactively.

    Args:
        locals_dict (dict, optional): Dictionary of local variables. Defaults to None.
    """

    def __init__(self, locals_dict=None):
        """Initialize the InteractiveConsole with the provided locals dictionary."""
        super().__init__(locals=locals_dict or {})
        self.capturer = CaptureOutput()

    def push(self, line):
        """Push a line to the command interpreter and execute it.

        This method captures the output of the executed command and returns both
        the 'more' flag and the captured output.

        Args:
            line (str): The line of code to be executed.

        Returns:
            tuple: A tuple containing:
                - more (bool): Flag indicating if more input is needed
                - str: The captured output from executing the command
        """
        with self.capturer:
            more = super().push(line)
        return more, self.capturer.get_output()
