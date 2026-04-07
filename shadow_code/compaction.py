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

Summarize this conversation for continuity. Format:

## User Goal
What the user is trying to accomplish (1-2 sentences).

## Files Modified
For each file created or edited:
- Path: exact path
- What changed: key modifications
- Current state: working / broken / partial

## Files Read (Not Modified)
List file paths that were read for context.

## Errors Encountered
What failed and how it was fixed (or if still broken).

## Current Task
What was being worked on. What the immediate next step is.

## Key Code Details
Function signatures, variable names, architectural decisions needed to continue.

Keep ALL file paths, function names, and variable names EXACT.
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
