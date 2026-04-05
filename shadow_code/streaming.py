# shadow_code/streaming.py -- Rich Live streaming controller
#
# Wraps OllamaClient.chat_stream() with Rich Live display, using UIRenderer
# for panel rendering and StreamDisplay for tool_call block filtering.
#
# The key integration point: StreamDisplay.feed() normally writes visible text
# to sys.stdout. Here we redirect its output so we can capture visible text
# for Rich Live rendering instead. We do this by temporarily replacing
# sys.stdout with a StringIO buffer during feed(), then extracting what
# StreamDisplay would have printed.
#
# Rich and prompt_toolkit are optional. If Rich is not installed, the
# stream_response_plain() fallback uses the existing StreamDisplay behavior
# (direct stdout writes, no panels).

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
    """Controls streaming LLM responses with Rich Live display.

    Integrates:
    - OllamaClient for streaming chat completion
    - UIRenderer for panel rendering (thinking, streaming, response)
    - StreamDisplay for filtering tool_call blocks from visible output
    - Rich Live for real-time terminal updates

    If Rich is not installed, falls back to plain-text streaming via
    StreamDisplay's direct stdout writes.
    """

    def __init__(self, client, ui, console=None, display=None):
        """Initialize the stream controller.

        Args:
            client: OllamaClient instance for chat_stream().
            ui: UIRenderer instance for panel rendering.
            console: Rich Console instance (optional, created if None and Rich available).
            display: StreamDisplay instance (optional, created if None).
        """
        self.client = client
        self.ui = ui
        self.display = display or StreamDisplay()

        if HAS_RICH:
            self.console = console or Console()
        else:
            self.console = console

    def stream_response(self, messages: list[dict], system: str) -> tuple[str, int]:
        """Stream an LLM response with live display.

        Uses Rich Live for real-time panel updates if available, otherwise
        falls back to plain stdout streaming.

        Args:
            messages: Conversation history.
            system: System prompt string.

        Returns:
            Tuple of (full_response, eval_tokens).
            full_response includes hidden tool_call blocks.
            eval_tokens is the number of tokens generated.

        Raises:
            StreamCancelled: If the user presses Ctrl+C during streaming.
        """
        if HAS_RICH:
            return self._stream_rich(messages, system)
        else:
            return self._stream_plain(messages, system)

    def _stream_rich(self, messages: list[dict], system: str) -> tuple[str, int]:
        """Stream with Rich Live panel rendering."""
        self.display.reset()
        accumulated_visible = ""

        try:
            with Live(
                self.ui.render_thinking(),
                console=self.console,
                refresh_per_second=10,
                transient=False,  # keep final response visible on screen
            ) as live:
                for chunk in self.client.chat_stream(messages, system):
                    visible_text = self._feed_and_capture(chunk)
                    if visible_text:
                        accumulated_visible += visible_text
                        live.update(self.ui.render_streaming(accumulated_visible))

                # Capture any remaining buffered visible text
                remaining = self._flush_and_capture()
                if remaining:
                    accumulated_visible += remaining

                tokens = self.client.last_eval_tokens
                live.update(self.ui.render_response(accumulated_visible, tokens))

        except KeyboardInterrupt:
            # Capture what we have so far
            remaining = self._flush_and_capture()
            if remaining:
                accumulated_visible += remaining
            raise StreamCancelled()

        return self.display.get_full_response(), self.client.last_eval_tokens

    def _stream_plain(self, messages: list[dict], system: str) -> tuple[str, int]:
        """Fallback: stream with plain stdout (no Rich).

        Uses StreamDisplay directly -- it writes visible text to sys.stdout
        and hides tool_call blocks automatically.
        """
        self.display.reset()

        try:
            for chunk in self.client.chat_stream(messages, system):
                self.display.feed(chunk)
        except KeyboardInterrupt:
            self.display.flush()
            print()
            raise StreamCancelled()

        self.display.flush()
        print()  # newline after streaming output

        return self.display.get_full_response(), self.client.last_eval_tokens

    def _feed_and_capture(self, chunk: str) -> str:
        """Feed a chunk to StreamDisplay, capturing what it would print to stdout.

        StreamDisplay.feed() writes visible text to sys.stdout. We temporarily
        redirect stdout to a StringIO buffer to capture that output instead of
        printing it, so we can render it in a Rich panel.

        Returns:
            The visible text that StreamDisplay would have printed.
        """
        capture = io.StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = capture
            self.display.feed(chunk)
        finally:
            sys.stdout = old_stdout
        return capture.getvalue()

    def _flush_and_capture(self) -> str:
        """Flush StreamDisplay, capturing any remaining visible text.

        Returns:
            The visible text flushed from the buffer.
        """
        capture = io.StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = capture
            self.display.flush()
        finally:
            sys.stdout = old_stdout
        return capture.getvalue()
