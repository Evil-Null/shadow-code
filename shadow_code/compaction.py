# shadow_code/compaction.py -- Auto-compaction via LLM summarization
#
# Adapted from Claude Code's compact/prompt.ts (9-section summary format).
#
# When context exceeds 65%, conversation is sent to LLM for structured
# summarization. The summary replaces old messages, freeing context space.

import re

from .config import COMPACTION_MODEL
from .ollama_client import OllamaClient

COMPACT_PROMPT = """RESPOND WITH TEXT ONLY. Do NOT call any tools.

Summarize this conversation. Include:

1. WHAT THE USER WANTS: All requests, in order
2. WHAT WAS DONE: Files read/modified/created, with exact paths and key changes
3. WHAT FAILED: Errors encountered and how they were fixed
4. WHAT'S NEXT: The current task and next step

Keep file paths, function names, and variable names exact. Be detailed on code changes.
Do NOT use any tools. Plain text only."""


def compact(client: OllamaClient, messages: list[dict], system_prompt: str) -> str:
    """Send conversation to LLM for summarization. Returns cleaned summary.

    Args:
        client: OllamaClient instance.
        messages: Current conversation messages.
        system_prompt: The static system prompt.

    Returns:
        Cleaned summary text (analysis stripped, summary extracted).

    Raises:
        Exception: If streaming fails or response is empty.
    """
    compact_messages = messages + [{"role": "user", "content": COMPACT_PROMPT}]

    full_response = ""
    for chunk in client.chat_stream(compact_messages, system_prompt, model=COMPACTION_MODEL):
        full_response += chunk

    if not full_response.strip():
        raise RuntimeError("Compaction produced empty response")

    return format_summary(full_response)


def format_summary(raw: str) -> str:
    """Clean up the compaction summary.

    Strips any XML-like tags the model might emit and returns plain text.
    """
    # Remove any XML-style tags the model might add
    cleaned = re.sub(r"<[a-z_]+>|</[a-z_]+>", "", raw)
    return cleaned.strip()
