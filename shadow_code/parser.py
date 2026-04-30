"""Parse tool calls from model output.

Phase 0 validation determined that the model naturally uses markdown code block
format (```tool_call) rather than XML tags. The regex matches this format.
"""

import json
import re
from dataclasses import dataclass


@dataclass
class ToolCall:
    tool: str
    params: dict
    raw: str


# Validated formats:
#   1. Canonical: ```tool_call\n{JSON}\n``` (Gemma 3/4 native)
#   2. Lenient:   ```bash | ```sh | ```json | ```python\n{JSON with tool+params}\n```
#                 (qwen2.5-coder occasionally relabels the fence; JSON itself is valid)
# Detection strategy: match ANY fenced block, then validate JSON content has
# the {"tool": str, "params": object} shape. Non-tool fenced blocks (e.g. real
# bash scripts the model just shows for explanation) are silently skipped.
CANONICAL_FENCE_RE = re.compile(r"```tool_call\s*\n(.*?)\n```", re.DOTALL)
ANY_FENCE_RE = re.compile(
    r"```(?:bash|sh|json|python|tool_call)?\s*\n(.*?)\n```", re.DOTALL
)
# Unclosed fence at end of stream — happens when the model stops generating
# right after emitting the JSON (anti-hallucination rule side effect on 7B
# models). Only match when fence is at the very end and contains valid tool JSON.
UNCLOSED_FENCE_RE = re.compile(
    r"```(?:bash|sh|json|python|tool_call)?\s*\n(\{[^`]*?\})\s*\Z", re.DOTALL
)
# Pass 4 fallback: raw shell commands in ```bash``` or ```sh``` blocks (no JSON).
# 7B models often emit ```bash\nls -la\n``` directly instead of the canonical
# tool_call format. Treat these as bash tool calls when no other tool was parsed.
RAW_SHELL_FENCE_RE = re.compile(r"```(?:bash|sh)\s*\n(.*?)\n```", re.DOTALL)


def _try_parse_tool_json(json_str: str) -> dict | None:
    """Return dict if json_str parses to a valid {tool, params} object, else None."""
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        return None
    if (
        isinstance(data, dict)
        and isinstance(data.get("tool"), str)
        and isinstance(data.get("params"), dict)
    ):
        return data
    return None


def parse_tool_calls(text: str) -> tuple[str, list[ToolCall]]:
    """Extract tool calls from model response.

    Returns (clean_text, calls) where clean_text has tool call blocks removed
    and calls is a list of parsed ToolCall objects.

    Two-pass strategy:
      Pass 1: Canonical ```tool_call``` blocks. Invalid JSON here -> __invalid__
              (the model intended a tool call and we want to surface the error).
      Pass 2: Other fenced blocks (```bash/```sh/```json). Only included if the
              JSON content is a valid {tool, params} object — otherwise treated
              as ordinary code in an explanation and left in clean_text.

    Invalid JSON inside a canonical ```tool_call``` produces a ToolCall with
    tool="__invalid__" so the caller can report the error back to the model.
    """
    calls: list[ToolCall] = []
    consumed_spans: list[tuple[int, int]] = []

    # Pass 1: canonical fences (strict — invalid JSON is an error to report)
    for match in CANONICAL_FENCE_RE.finditer(text):
        raw_block = match.group(0)
        json_str = match.group(1)
        data = _try_parse_tool_json(json_str)
        if data is not None:
            calls.append(ToolCall(tool=data["tool"], params=data["params"], raw=raw_block))
        else:
            # Distinguish "invalid JSON" from "valid JSON but wrong shape"
            try:
                json.loads(json_str)
                # Valid JSON, wrong shape — skip silently (model may show example)
                continue
            except json.JSONDecodeError:
                calls.append(
                    ToolCall(
                        tool="__invalid__",
                        params={"error": f"Invalid JSON: {json_str[:200]}"},
                        raw=raw_block,
                    )
                )
        consumed_spans.append(match.span())

    # Pass 2: lenient fences (only count if JSON is a valid tool-call shape)
    for match in ANY_FENCE_RE.finditer(text):
        # Skip if already consumed by canonical pass
        if any(s <= match.start() < e for s, e in consumed_spans):
            continue
        # Skip canonical fences re-matched by the broader regex
        if match.group(0).startswith("```tool_call"):
            continue
        raw_block = match.group(0)
        json_str = match.group(1)
        data = _try_parse_tool_json(json_str)
        if data is None:
            continue  # plain code block in explanation — leave it in clean_text
        calls.append(ToolCall(tool=data["tool"], params=data["params"], raw=raw_block))
        consumed_spans.append(match.span())

    # Pass 3: unclosed fence at end-of-stream (model stopped generating after
    # emitting JSON — common with 7B models under strict anti-halluc rules).
    if not calls:  # only fall back if nothing matched above
        m = UNCLOSED_FENCE_RE.search(text)
        if m and not any(s <= m.start() < e for s, e in consumed_spans):
            data = _try_parse_tool_json(m.group(1))
            if data is not None:
                calls.append(
                    ToolCall(tool=data["tool"], params=data["params"], raw=m.group(0))
                )
                consumed_spans.append(m.span())

    # Pass 4: raw shell command in ```bash/```sh block (7B fallback).
    # Only fires when no other tool call was parsed AND the body does NOT look
    # like JSON (so we don't double-match Pass 2 candidates).
    if not calls:
        for m in RAW_SHELL_FENCE_RE.finditer(text):
            if any(s <= m.start() < e for s, e in consumed_spans):
                continue
            body = m.group(1).strip()
            if not body:
                continue
            # Skip JSON-shaped bodies (already handled by Pass 2 and rejected if invalid)
            if body.startswith("{") and body.endswith("}"):
                continue
            calls.append(
                ToolCall(
                    tool="bash",
                    params={"command": body},
                    raw=m.group(0),
                )
            )
            consumed_spans.append(m.span())

    # Strip consumed spans from text
    if consumed_spans:
        consumed_spans.sort()
        parts: list[str] = []
        last = 0
        for start, end in consumed_spans:
            parts.append(text[last:start])
            last = end
        parts.append(text[last:])
        clean = "".join(parts).strip()
    else:
        clean = text.strip()
    return clean, calls
