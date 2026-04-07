"""Tests for compaction.py -- conversation summarization."""

import unittest
from unittest.mock import MagicMock

from shadow_code.compaction import compact, format_summary


class TestFormatSummary(unittest.TestCase):
    """Tests for format_summary()."""

    def test_extracts_summary_block(self):
        raw = "<analysis>some analysis</analysis>\n<summary>The actual summary</summary>"
        result = format_summary(raw)
        self.assertEqual(result, "The actual summary")

    def test_strips_analysis_block(self):
        raw = "<analysis>discard this</analysis>\nPlain text remains"
        result = format_summary(raw)
        self.assertNotIn("discard this", result)
        self.assertIn("Plain text remains", result)

    def test_no_tags_returns_cleaned(self):
        raw = "Just a plain text summary with no XML tags."
        result = format_summary(raw)
        self.assertEqual(result, raw)

    def test_multiline_summary(self):
        raw = (
            "<analysis>Line 1\nLine 2</analysis>\n"
            "<summary>\n1. Request: Fix bug\n2. Files: main.py\n</summary>"
        )
        result = format_summary(raw)
        self.assertIn("Fix bug", result)
        self.assertIn("main.py", result)

    def test_nested_summary_tags_cleaned(self):
        raw = "<summary><summary>inner</summary></summary>"
        result = format_summary(raw)
        self.assertIn("inner", result)

    def test_empty_summary(self):
        raw = "<analysis>stuff</analysis><summary></summary>"
        result = format_summary(raw)
        self.assertEqual(result, "")

    def test_whitespace_stripped(self):
        raw = "<summary>  \n  Hello  \n  </summary>"
        result = format_summary(raw)
        self.assertEqual(result, "Hello")


class TestCompact(unittest.TestCase):
    """Tests for compact() function."""

    def test_compact_returns_summary(self):
        client = MagicMock()
        client.chat_stream.return_value = iter(
            [
                "<analysis>thinking</analysis>\n",
                "<summary>Summarized content</summary>",
            ]
        )
        messages = [{"role": "user", "content": "hello"}]
        result = compact(client, messages, "system prompt")
        self.assertEqual(result, "Summarized content")

    def test_compact_raises_on_empty_response(self):
        client = MagicMock()
        client.chat_stream.return_value = iter(["", "  "])
        messages = [{"role": "user", "content": "hello"}]
        with self.assertRaises(RuntimeError):
            compact(client, messages, "system prompt")

    def test_compact_appends_compact_prompt(self):
        client = MagicMock()
        client.chat_stream.return_value = iter(["<summary>OK</summary>"])
        messages = [{"role": "user", "content": "hello"}]
        compact(client, messages, "system prompt")
        # Verify chat_stream was called with messages + compact prompt
        call_args = client.chat_stream.call_args
        sent_messages = call_args[0][0]
        self.assertEqual(len(sent_messages), 2)  # original + compact prompt
        self.assertIn("summary", sent_messages[-1]["content"].lower())


if __name__ == "__main__":
    unittest.main()
