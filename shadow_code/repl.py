"""prompt_toolkit REPL for shadow-code.

Professional input experience with:
  - Visual separator between output and input
  - Styled prompt symbol (▸) in brand color
  - Persistent file history (~/.shadow-code/prompt_history)
  - Bottom toolbar showing model, tokens, shortcuts
  - Alt+Enter for multiline input
  - Ctrl+D/Ctrl+X to exit
  - Tab-completion for slash commands with styled menu
  - History search with Ctrl+R

Falls back to built-in input() if prompt_toolkit is not installed.
"""

import shutil
from pathlib import Path

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import WordCompleter
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.styles import Style as PTStyle

    _HAS_PROMPT_TOOLKIT = True
except ImportError:
    _HAS_PROMPT_TOOLKIT = False


# Slash commands available for tab completion
_SLASH_COMMANDS = [
    "/help",
    "/clear",
    "/exit",
    "/tokens",
    "/save",
    "/load",
    "/list",
    "/info",
    "/skills",
    "/compact",
    "/version",
    "/history",
    "/cd",
]

# ANSI colors
_BRAND = "\033[38;5;173m"  # #d77757 orange
_DIM = "\033[38;5;240m"  # dark gray
_RESET = "\033[0m"
_BOLD = "\033[1m"

# Symbols
_PROMPT_SYMBOL = "\u25b8"  # ▸
_LINE = "\u2500"  # ─

# prompt_toolkit color scheme
_PT_STYLE = None
if _HAS_PROMPT_TOOLKIT:
    _PT_STYLE = PTStyle.from_dict(
        {
            "completion-menu.completion": "bg:#2d2d2d #e0e0e0",
            "completion-menu.completion.current": "bg:#d77757 #ffffff bold",
            "completion-menu.meta.completion": "#888888",
            "completion-menu.meta.completion.current": "#ffffff",
            "scrollbar.background": "bg:#333333",
            "scrollbar.button": "bg:#666666",
            "bottom-toolbar": "bg:#1a1a1a #888888",
            "bottom-toolbar.text": "#888888",
        }
    )


def print_separator():
    """Print a visual separator line between output and input."""
    cols = shutil.get_terminal_size().columns
    label = " shadow "
    bar_left = _LINE * 2
    bar_right = _LINE * max(0, cols - len(bar_left) - len(label) - 1)
    print(f"{_DIM}{bar_left}{_BRAND}{_BOLD}{label}{_RESET}{_DIM}{bar_right}{_RESET}")


def create_prompt_session(state=None):
    """Create a prompt_toolkit PromptSession with styled prompt and toolbar.

    Args:
        state: Optional SessionState for bottom toolbar. If None, no toolbar.

    Returns:
        A PromptSession if prompt_toolkit is available, or None.
    """
    if not _HAS_PROMPT_TOOLKIT:
        return None

    history_path = Path("~/.shadow-code/prompt_history").expanduser()
    history_path.parent.mkdir(parents=True, exist_ok=True)

    bindings = KeyBindings()

    @bindings.add("escape", "enter")
    def _multiline(event):
        """Alt+Enter inserts a newline (multiline input)."""
        event.current_buffer.insert_text("\n")

    @bindings.add("c-d")
    def _exit(event):
        """Ctrl+D exits the REPL."""
        event.app.exit(result=None)

    @bindings.add("c-x")
    def _exit_cx(event):
        """Ctrl+X exits the REPL."""
        event.app.exit(result=None)

    @bindings.add("c-l")
    def _clear_screen(event):
        """Ctrl+L clears the screen."""
        event.app.renderer.clear()

    @bindings.add("c-u")
    def _clear_line(event):
        """Ctrl+U clears the current input line."""
        event.current_buffer.reset()

    completer = WordCompleter(_SLASH_COMMANDS, sentence=True)

    # Bottom toolbar
    toolbar = None
    if state is not None:

        def toolbar():
            from .status_bar import make_toolbar_html

            return make_toolbar_html(state)

    return PromptSession(
        history=FileHistory(str(history_path)),
        key_bindings=bindings,
        completer=completer,
        multiline=False,
        enable_history_search=True,
        style=_PT_STYLE,
        bottom_toolbar=toolbar,
        prompt_continuation="   ",
    )


def get_input(session, model_name: str = "") -> str | None:
    """Get user input using the prompt session.

    Returns:
        The user's input string (stripped), or None on EOF/Ctrl+D.
        Returns empty string on KeyboardInterrupt (caller should skip).
    """
    if session is not None and _HAS_PROMPT_TOOLKIT:
        return _get_input_prompt_toolkit(session)
    return _get_input_fallback()


def _get_input_prompt_toolkit(session) -> str | None:
    """Get input with styled prompt."""
    try:
        print_separator()
        prompt_str = f"{_BRAND}{_PROMPT_SYMBOL}{_RESET} "
        text = session.prompt(prompt_str)
        if text is None:
            return None
        return str(text.strip())
    except EOFError:
        return None
    except KeyboardInterrupt:
        return ""


def _get_input_fallback() -> str | None:
    """Fallback input with separator."""
    try:
        print_separator()
        text = input(f"{_BRAND}{_PROMPT_SYMBOL}{_RESET} ")
        return text.strip()
    except EOFError:
        return None
    except KeyboardInterrupt:
        print()
        return ""
