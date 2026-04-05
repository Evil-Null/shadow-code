# shadow_code/ui.py -- Claude Code style UI rendering
#
# Minimalist design: no heavy borders, soft colors, clean layout.
# Adapted from Claude Code's dark theme palette (src/utils/theme.ts).

try:
    from rich.console import Group
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.rule import Rule
    from rich.spinner import Spinner
    from rich.table import Table
    from rich.text import Text
    from rich.box import SIMPLE, ROUNDED, MINIMAL
    from rich import box

    HAS_RICH = True
except ImportError:
    HAS_RICH = False

from .config import MODEL_NAME

# Claude Code inspired colors (soft, not screaming)
_CLAUDE_ORANGE = "#d77757"    # Claude's brand -- for assistant identity
_SUBTLE = "#888888"           # dim text, borders, secondary info
_TEXT = "#e0e0e0"             # primary text
_SUCCESS = "#5faf5f"          # soft green
_ERROR = "#d75f5f"            # soft red
_WARNING = "#d7af5f"          # soft amber
_TOOL = "#5f87d7"             # soft blue -- for tool calls
_ACCENT = "#af87d7"           # soft purple -- for highlights


class UIRenderer:
    """Claude Code-style minimalist UI rendering."""

    def render_welcome(self) -> "Panel":
        content = Text()
        content.append("\n  shadow", style=f"bold {_CLAUDE_ORANGE}")
        content.append("-code", style=f"{_SUBTLE}")
        content.append(f"  v0.1.0\n", style=f"dim")
        content.append(f"  {MODEL_NAME}\n", style=f"dim")
        content.append("  /help for commands\n", style=f"dim italic")
        return Panel(content, border_style=_SUBTLE, box=ROUNDED, padding=(0, 0))

    def render_thinking(self, model: str = "") -> "Panel":
        spinner = Spinner("dots", text=Text(" thinking...", style=f"{_SUBTLE}"))
        return Panel(spinner, border_style=_SUBTLE, box=MINIMAL, padding=(0, 1))

    def render_streaming(self, text: str) -> "Panel":
        body = Markdown(text) if text.strip() else Text("...", style=f"{_SUBTLE}")
        return Panel(body, border_style=_SUBTLE, box=MINIMAL, padding=(0, 1))

    def render_response(self, text: str, tokens: int = 0) -> "Panel":
        subtitle = f"[{_SUBTLE}]{tokens:,} tokens[/{_SUBTLE}]" if tokens else ""
        return Panel(
            Markdown(text),
            border_style=_SUBTLE,
            box=MINIMAL,
            subtitle=subtitle,
            padding=(0, 1),
        )

    def render_tool_call(self, tool: str, desc: str) -> "Text":
        """Inline tool indicator -- no heavy panel, just a subtle line."""
        text = Text()
        text.append("  > ", style=f"{_SUBTLE}")
        text.append(tool, style=f"bold {_TOOL}")
        text.append(f" {desc}", style=f"{_SUBTLE}")
        return text

    def render_tool_result(self, tool: str, output: str, success: bool) -> "Panel":
        color = _SUCCESS if success else _ERROR
        preview = output[:500] + ("..." if len(output) > 500 else "")
        title = f"[{color}]{tool}[/{color}]"
        return Panel(
            Text(preview, style=f"dim"),
            border_style=color,
            box=SIMPLE,
            title=title,
            padding=(0, 1),
        )

    def render_error(self, message: str) -> "Text":
        text = Text()
        text.append("  error: ", style=f"bold {_ERROR}")
        text.append(message, style=f"{_ERROR}")
        return text

    def render_context_status(self, used: int, total: int) -> "Text":
        pct = (used / total) * 100 if total else 0
        if pct < 50:
            color = _SUCCESS
        elif pct < 75:
            color = _WARNING
        else:
            color = _ERROR

        bar_w = 20
        filled = int(bar_w * pct / 100)
        bar = "=" * filled + "-" * (bar_w - filled)

        text = Text()
        text.append(f"  [{bar}] ", style=f"{color}")
        text.append(f"{used // 1000}K/{total // 1000}K ", style=f"bold {color}")
        text.append(f"({pct:.0f}%)", style=f"{_SUBTLE}")
        return text

    def render_help(self, commands: list[tuple[str, str]]) -> "Table":
        table = Table(
            show_header=False,
            box=None,
            padding=(0, 2),
            show_edge=False,
        )
        table.add_column(style=f"{_TOOL}", no_wrap=True, width=20)
        table.add_column(style=f"{_SUBTLE}")
        for cmd, desc in commands:
            table.add_row(cmd, desc)
        return table
