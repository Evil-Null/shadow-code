# shadow_code/compaction.py -- Auto-compaction via LLM summarization
#
# Adapted from Claude Code's compact/prompt.ts (9-section summary format).
#
# When context exceeds 65%, conversation is sent to LLM for structured
# summarization. The summary replaces old messages, freeing context space.

import re

from .config import COMPACTION_MODEL
from .ollama_client import OllamaClient

# Aggressive no-tools preamble (from Claude Code -- prevents wasted turns)
_NO_TOOLS = """CRITICAL: Respond with TEXT ONLY. Do NOT call any tools.
Do NOT use bash, read_file, edit_file, write_file, glob, grep, or list_dir.
You already have all the context you need in the conversation above.
Your entire response must be plain text: an <analysis> block followed by a <summary> block.
"""

COMPACT_PROMPT = (
    _NO_TOOLS
    + """Your task is to create a detailed summary of the conversation so far,
paying close attention to the user's explicit requests and your previous actions.
This summary should be thorough in capturing technical details, code patterns,
and architectural decisions essential for continuing work without losing context.

Before providing your summary, wrap your analysis in <analysis> tags to organize
your thoughts. In your analysis:
1. Chronologically analyze each message. For each, identify:
   - The user's explicit requests and intents
   - Your approach to addressing them
   - Key decisions, technical concepts, code patterns
   - Specific file names, code snippets, function signatures, file edits
   - Errors encountered and how they were fixed
   - User feedback, especially corrections ("do it differently", "not that way")
2. Double-check for technical accuracy and completeness.

Your summary should include these sections:

1. Primary Request and Intent: All of the user's explicit requests in detail
2. Key Technical Concepts: Technologies, frameworks, patterns discussed
3. Files and Code: Files examined, modified, or created. Include:
   - Why each file is important
   - Summary of changes made
   - Key code snippets where relevant
4. Errors and Fixes: All errors encountered, how fixed, user feedback on fixes
5. Problem Solving: Problems solved, ongoing troubleshooting
6. All User Messages: List ALL non-tool-result user messages (critical for intent tracking)
7. Pending Tasks: Incomplete work explicitly requested
8. Current Work: Precisely what was being worked on immediately before this summary,
   with file names and code snippets
9. Next Step: The next action directly in line with the user's most recent request.
   Include direct quotes from the conversation showing exactly what task was in progress.

<analysis>
[Your chronological analysis of the conversation]
</analysis>

<summary>
1. Primary Request and Intent:
   [Detailed description]

2. Key Technical Concepts:
   - [Concept 1]
   - [Concept 2]

3. Files and Code:
   - [File path]
     - [Why important]
     - [Changes made]
     - [Code snippet if relevant]

4. Errors and Fixes:
   - [Error]: [How fixed]

5. Problem Solving:
   [Description]

6. All User Messages:
   - [Message 1]
   - [Message 2]

7. Pending Tasks:
   - [Task 1]

8. Current Work:
   [Precise description with file names]

9. Next Step:
   [Next action with quotes from conversation]
</summary>

REMINDER: Do NOT call any tools. Respond with plain text only.
"""
)


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
    """Strip <analysis>, extract <summary> content.

    The model wraps reasoning in <analysis> (discarded) and the
    actual summary in <summary> (kept). If no tags, returns cleaned text.
    """
    # Remove analysis block
    cleaned = re.sub(r"<analysis>.*?</analysis>", "", raw, flags=re.DOTALL)

    # Extract summary content
    match = re.search(r"<summary>(.*?)</summary>", cleaned, re.DOTALL)
    if match:
        summary = match.group(1).strip()
        # Replace XML-style tags with readable headers
        summary = summary.replace("<summary>", "").replace("</summary>", "")
        return summary

    # No tags -- return cleaned text
    return cleaned.strip()
