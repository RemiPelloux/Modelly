"""HTML formatting of command console entries."""


def format_command_html(entry):
    """Format the command part of a console entry as HTML."""
    prompt = "..: " if entry.is_continuation else ">>> "
    prompt_color = "#6c757d" if entry.is_continuation else "#2196F3"

    # Handle multi-line commands with proper formatting
    command_lines = entry.command.split("\n")
    formatted_lines = []

    for i, line in enumerate(command_lines):
        line_prompt = prompt if i == 0 else "..: "
        line_prompt_color = prompt_color if i == 0 else "#6c757d"
        formatted_lines.append(
            f'<span style="color: {line_prompt_color};">{line_prompt}</span><span>{line.removeprefix(">>> ").removeprefix("..: ")}</span>'
        )

    command_html = "<br>".join(formatted_lines)

    return f"""
    <div style="margin: 0px 0 0 0;">
        <div style="background-color: #f5f5f5; padding: 6px 8px; border-radius: 4px; font-family: 'Consolas', monospace; font-size: 0.9em;">
        {command_html}
        </div>
    """


def format_output_html(entry):
    """Format the output part of a console entry as HTML."""
    if not entry.output:
        return "</div>"

    escaped_output = (
        entry.output.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace(" ", "&nbsp;")
        .replace("\n", "<br>")
    )

    return f"""
    <div style="background-color: #ffffff; padding: 6px 8px; border-left: 3px solid {"#ff3860" if entry.is_error else "#2196F3"}; margin-top: 2px; font-family: 'Consolas', monospace; font-size: 0.9em; {"color: #ff3860;" if entry.is_error else ""}">
    {escaped_output}
    </div>
    </div>
    """
