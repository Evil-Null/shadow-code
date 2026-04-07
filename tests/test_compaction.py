"""Tests for compaction.py -- conversation summarization."""

import unittest
from unittest.mock import MagicMock

from shadow_code.compaction import compact, format_summary


class TestFormatSummary(unittest.TestCase):
    """Tests for format_summary()."""

    def test_strips_xml_tags(self):
        raw = "<analysis>some analysis</analysis>\nThe actual summary"
        result = format_summary(raw)
        self.assertNotIn("<analysis>", result)
        self.assertIn("The actual summary", result)

    def test_no_tags_returns_cleaned(self):
        raw = "Just a plain text summary with no XML tags."
        result = format_summary(raw)
        self.assertEqual(result, raw)

    def test_multiline(self):
        raw = "1. Request: Fix bug\n2. Files: main.py"
        result = format_summary(raw)
        self.assertIn("Fix bug", result)
        self.assertIn("main.py", result)

    def test_whitespace_stripped(self):
        raw = "  \n  Hello  \n  "
        result = format_summary(raw)
        self.assertEqual(result, "Hello")

    def test_strips_summary_tags(self):
        raw = "<summary>content here</summary>"
        result = format_summary(raw)
        self.assertNotIn("<summary>", result)
        self.assertIn("content here", result)


class TestCompact(unittest.TestCase):
    """Tests for compact() function."""

    def test_compact_returns_summary(self):
        client = MagicMock()
        client.chat_stream.return_value = iter(["Summary: user asked to fix bug in main.py"])
        messages = [{"role": "user", "content": "hello"}]
        result = compact(client, messages, "system prompt")
        self.assertIn("fix bug", result)

    def test_compact_raises_on_empty_response(self):
        client = MagicMock()
        client.chat_stream.return_value = iter(["", "  "])
        messages = [{"role": "user", "content": "hello"}]
        with self.assertRaises(RuntimeError):
            compact(client, messages, "system prompt")

    def test_compact_appends_compact_prompt(self):
        client = MagicMock()
        client.chat_stream.return_value = iter(["OK summary"])
        messages = [{"role": "user", "content": "hello"}]
        compact(client, messages, "system prompt")
        call_args = client.chat_stream.call_args
        sent_messages = call_args[0][0]
        self.assertEqual(len(sent_messages), 2)
        self.assertIn("summarize", sent_messages[-1]["content"].lower())


if __name__ == "__main__":
    unittest.main()
