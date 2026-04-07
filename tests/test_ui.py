"""Tests for ui.py -- Rich UI rendering (requires rich)."""

import unittest

try:
    from rich.text import Text

    HAS_RICH = True
except ImportError:
    HAS_RICH = False

from shadow_code.ui import HAS_RICH as UI_HAS_RICH


@unittest.skipUnless(HAS_RICH and UI_HAS_RICH, "rich not installed")
class TestUIRenderer(unittest.TestCase):
    """Tests for UIRenderer methods."""

    def setUp(self):
        from shadow_code.ui import UIRenderer

        self.ui = UIRenderer()

    def test_render_welcome(self):
        result = self.ui.render_welcome()
        self.assertIsNotNone(result)

    def test_render_thinking(self):
        result = self.ui.render_thinking()
        self.assertIsNotNone(result)

    def test_render_streaming(self):
        result = self.ui.render_streaming("Hello world")
        self.assertIsNotNone(result)

    def test_render_streaming_empty(self):
        result = self.ui.render_streaming("")
        self.assertIsNotNone(result)

    def test_render_response(self):
        result = self.ui.render_response("Some response", tokens=100)
        self.assertIsNotNone(result)

    def test_render_response_no_tokens(self):
        result = self.ui.render_response("Response")
        self.assertIsNotNone(result)

    def test_render_tool_call(self):
        result = self.ui.render_tool_call("bash", "ls -la")
        self.assertIsInstance(result, Text)

    def test_render_tool_result_success(self):
        result = self.ui.render_tool_result("bash", "file1\nfile2", True)
        self.assertIsNotNone(result)

    def test_render_tool_result_failure(self):
        result = self.ui.render_tool_result("bash", "command not found", False)
        self.assertIsNotNone(result)

    def test_render_tool_result_long_output(self):
        long_output = "x" * 5000
        result = self.ui.render_tool_result("bash", long_output, True)
        self.assertIsNotNone(result)

    def test_render_tool_result_syntax_highlight(self):
        code = "def hello():\n    print('hi')\n" * 5
        result = self.ui.render_tool_result("read_file", code, True)
        self.assertIsNotNone(result)

    def test_render_tool_result_short_text(self):
        result = self.ui.render_tool_result("glob", "short", True)
        self.assertIsNotNone(result)

    def test_render_error(self):
        result = self.ui.render_error("Something went wrong")
        self.assertIsInstance(result, Text)

    def test_render_context_status_low(self):
        result = self.ui.render_context_status(10000, 131072)
        self.assertIsInstance(result, Text)

    def test_render_context_status_medium(self):
        result = self.ui.render_context_status(80000, 131072)
        self.assertIsInstance(result, Text)

    def test_render_context_status_high(self):
        result = self.ui.render_context_status(120000, 131072)
        self.assertIsInstance(result, Text)

    def test_render_context_status_zero(self):
        result = self.ui.render_context_status(0, 0)
        self.assertIsInstance(result, Text)

    def test_render_help(self):
        commands = [("/help", "Show help"), ("/exit", "Exit")]
        result = self.ui.render_help(commands)
        self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main()
