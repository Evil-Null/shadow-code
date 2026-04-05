# shadow_code/ui.py -- Rich UI rendering for shadow-code
#
# Provides panel-based rendering for all UI elements: welcome, thinking,
# streaming, responses, tool calls, tool results, errors, context status,
# and help. All methods return Rich renderables (Panel, Text, Table) for
# composition with Rich Console or Rich Live.
#
# Rich is an optional dependency. If not installed, callers should fall back
# to plain-text output (see streaming.py for the fallback pattern).

try:
    from rich.console import Group
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.rule import Rule
    from rich.spinner import Spinner
    from rich.table import Table
    from rich.text import Text

    HAS_RICH = True
except ImportError:
    HAS_RICH = False

from .config import MODEL_NAME


class UIRenderer:
    """Renders all shadow-code UI elements as Rich Panel/Text objects.

    Every render_* method returns a Rich renderable suitable for
    Console.print() or Live.update().
    """

    def render_welcome(self) -> "Panel":
        """Welcome banner shown at startup."""
        content = Text()
        content.append("Shadow Code", style="bold cyan")
        content.append(" v0.1.0\n", style="dim")
        content.append("Local AI Coding Assistant\n", style="dim")
        content.append(f"Model: {MODEL_NAME} | ", style="dim")
        content.append("Type /help for commands", style="dim italic")
        return Panel(content, border_style="cyan", padding=(1, 2))

    def render_thinking(self, model: str = "") -> "Panel":
        """Spinner panel shown while waiting for the first token."""
        model_name = model or MODEL_NAME
        spinner = Spinner("dots", text=Text(f" {model_name} is thinking...", style="cyan"))
        return Panel(spinner, border_style="blue")

    def render_streaming(self, text: str) -> "Panel":
        """Panel with markdown-rendered text, updated during streaming."""
        body = Markdown(text) if text.strip() else Text("...")
        return Panel(
            body,
            border_style="blue",
            subtitle="[dim]streaming...[/dim]",
        )

    def render_response(self, text: str, tokens: int = 0) -> "Panel":
        """Final response panel with optional token count in subtitle."""
        subtitle = f"[dim]{tokens:,} tokens[/dim]" if tokens else ""
        return Panel(Markdown(text), border_style="blue", subtitle=subtitle)

    def render_tool_call(self, tool: str, desc: str) -> "Panel":
        """Panel showing a tool invocation (before execution)."""
        return Panel(
            Text(desc, style="dim"),
            border_style="cyan",
            title=f"[bold cyan]{tool}[/bold cyan]",
        )

    def render_tool_result(self, tool: str, output: str, success: bool) -> "Panel":
        """Panel showing tool execution result. Green if success, red if failure."""
        style = "green" if success else "red"
        preview = output[:500] + ("..." if len(output) > 500 else "")
        return Panel(
            Text(preview),
            border_style=style,
            title=f"[bold {style}]{tool}[/bold {style}]",
        )

    def render_error(self, message: str) -> "Panel":
        """Red-bordered error panel."""
        return Panel(
            Text(message, style="bold red"),
            border_style="red",
            title="[bold red]Error[/bold red]",
        )

    def render_context_status(self, used: int, total: int) -> "Text":
        """Color-coded context usage indicator.

        Green  < 50%
        Yellow < 75%
        Red    >= 75%
        """
        pct = (used / total) * 100 if total else 0
        if pct < 50:
            color = "green"
        elif pct < 75:
            color = "yellow"
        else:
            color = "red"
        text = Text()
        text.append("  Context: ", style="dim")
        text.append(f"{used // 1000}K/{total // 1000}K", style=f"bold {color}")
        text.append(f" ({pct:.0f}%)", style="dim")
        return text

    def render_help(self, commands: list[tuple[str, str]]) -> "Table":
        """Render a help table of slash commands.

        Args:
            commands: List of (command, description) tuples.
                      e.g. [("/help", "Show this help"), ("/exit", "Exit shadow-code")]
        """
        table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
        table.add_column("Command", style="green", no_wrap=True)
        table.add_column("Description")
        for cmd, desc in commands:
            table.add_row(cmd, desc)
        return table
