"""prompt_toolkit REPL for shadow-code.

Claude Code style input with:
  - Top border line (╭───╮) with model info
  - Text input area (no side borders -- clean look)
  - Bottom border line (╰───╯) after input
  - Bottom toolbar with status
  - Alt+Enter for multiline, Ctrl+D/Ctrl+X to exit
  - Tab-completion, history search

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


# Slash commands for tab completion
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

# Colors
_BORDER = "\033[38;5;240m"  # dark gray
_BRAND = "\033[38;5;173m"  # orange
_DIM = "\033[2m"
_RESET = "\033[0m"

# Box drawing
_TL = "\u256d"  # ╭
_TR = "\u256e"  # ╮
_BL = "\u2570"  # ╰
_BR = "\u256f"  # ╯
_H = "\u2500"  # ─

# prompt_toolkit style
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


def _top_border(model: str = "", width: int = 0) -> str:
    """Build top border: ╭─── model ───╮"""
    cols = width or shutil.get_terminal_size().columns
    inner = cols - 2  # minus ╭ and ╮

    if model:
        label = f" {model} "
        bar_right = _H * max(0, inner - len(label))
        return f"{_BORDER}{_TL}{_BRAND}{label}{_BORDER}{bar_right}{_TR}{_RESET}"

    return f"{_BORDER}{_TL}{_H * inner}{_TR}{_RESET}"


def _bottom_border(hint: str = "", width: int = 0) -> str:
    """Build bottom border: ╰─── hint ───╯"""
    cols = width or shutil.get_terminal_size().columns
    inner = cols - 2

    if hint:
        bar_left = _H * max(0, inner - len(hint) - 1)
        return f"{_BORDER}{_BL}{bar_left}{_DIM}{hint} {_RESET}{_BORDER}{_BR}{_RESET}"

    return f"{_BORDER}{_BL}{_H * inner}{_BR}{_RESET}"


def create_prompt_session(state=None):
    """Create a PromptSession with Claude Code style input."""
    if not _HAS_PROMPT_TOOLKIT:
        return None

    history_path = Path("~/.shadow-code/prompt_history").expanduser()
    history_path.parent.mkdir(parents=True, exist_ok=True)

    bindings = KeyBindings()

    @bindings.add("escape", "enter")
    def _multiline(event):
        event.current_buffer.insert_text("\n")

    @bindings.add("c-d")
    def _exit(event):
        event.app.exit(result=None)

    @bindings.add("c-x")
    def _exit_cx(event):
        event.app.exit(result=None)

    @bindings.add("c-l")
    def _clear_screen(event):
        event.app.renderer.clear()

    @bindings.add("c-u")
    def _clear_line(event):
        event.current_buffer.reset()

    completer = WordCompleter(_SLASH_COMMANDS, sentence=True)

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
        prompt_continuation="  ",
    )


def get_input(session, model_name: str = "") -> str | None:
    """Get input. Returns stripped string, None on EOF, empty on interrupt."""
    if session is not None and _HAS_PROMPT_TOOLKIT:
        return _get_input_prompt_toolkit(session, model_name)
    return _get_input_fallback(model_name)


def _get_input_prompt_toolkit(session, model_name: str = "") -> str | None:
    """Claude Code style: top border → input → bottom border."""
    try:
        # ╭─── model ───╮
        print(_top_border(model_name))

        # Input (indented, no side borders)
        text = session.prompt("  ")

        # ╰─── hints ───╯
        print(_bottom_border("Ctrl+D exit │ /help"))

        if text is None:
            return None
        return str(text.strip())
    except EOFError:
        print()  # close the box visually
        return None
    except KeyboardInterrupt:
        print()
        return ""


def _get_input_fallback(model_name: str = "") -> str | None:
    """Fallback with same visual style."""
    try:
        print(_top_border(model_name))
        text = input("  ")
        print(_bottom_border("Ctrl+D exit │ /help"))
        return text.strip()
    except EOFError:
        print()
        return None
    except KeyboardInterrupt:
        print()
        return ""
