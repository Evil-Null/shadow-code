# shadow_code/streaming.py -- Rich Live streaming controller
#
# Handles streaming display with Rich Live panels.
# Tool call blocks are hidden by StreamDisplay, only visible text shown.
# transient=True so intermediate panels clear, tool results stay visible.

import io
import sys

from .display import StreamDisplay


class StreamCancelled(Exception):
    """Raised when the user interrupts streaming with Ctrl+C."""

    pass


try:
    from rich.console import Console
    from rich.live import Live

    HAS_RICH = True
except ImportError:
    HAS_RICH = False


class StreamController:
    """Controls streaming LLM responses with Rich Live display."""

    def __init__(self, client, ui, console=None, display=None):
        self.client = client
        self.ui = ui
        self.display = display or StreamDisplay()
        if HAS_RICH:
            self.console = console or Console()
        else:
            self.console = console

    def stream_response(self, messages: list[dict], system: str) -> tuple[str, int]:
        """Stream response. Returns (full_response_with_tool_calls, eval_tokens)."""
        if HAS_RICH:
            return self._stream_rich(messages, system)
        else:
            return self._stream_plain(messages, system)

    def _stream_rich(self, messages: list[dict], system: str) -> tuple[str, int]:
        """Stream with Rich Live panel rendering."""
        self.display.reset()
        accumulated_visible = ""

        try:
            # transient=True: panel clears after streaming ends
            # This way tool results (printed via console.print) stay visible
            # and don't get overwritten by the next Live panel
            with Live(
                self.ui.render_thinking(),
                console=self.console,
                refresh_per_second=10,
                transient=True,
            ) as live:
                for chunk in self.client.chat_stream(messages, system):
                    visible_text = self._feed_and_capture(chunk)
                    if visible_text:
                        accumulated_visible += visible_text
                        live.update(self.ui.render_streaming(accumulated_visible))

                # Flush remaining
                remaining = self._flush_and_capture()
                if remaining:
                    accumulated_visible += remaining

        except KeyboardInterrupt:
            remaining = self._flush_and_capture()
            if remaining:
                accumulated_visible += remaining
            raise StreamCancelled() from None

        # Print final visible text OUTSIDE Live (so it stays on screen permanently)
        if accumulated_visible.strip():
            tokens = self.client.last_eval_tokens
            self.console.print(self.ui.render_response(accumulated_visible, tokens))

        return self.display.get_full_response(), self.client.last_eval_tokens

    def _stream_plain(self, messages: list[dict], system: str) -> tuple[str, int]:
        """Fallback: plain stdout streaming."""
        self.display.reset()

        try:
            for chunk in self.client.chat_stream(messages, system):
                self.display.feed(chunk)
        except KeyboardInterrupt:
            self.display.flush()
            print()
            raise StreamCancelled() from None

        self.display.flush()
        print()

        return self.display.get_full_response(), self.client.last_eval_tokens

    def _feed_and_capture(self, chunk: str) -> str:
        """Feed chunk to StreamDisplay, capture what it would print."""
        capture = io.StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = capture
            self.display.feed(chunk)
        finally:
            sys.stdout = old_stdout
        return capture.getvalue()

    def _flush_and_capture(self) -> str:
        """Flush StreamDisplay, capture remaining text."""
        capture = io.StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = capture
            self.display.flush()
        finally:
            sys.stdout = old_stdout
        return capture.getvalue()
