"""Conversation history management with 3-tier context management.

Tier 1: Clear old tool results (fast, no API call) at 55% context usage.
Tier 2: Auto-compaction via LLM summarization at 65% context usage.
Tier 3: Emergency hard truncate at 85% (fallback if compaction fails).

Tool results use <tool_result> tags -- these are system-generated (not model-generated)
so they remain as XML regardless of the ```tool_call format used by the model.
"""

from .config import CONTEXT_WINDOW

# Thresholds (Claude Code style)
RESULT_CLEARING_RATIO = 0.55  # clear old tool results at 55%
COMPACTION_RATIO = 0.65  # auto-compact at 65% (low enough to leave room for summary)
EMERGENCY_TRUNCATE_RATIO = 0.85  # hard truncate at 85% (fallback if compaction fails)
KEEP_RECENT_RESULTS = 5
KEEP_RECENT_MESSAGES = 20
CLEARED_STUB = "[Tool result cleared to save context. Output was already processed.]"


class Conversation:
    def __init__(self):
        self.messages: list[dict] = []
        self.total_prompt_tokens = 0

    def add_user(self, content: str):
        self.messages.append({"role": "user", "content": content})

    def add_assistant(self, content: str):
        self.messages.append({"role": "assistant", "content": content})

    def add_tool_results(self, results_text: str):
        prefixed = (
            "[Tool results below. Use these results to continue. "
            "Write COMPLETE code -- never abbreviate with '...' or placeholders.]\n\n"
            + results_text
        )
        self.messages.append({"role": "user", "content": prefixed})

    def update_tokens(self, prompt_tokens: int):
        self.total_prompt_tokens = prompt_tokens

    # === Context Management (Claude Code style, 3-tier) ===

    def needs_result_clearing(self) -> bool:
        return bool(self.total_prompt_tokens > int(CONTEXT_WINDOW * RESULT_CLEARING_RATIO))

    def needs_compaction(self) -> bool:
        return bool(self.total_prompt_tokens > int(CONTEXT_WINDOW * COMPACTION_RATIO))

    def needs_emergency_truncate(self) -> bool:
        return bool(self.total_prompt_tokens > int(CONTEXT_WINDOW * EMERGENCY_TRUNCATE_RATIO))

    def clear_old_tool_results(self):
        """Tier 1: Replace old tool results with stubs. Fast, no API call."""
        indices = [
            i
            for i, m in enumerate(self.messages)
            if m["role"] == "user" and "<tool_result" in m["content"]
        ]
        for i in indices[:-KEEP_RECENT_RESULTS]:
            self.messages[i] = {"role": "user", "content": CLEARED_STUB}

    def apply_compaction_summary(self, summary: str):
        """Tier 2: Replace old messages with LLM-generated summary."""
        if len(self.messages) <= KEEP_RECENT_MESSAGES:
            return
        self.messages = self.messages[-KEEP_RECENT_MESSAGES:]
        self.messages.insert(
            0,
            {
                "role": "user",
                "content": "[This session continues from earlier. Summary of previous work:\n\n"
                + summary
                + "\n\nRecent messages follow.]",
            },
        )

    def emergency_truncate(self):
        """Tier 3: Hard truncate as last resort (compaction failed)."""
        if len(self.messages) <= KEEP_RECENT_MESSAGES:
            return
        removed = len(self.messages) - KEEP_RECENT_MESSAGES
        self.messages = self.messages[-KEEP_RECENT_MESSAGES:]
        self.messages.insert(
            0,
            {
                "role": "user",
                "content": f"[Previous {removed} messages truncated to save context.]",
            },
        )

    def clear(self):
        self.messages.clear()
        self.total_prompt_tokens = 0

    def get_messages(self) -> list[dict]:
        return list(self.messages)
