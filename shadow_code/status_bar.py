"""Session state and status bar for shadow-code CLI.

Provides a persistent bottom toolbar during input (via prompt_toolkit)
and status rendering during streaming (via Rich).
"""

from dataclasses import dataclass


@dataclass
class SessionState:
    """Mutable session state shared between REPL and streaming."""

    model_name: str = ""
    tokens_used: int = 0
    tokens_total: int = 131_072
    effort: str = "mid"  # low | mid | high
    connected: bool = True
    streaming: bool = False
    turn: int = 0
    max_turns: int = 20
    session_id: int | None = None
    errors: int = 0

    def token_pct(self) -> float:
        if self.tokens_total == 0:
            return 0.0
        return self.tokens_used / self.tokens_total * 100

    def format_tokens(self) -> str:
        return f"{self.tokens_used // 1000}K/{self.tokens_total // 1000}K"


def make_toolbar_text(state: SessionState) -> str:
    """Generate plain-text toolbar string for prompt_toolkit bottom_toolbar."""
    parts = [
        state.model_name,
        state.format_tokens(),
    ]

    if state.turn > 0:
        parts.append(f"turn {state.turn}/{state.max_turns}")

    parts.append("Ctrl+D exit | /help")

    return " │ ".join(parts)


try:
    from prompt_toolkit.formatted_text import HTML

    def make_toolbar_html(state: SessionState) -> HTML:
        """Generate styled HTML toolbar for prompt_toolkit bottom_toolbar."""
        pct = state.token_pct()

        if pct < 50:
            token_color = "ansigreen"
        elif pct < 75:
            token_color = "ansiyellow"
        else:
            token_color = "ansired"

        return HTML(
            f" <b>{state.model_name}</b>"
            f" │ <style fg='{token_color}'>{state.format_tokens()}</style>"
            f" │ <i>Ctrl+D exit │ /help</i>"
        )

except ImportError:
    pass
