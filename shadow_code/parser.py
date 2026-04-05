"""Parse tool calls from model output.

Phase 0 validation determined that the model naturally uses markdown code block
format (```tool_call) rather than XML tags. The regex matches this format.
"""

import re
import json
from dataclasses import dataclass


@dataclass
class ToolCall:
    tool: str
    params: dict
    raw: str


# Phase 0 validated format: ```tool_call\n{JSON}\n```
# The model (Gemma 3, 27B) naturally produces this format even when
# instructed to use XML tags -- it's the training-data-preferred format.
TOOL_CALL_RE = re.compile(r'```tool_call\s*\n(.*?)\n```', re.DOTALL)


def parse_tool_calls(text: str) -> tuple[str, list[ToolCall]]:
    """Extract tool calls from model response.

    Returns (clean_text, calls) where clean_text has tool call blocks removed
    and calls is a list of parsed ToolCall objects.

    Invalid JSON in a tool call block produces a ToolCall with tool="__invalid__"
    so the caller can report the error back to the model.
    """
    calls = []
    for match in TOOL_CALL_RE.finditer(text):
        raw_block = match.group(0)
        json_str = match.group(1)
        try:
            data = json.loads(json_str)
            if isinstance(data.get("tool"), str) and isinstance(data.get("params"), dict):
                calls.append(ToolCall(
                    tool=data["tool"],
                    params=data["params"],
                    raw=raw_block,
                ))
            # else: has JSON but wrong structure -- skip silently
        except json.JSONDecodeError:
            calls.append(ToolCall(
                tool="__invalid__",
                params={"error": f"Invalid JSON: {json_str[:200]}"},
                raw=raw_block,
            ))
    clean = TOOL_CALL_RE.sub("", text).strip()
    return clean, calls
