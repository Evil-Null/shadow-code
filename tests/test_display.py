"""Tests for display.py -- streaming buffer that hides tool_call blocks."""

import io
import sys
import unittest

from shadow_code.display import TAG_END, TAG_START, StreamDisplay


class TestStreamDisplayBasic(unittest.TestCase):
    """Basic StreamDisplay behavior."""

    def setUp(self):
        self.display = StreamDisplay()
        self.display.reset()

    def test_reset_clears_state(self):
        self.display.full_response = "leftover"
        self.display.buffer = "leftover"
        self.display.buffering = True
        self.display.reset()
        self.assertEqual(self.display.full_response, "")
        self.assertEqual(self.display.buffer, "")
        self.assertFalse(self.display.buffering)

    def test_plain_text_passes_through(self):
        captured = io.StringIO()
        old = sys.stdout
        try:
            sys.stdout = captured
            self.display.feed("Hello world")
            self.display.flush()
        finally:
            sys.stdout = old
        self.assertIn("Hello world", captured.getvalue())

    def test_full_response_accumulates(self):
        self.display.feed("Hello ")
        self.display.feed("world")
        self.assertEqual(self.display.get_full_response(), "Hello world")

    def test_tool_call_hidden_from_output(self):
        tool_block = '```tool_call\n{"tool": "bash", "params": {"command": "ls"}}\n```'
        captured = io.StringIO()
        old = sys.stdout
        try:
            sys.stdout = captured
            self.display.feed(tool_block)
            self.display.flush()
        finally:
            sys.stdout = old
        # tool_call block should NOT appear in printed output
        self.assertNotIn("tool_call", captured.getvalue())
        self.assertNotIn('"tool"', captured.getvalue())

    def test_tool_call_in_full_response(self):
        tool_block = '```tool_call\n{"tool": "bash", "params": {"command": "ls"}}\n```'
        self.display.feed(tool_block)
        # Full response should contain the tool call
        self.assertIn("tool_call", self.display.get_full_response())

    def test_text_before_tool_call_shown(self):
        captured = io.StringIO()
        old = sys.stdout
        try:
            sys.stdout = captured
            self.display.feed('Let me check.\n```tool_call\n{"tool": "bash", "params": {}}\n```')
            self.display.flush()
        finally:
            sys.stdout = old
        output = captured.getvalue()
        self.assertIn("Let me check.", output)
        self.assertNotIn('"tool"', output)

    def test_text_after_tool_call_in_full_response(self):
        self.display.feed('```tool_call\n{"tool": "bash", "params": {}}\n```\nDone!')
        self.display.flush()
        # The full response captures everything regardless of display
        full = self.display.get_full_response()
        self.assertIn("Done!", full)


class TestStreamDisplayChunked(unittest.TestCase):
    """Test with chunks split across feed() calls."""

    def setUp(self):
        self.display = StreamDisplay()
        self.display.reset()

    def test_chunked_tool_call(self):
        """Tool call split across multiple chunks should still be hidden."""
        captured = io.StringIO()
        old = sys.stdout
        try:
            sys.stdout = captured
            self.display.feed("```tool_")
            self.display.feed('call\n{"tool": "bash", ')
            self.display.feed('"params": {"command": "ls"}}\n')
            self.display.feed("```")
            self.display.flush()
        finally:
            sys.stdout = old
        self.assertNotIn('"tool"', captured.getvalue())

    def test_normal_code_block_not_hidden(self):
        """A ```python block should NOT be hidden."""
        captured = io.StringIO()
        old = sys.stdout
        try:
            sys.stdout = captured
            self.display.feed('```python\nprint("hello")\n```')
            self.display.flush()
        finally:
            sys.stdout = old
        output = captured.getvalue()
        self.assertIn("python", output)
        self.assertIn("hello", output)


class TestStreamDisplayEdgeCases(unittest.TestCase):
    """Edge cases for StreamDisplay."""

    def setUp(self):
        self.display = StreamDisplay()
        self.display.reset()

    def test_unclosed_tool_call_swallowed(self):
        """Unclosed tool_call block is swallowed on flush."""
        captured = io.StringIO()
        old = sys.stdout
        try:
            sys.stdout = captured
            self.display.feed('```tool_call\n{"tool": "bash", "params": {}}')
            # No closing ```
            self.display.flush()
        finally:
            sys.stdout = old
        self.assertNotIn("tool_call", captured.getvalue())

    def test_empty_feed(self):
        self.display.feed("")
        self.assertEqual(self.display.get_full_response(), "")

    def test_multiple_tool_calls_in_full_response(self):
        text = (
            "First.\n"
            '```tool_call\n{"tool": "bash", "params": {"command": "pwd"}}\n```\n'
            "Middle.\n"
            '```tool_call\n{"tool": "bash", "params": {"command": "ls"}}\n```\n'
            "Last."
        )
        self.display.feed(text)
        self.display.flush()
        full = self.display.get_full_response()
        # Full response contains everything
        self.assertIn("First.", full)
        self.assertIn("Middle.", full)
        self.assertIn("Last.", full)
        self.assertIn('"tool"', full)


class TestStreamDisplayConstants(unittest.TestCase):
    """Test constants are correct."""

    def test_tag_start(self):
        self.assertEqual(TAG_START, "```tool_call")

    def test_tag_end(self):
        self.assertEqual(TAG_END, "```")


class TestSplitPartial(unittest.TestCase):
    """Test the _split_partial helper."""

    def setUp(self):
        self.display = StreamDisplay()

    def test_no_partial(self):
        safe, held = self.display._split_partial("hello world")
        self.assertEqual(safe, "hello world")
        self.assertEqual(held, "")

    def test_partial_backtick(self):
        safe, held = self.display._split_partial("hello `")
        self.assertEqual(safe, "hello ")
        self.assertEqual(held, "`")

    def test_partial_double_backtick(self):
        safe, held = self.display._split_partial("hello ``")
        self.assertEqual(safe, "hello ")
        self.assertEqual(held, "``")

    def test_partial_triple_backtick(self):
        safe, held = self.display._split_partial("hello ```")
        self.assertEqual(safe, "hello ")
        self.assertEqual(held, "```")


class TestFindClosingBackticks(unittest.TestCase):
    """Test the _find_closing_backticks helper."""

    def setUp(self):
        self.display = StreamDisplay()

    def test_closing_at_start(self):
        result = self.display._find_closing_backticks("```\n")
        self.assertEqual(result, 0)

    def test_closing_after_newline(self):
        result = self.display._find_closing_backticks("some json\n```\n")
        self.assertIsNotNone(result)

    def test_no_closing(self):
        result = self.display._find_closing_backticks("just text")
        self.assertIsNone(result)

    def test_opening_not_closing(self):
        # ```python is an opening, not a closing
        result = self.display._find_closing_backticks("```python\n")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
