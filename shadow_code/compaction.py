# shadow_code/compaction.py -- Auto-compaction via LLM summarization
#
# When context usage exceeds the compaction threshold (65%), the conversation
# history is sent to the LLM with a special summarization prompt. The LLM
# produces a structured summary that replaces old messages, freeing context
# space while preserving essential information.
#
# This follows the Claude Code pattern:
#   1. Append COMPACT_PROMPT as a final user message
#   2. Stream the response (non-displayed, just collect)
#   3. Strip <analysis> tags, extract <summary> content
#   4. Return the summary text for conversation.apply_compaction_summary()

import re

from .ollama_client import OllamaClient


COMPACT_PROMPT = """Your task is to create a detailed summary of the conversation so far.
This summary will replace the conversation history to free up context space.

CRITICAL: Respond with TEXT ONLY. Do NOT use any tools.

Your summary should include:

1. Primary Request: What the user asked for
2. Files Modified: List of files read, edited, or created with key changes
3. Errors and Fixes: Problems encountered and how they were resolved
4. Current Work: What was being worked on immediately before this summary
5. Pending Tasks: Any incomplete work
6. Next Step: The next action to take

Wrap your analysis in <analysis> tags (will be stripped), then provide the
summary in <summary> tags.

<analysis>
[Your analysis of the conversation]
</analysis>

<summary>
[Structured summary following the sections above]
</summary>
"""


def compact(client: OllamaClient, messages: list[dict], system_prompt: str) -> str:
    """Send conversation to LLM for summarization.

    Appends the compaction prompt as a final user message, streams the
    response (collecting it silently -- nothing is displayed), then
    extracts the structured summary.

    Args:
        client: OllamaClient instance for streaming chat.
        messages: Current conversation messages (list of role/content dicts).
        system_prompt: The static system prompt.

    Returns:
        Cleaned summary text (analysis stripped, summary extracted).
    """
    compact_messages = messages + [{"role": "user", "content": COMPACT_PROMPT}]

    full_response = ""
    for chunk in client.chat_stream(compact_messages, system_prompt):
        full_response += chunk

    return format_summary(full_response)


def format_summary(raw: str) -> str:
    """Strip <analysis> block and extract <summary> content.

    The compaction prompt instructs the model to wrap its reasoning in
    <analysis> tags (which we discard) and the actual summary in <summary>
    tags (which we keep). If the model doesn't use tags, the full cleaned
    text is returned as-is.

    Args:
        raw: Raw model response from the compaction call.

    Returns:
        Cleaned summary text.
    """
    # Remove <analysis>...</analysis> block (greedy within tags, DOTALL for newlines)
    cleaned = re.sub(r"<analysis>.*?</analysis>", "", raw, flags=re.DOTALL)

    # Extract content from <summary>...</summary>
    match = re.search(r"<summary>(.*?)</summary>", cleaned, re.DOTALL)
    if match:
        return match.group(1).strip()

    # No <summary> tags -- return whatever remains after stripping analysis
    return cleaned.strip()
