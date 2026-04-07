"""Tests for streaming.py -- Rich Live streaming controller."""

import unittest
from unittest.mock import MagicMock

from shadow_code.streaming import StreamCancelled, StreamController


class TestStreamCancelled(unittest.TestCase):
    """Test StreamCancelled exception."""

    def test_is_exception(self):
        self.assertTrue(issubclass(StreamCancelled, Exception))

    def test_can_raise_and_catch(self):
        with self.assertRaises(StreamCancelled):
            raise StreamCancelled()


class TestStreamControllerPlain(unittest.TestCase):
    """Test StreamController in plain mode (no Rich)."""

    def _make_controller(self, chunks):
        """Create a StreamController with a mock client."""
        client = MagicMock()
        client.chat_stream.return_value = iter(chunks)
        client.last_eval_tokens = 42
        ui = MagicMock()
        ctrl = StreamController(client, ui, console=None, display=None)
        return ctrl

    def test_stream_plain_returns_response(self):
        ctrl = self._make_controller(["Hello ", "world"])
        resp, tokens = ctrl._stream_plain([], "system")
        self.assertEqual(resp, "Hello world")
        self.assertEqual(tokens, 42)

    def test_stream_plain_empty(self):
        ctrl = self._make_controller([])
        resp, tokens = ctrl._stream_plain([], "system")
        self.assertEqual(resp, "")

    def test_stream_response_uses_plain_when_no_rich(self):
        """When HAS_RICH is available but console is None, should still work."""
        ctrl = self._make_controller(["test"])
        # _stream_plain should work without Rich
        resp, _ = ctrl._stream_plain([], "system")
        self.assertEqual(resp, "test")


class TestStreamControllerCapture(unittest.TestCase):
    """Test _feed_and_capture and _flush_and_capture."""

    def test_feed_and_capture_plain_text(self):
        client = MagicMock()
        ui = MagicMock()
        ctrl = StreamController(client, ui)
        ctrl.display.reset()
        result = ctrl._feed_and_capture("Hello")
        self.assertIn("Hello", result)

    def test_feed_and_capture_tool_call_hidden(self):
        client = MagicMock()
        ui = MagicMock()
        ctrl = StreamController(client, ui)
        ctrl.display.reset()
        result = ctrl._feed_and_capture('```tool_call\n{"tool": "bash", "params": {}}\n```')
        self.assertNotIn('"tool"', result)

    def test_flush_and_capture(self):
        client = MagicMock()
        ui = MagicMock()
        ctrl = StreamController(client, ui)
        ctrl.display.reset()
        ctrl.display.buffer = "leftover"
        result = ctrl._flush_and_capture()
        self.assertIn("leftover", result)


if __name__ == "__main__":
    unittest.main()
