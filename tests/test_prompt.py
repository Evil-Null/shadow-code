"""Tests for prompt.py -- system prompt integrity checks."""

import unittest

from shadow_code.prompt import SYSTEM_PROMPT


class TestSystemPrompt(unittest.TestCase):
    """Test the static SYSTEM_PROMPT constant."""

    def test_is_string(self):
        self.assertIsInstance(SYSTEM_PROMPT, str)

    def test_not_empty(self):
        self.assertGreater(len(SYSTEM_PROMPT), 1000)

    # --- Required sections ---

    def test_has_tool_calling_format(self):
        self.assertIn("```tool_call", SYSTEM_PROMPT)

    def test_has_tool_result_format(self):
        self.assertIn("<tool_result", SYSTEM_PROMPT)

    def test_has_bash_tool(self):
        self.assertIn("## bash", SYSTEM_PROMPT)

    def test_has_read_file_tool(self):
        self.assertIn("## read_file", SYSTEM_PROMPT)

    def test_has_edit_file_tool(self):
        self.assertIn("## edit_file", SYSTEM_PROMPT)

    def test_has_write_file_tool(self):
        self.assertIn("## write_file", SYSTEM_PROMPT)

    def test_has_glob_tool(self):
        self.assertIn("## glob", SYSTEM_PROMPT)

    def test_has_grep_tool(self):
        self.assertIn("## grep", SYSTEM_PROMPT)

    def test_has_list_dir_tool(self):
        self.assertIn("## list_dir", SYSTEM_PROMPT)

    def test_has_doing_tasks_section(self):
        self.assertIn("# Doing Tasks", SYSTEM_PROMPT)

    def test_has_git_section(self):
        self.assertIn("Committing Changes with Git", SYSTEM_PROMPT)

    def test_has_tone_section(self):
        self.assertIn("Tone and Style", SYSTEM_PROMPT)

    def test_has_output_efficiency(self):
        self.assertIn("Output Efficiency", SYSTEM_PROMPT)

    # --- Language rule ---

    def test_has_language_rule(self):
        self.assertIn("SAME language", SYSTEM_PROMPT)

    def test_has_georgian_rule(self):
        self.assertIn("Georgian", SYSTEM_PROMPT)

    # --- Safety rules ---

    def test_has_security_rule(self):
        self.assertIn("OWASP", SYSTEM_PROMPT)

    def test_has_git_safety(self):
        self.assertIn("--no-verify", SYSTEM_PROMPT)
        self.assertIn("force push", SYSTEM_PROMPT.lower())

    def test_no_dynamic_content(self):
        """System prompt must be 100% static -- no f-string markers."""
        # If someone accidentally converts to f-string, this catches it
        self.assertNotIn("{os.", SYSTEM_PROMPT)
        self.assertNotIn("{datetime", SYSTEM_PROMPT)
        self.assertNotIn("{platform", SYSTEM_PROMPT)
        self.assertNotIn("{sys.", SYSTEM_PROMPT)

    # --- Tool call format examples ---

    def test_has_json_tool_example(self):
        self.assertIn('"tool":', SYSTEM_PROMPT)
        self.assertIn('"params":', SYSTEM_PROMPT)

    def test_has_tool_call_rules(self):
        self.assertIn("exactly two keys", SYSTEM_PROMPT)

    # --- Executing actions section ---

    def test_has_care_section(self):
        self.assertIn("Executing Actions with Care", SYSTEM_PROMPT)

    def test_has_destructive_warnings(self):
        self.assertIn("rm -rf", SYSTEM_PROMPT)
        self.assertIn("reset --hard", SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()
