# shadow_code/display.py -- Streaming buffer that hides tool call JSON from the user
#
# The model outputs tool calls as ```tool_call ... ``` markdown blocks.
# This display buffer intercepts streaming chunks and:
#   - Shows normal text immediately
#   - Hides ```tool_call JSON blocks from the user
#   - Collects the full response for parser.py to process after streaming ends
#
# IMPORTANT: ```tool_call detection is trickier than XML tags because ``` appears
# in normal code blocks too. Strategy: only buffer/hide when we see the exact
# sequence ```tool_call (backticks followed by "tool_call"). Normal code blocks
# like ```python or ```json are passed through to the user.

import sys

# The opening marker: three backticks followed by "tool_call"
TAG_START = "```tool_call"
# The closing marker: three backticks on their own line (after tool_call block)
TAG_END = "```"


class StreamDisplay:
    """Streaming display buffer that hides tool_call blocks from terminal output.

    Usage:
        display = StreamDisplay()
        display.reset()
        for chunk in stream:
            display.feed(chunk)
        display.flush()
        full_text = display.get_full_response()
    """

    def __init__(self):
        self.buffer = ""
        self.buffering = False  # True when inside a ```tool_call block
        self.full_response = ""  # Accumulates ALL chunks (including hidden ones)

    def reset(self):
        """Reset state for a new streaming response."""
        self.buffer = ""
        self.buffering = False
        self.full_response = ""

    def feed(self, chunk: str):
        """Process a streaming chunk. Shows text to user, hides tool_call blocks."""
        self.full_response += chunk

        if self.buffering:
            # We are inside a ```tool_call block -- buffer everything, don't show
            self.buffer += chunk
            # Look for the closing ``` that ends the tool_call block.
            # The closing ``` must appear after the opening line.
            # We skip the opening ```tool_call line itself when searching for the end.
            # Find first newline after TAG_START to skip past the opening line.
            first_newline = self.buffer.find("\n")
            if first_newline == -1:
                # Haven't even finished the opening line yet
                return
            rest = self.buffer[first_newline + 1 :]
            # Look for closing ``` -- it will be on its own line (possibly with whitespace)
            close_pos = self._find_closing_backticks(rest)
            if close_pos is not None:
                # Found the closing ```. Everything after closing ``` + newline is shown.
                after_close = rest[close_pos:]
                # The closing ``` may be followed by a newline and more text
                end_of_close = after_close.find("\n")
                if end_of_close != -1:
                    remaining = after_close[end_of_close + 1 :]
                    if remaining:
                        sys.stdout.write(remaining)
                        sys.stdout.flush()
                else:
                    # closing ``` is at the very end, no trailing text
                    pass
                self.buffering = False
                self.buffer = ""
            return

        # Not currently buffering -- look for ```tool_call in the combined text
        combined = self.buffer + chunk
        idx = combined.find(TAG_START)

        if idx != -1:
            # Found ```tool_call -- show everything before it, start buffering
            before = combined[:idx]
            if before:
                sys.stdout.write(before)
                sys.stdout.flush()
            self.buffering = True
            self.buffer = combined[idx:]
            return

        # Check for partial match at the end of combined (TAG_START split across chunks)
        # We need to hold back characters that could be the start of ```tool_call
        safe, held = self._split_partial(combined)
        if safe:
            sys.stdout.write(safe)
            sys.stdout.flush()
        self.buffer = held

    def _find_closing_backticks(self, text: str) -> int | None:
        """Find closing ``` in text that ends a tool_call block.

        The closing ``` must be at the start of a line (possibly with leading whitespace).
        Returns the position of the ``` in text, or None if not found.
        """
        pos = 0
        while pos < len(text):
            idx = text.find("```", pos)
            if idx == -1:
                return None
            # Check that this ``` is at the start of a line (or start of text)
            if idx == 0 or text[idx - 1] == "\n":
                # Make sure this isn't another opening like ```python (just closing ```)
                after = text[idx + 3 :]
                # Closing ``` is followed by nothing, whitespace, or newline
                if not after or after[0] in ("\n", "\r", " ", "\t"):
                    return idx
                # If followed by a letter, it's a new code block opening, not our close
                # Skip past it
                pos = idx + 3
            else:
                pos = idx + 3
        return None

    def _split_partial(self, text: str) -> tuple[str, str]:
        """Split text into safe-to-print and held-back portions.

        We hold back the end of text if it could be the beginning of TAG_START.
        For example, if text ends with "``" that could be the start of "```tool_call".
        """
        # Check progressively longer suffixes of text against prefixes of TAG_START
        max_check = min(len(TAG_START), len(text))
        for i in range(max_check, 0, -1):
            if TAG_START.startswith(text[-i:]):
                return text[:-i], text[-i:]
        return text, ""

    def flush(self):
        """Flush any remaining buffer to the terminal.

        Called at the end of streaming. If we're still buffering (model produced
        an unclosed ```tool_call block), we flush it so the parser can still
        extract it from full_response.
        """
        if self.buffer and not self.buffering:
            # Not inside a tool call block -- safe to print remaining buffer
            sys.stdout.write(self.buffer)
            sys.stdout.flush()
        # If buffering is True, we swallow the incomplete tool call block
        # (the parser will handle it from full_response)
        self.buffer = ""

    def get_full_response(self) -> str:
        """Return the complete response text (including hidden tool_call blocks)."""
        return str(self.full_response)
