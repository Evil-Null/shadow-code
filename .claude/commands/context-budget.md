Analyze context window consumption for the shadow-code project. Read the conversation and config modules, then produce a budget report.

## What to Do

1. Read `shadow_code/config.py` to get `CONTEXT_WINDOW` and `TOOL_OUTPUT_MAX_CHARS`.
2. Read `shadow_code/conversation.py` to get the 3-tier thresholds (`RESULT_CLEARING_RATIO`, `COMPACTION_RATIO`, `EMERGENCY_TRUNCATE_RATIO`).
3. Read `shadow_code/prompt.py` and count the characters in `SYSTEM_PROMPT` to estimate its token cost (chars / 4 as rough estimate).
4. Compute the budget breakdown and remaining headroom.

## Output Format

```
Context Budget: shadow-code
=============================

Window:      {CONTEXT_WINDOW} tokens

Fixed Costs:
  System prompt:    ~{prompt_tokens} tokens ({pct}%)
  Tool definitions: included in system prompt

Per-Turn Costs (worst case):
  Tool output cap:  {TOOL_OUTPUT_MAX_CHARS} chars (~{tool_tokens} tokens)
  Max tool turns:   {MAX_TOOL_TURNS} per user message

Thresholds:
  Result clearing:  {55%} = {tokens} tokens
  Auto-compaction:  {65%} = {tokens} tokens
  Emergency trunc:  {85%} = {tokens} tokens

Headroom After System Prompt:
  Available:        {available} tokens ({pct}%)
  Tool turns before compaction: ~{N} full-size tool results
  Tool turns before truncation: ~{N} full-size tool results

Recommendations:
  - [if prompt is >15% of window] System prompt consumes {pct}% — consider trimming
  - [if headroom < 20 tool turns] Only ~{N} tool turns before compaction triggers
  - [always] Use SHADOW_COMPACTION_MODEL=gemma3:4b for cheaper compaction
```

Compute real numbers from the source code — do not hardcode values.

## Arguments

$ARGUMENTS - optional: `--json` to output as JSON instead of text
