"""Tests for repl.py -- REPL input handling."""

import unittest
from unittest.mock import patch

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


class TestCreatePromptSession(unittest.TestCase):
    """Test create_prompt_session."""

    def test_returns_none_without_prompt_toolkit(self):
        from shadow_code.repl import create_prompt_session

        with patch("shadow_code.repl._HAS_PROMPT_TOOLKIT", False):
            result = create_prompt_session()
            self.assertIsNone(result)

    def test_returns_dict_with_prompt_toolkit(self):
        from shadow_code.repl import create_prompt_session

        # Only test if prompt_toolkit is installed
        try:
            import prompt_toolkit  # noqa: F401

            result = create_prompt_session()
            self.assertIsInstance(result, dict)
            self.assertIn("history_path", result)
        except ImportError:
            pass  # Skip if not installed


if __name__ == "__main__":
    unittest.main()
