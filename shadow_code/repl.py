"""prompt_toolkit REPL for shadow-code.

Provides an enhanced input experience with:
  - Persistent file history (~/.shadow-code/prompt_history)
  - Alt+Enter for multiline input (inserts newline)
  - Ctrl+D to exit
  - Tab-completion for slash commands
  - History search with Ctrl+R (enable_history_search)

Falls back to built-in input() if prompt_toolkit is not installed.

Usage:
    from .repl import create_prompt_session, get_input

    session = create_prompt_session()
    while True:
        text = get_input(session, "shadow-gemma:latest")
        if text is None:
            break  # EOF / Ctrl+D
        # process text...
"""

import os
from pathlib import Path

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.completion import WordCompleter
    from prompt_toolkit.formatted_text import HTML

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
]


def create_prompt_session():
    """Create a prompt_toolkit PromptSession with history and keybindings.

    Returns a PromptSession if prompt_toolkit is available, or None for
    the fallback path.
    """
    if not _HAS_PROMPT_TOOLKIT:
        return None

    # Ensure history directory exists
    history_path = Path("~/.shadow-code/prompt_history").expanduser()
    history_path.parent.mkdir(parents=True, exist_ok=True)

    # Key bindings
    bindings = KeyBindings()

    @bindings.add("escape", "enter")
    def _multiline(event):
        """Alt+Enter inserts a newline (multiline input)."""
        event.current_buffer.insert_text("\n")

    @bindings.add("c-d")
    def _exit(event):
        """Ctrl+D exits the REPL."""
        event.app.exit(result=None)

    # Slash command completer
    completer = WordCompleter(
        _SLASH_COMMANDS,
        sentence=True,  # complete after spaces too
    )

    return PromptSession(
        history=FileHistory(str(history_path)),
        key_bindings=bindings,
        completer=completer,
        multiline=False,
        enable_history_search=True,
    )


def get_input(session, model_name: str = "") -> str | None:
    """Get user input using the prompt session.

    Args:
        session: A PromptSession from create_prompt_session(), or None for
                 fallback mode.
        model_name: The model name to display in the prompt (unused in
                    basic mode, available for future prompt customization).

    Returns:
        The user's input string (stripped), or None on EOF/Ctrl+D.
        Returns empty string on KeyboardInterrupt (caller should skip).
    """
    if session is not None and _HAS_PROMPT_TOOLKIT:
        return _get_input_prompt_toolkit(session)
    return _get_input_fallback()


def _get_input_prompt_toolkit(session) -> str | None:
    """Get input using prompt_toolkit."""
    try:
        text = session.prompt("shadow> ")
        if text is None:
            return None  # Ctrl+D via keybinding
        return text.strip()
    except EOFError:
        return None
    except KeyboardInterrupt:
        return ""  # empty string signals "skip this input"


def _get_input_fallback() -> str | None:
    """Fallback input using built-in input()."""
    try:
        text = input("shadow> ")
        return text.strip()
    except EOFError:
        return None
    except KeyboardInterrupt:
        print()  # newline after ^C
        return ""  # empty string signals "skip this input"
