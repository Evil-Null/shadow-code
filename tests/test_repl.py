"""Tests for repl.py -- REPL input handling."""

import unittest
from unittest.mock import MagicMock, patch

from shadow_code.repl import _SLASH_COMMANDS, get_input


class TestSlashCommands(unittest.TestCase):
    """Test slash command list."""

    def test_contains_help(self):
        self.assertIn("/help", _SLASH_COMMANDS)

    def test_contains_exit(self):
        self.assertIn("/exit", _SLASH_COMMANDS)

    def test_contains_clear(self):
        self.assertIn("/clear", _SLASH_COMMANDS)

    def test_all_start_with_slash(self):
        for cmd in _SLASH_COMMANDS:
            self.assertTrue(cmd.startswith("/"), f"{cmd} doesn't start with /")


class TestGetInputFallback(unittest.TestCase):
    """Test get_input with session=None (fallback mode)."""

    @patch("builtins.input", return_value="hello world")
    def test_fallback_returns_stripped(self, mock_input):
        result = get_input(None, "model")
        self.assertEqual(result, "hello world")

    @patch("builtins.input", return_value="  spaced  ")
    def test_fallback_strips_whitespace(self, mock_input):
        result = get_input(None, "model")
        self.assertEqual(result, "spaced")

    @patch("builtins.input", side_effect=EOFError)
    def test_fallback_eof_returns_none(self, mock_input):
        result = get_input(None, "model")
        self.assertIsNone(result)

    @patch("builtins.input", side_effect=KeyboardInterrupt)
    def test_fallback_interrupt_returns_empty(self, mock_input):
        result = get_input(None, "model")
        self.assertEqual(result, "")


class TestGetInputWithSession(unittest.TestCase):
    """Test get_input with a mock PromptSession."""

    def test_session_returns_text(self):
        session = MagicMock()
        session.prompt.return_value = "user input"
        # Need _HAS_PROMPT_TOOLKIT to be True for session path
        with patch("shadow_code.repl._HAS_PROMPT_TOOLKIT", True):
            result = get_input(session, "model")
        self.assertEqual(result, "user input")

    def test_session_strips_whitespace(self):
        session = MagicMock()
        session.prompt.return_value = "  padded  "
        with patch("shadow_code.repl._HAS_PROMPT_TOOLKIT", True):
            result = get_input(session, "model")
        self.assertEqual(result, "padded")

    def test_session_none_result(self):
        session = MagicMock()
        session.prompt.return_value = None
        with patch("shadow_code.repl._HAS_PROMPT_TOOLKIT", True):
            result = get_input(session, "model")
        self.assertIsNone(result)

    def test_session_eof(self):
        session = MagicMock()
        session.prompt.side_effect = EOFError
        with patch("shadow_code.repl._HAS_PROMPT_TOOLKIT", True):
            result = get_input(session, "model")
        self.assertIsNone(result)

    def test_session_keyboard_interrupt(self):
        session = MagicMock()
        session.prompt.side_effect = KeyboardInterrupt
        with patch("shadow_code.repl._HAS_PROMPT_TOOLKIT", True):
            result = get_input(session, "model")
        self.assertEqual(result, "")


if __name__ == "__main__":
    unittest.main()
