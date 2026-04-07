---
name: shadow-code-debug
description: Debugging guide for the shadow-code REPL loop, Ollama connectivity, tool dispatch, and streaming issues
version: 1.0.0
---

# Shadow Code Debugging

## Ollama Connection Failures

When `shadow-code` fails to start with "Cannot connect to Ollama":

1. Check Ollama is running: `curl http://localhost:11434/api/tags`
2. Check the model exists: `ollama list | grep shadow-gemma`
3. Check env overrides: `echo $OLLAMA_HOST $SHADOW_MODEL`
4. The health check is in `ollama_client.py:health_check()` — it tries base name matching (e.g. `shadow-gemma:latest` matches `shadow-gemma:v2`)

If Ollama is on a different host/port:
```bash
OLLAMA_HOST=http://192.168.1.10:11434 shadow-code
```

## Tool Call Not Detected

When the model responds but tools don't execute:

1. Check model output format — must be ` ```tool_call\n{JSON}\n``` ` (not ```json, not XML)
2. The regex is `TOOL_CALL_RE` in `parser.py` — test it directly:
   ```python
   from shadow_code.parser import parse_tool_calls
   text = model_response
   clean, calls = parse_tool_calls(text)
   print(f"Found {len(calls)} tool calls")
   for tc in calls:
       print(f"  {tc.tool}: {tc.params}")
   ```
3. If `calls` is empty, the model isn't producing the expected format. Check `prompt.py` SYSTEM_PROMPT — the "Tool Calling Format" section must match what the model naturally outputs
4. Common model issues:
   - Model writes `tool_call` in an explanation (not as actual invocation)
   - JSON has trailing comma or single quotes
   - Missing `"params"` key or wrong type (string instead of dict)

## Streaming Display Issues

When response text disappears or tool output is hidden:

1. **Text vanishes after streaming**: Check `streaming.py` — `transient` must be `True` on the `Live()` context. The final response is printed OUTSIDE Live via `console.print(ui.render_response(...))`
2. **Tool call JSON visible to user**: `display.py` StreamDisplay should hide `tool_call` blocks. Debug with:
   ```python
   from shadow_code.display import StreamDisplay
   d = StreamDisplay()
   d.reset()
   d.feed(chunk)  # step through chunks
   print(f"buffering={d.buffering}, buffer={d.buffer[:50]}")
   ```
3. **Rich not working**: Check `_RICH` flag in `main.py`. Falls back to plain mode if `rich` import fails. Run `python3 -c "from rich.console import Console; print('OK')"` to verify

## Tool Execution Failures

When a tool returns an error:

1. **"File has not been read yet"**: `edit_file` and `write_file` enforce read-before-write via `ToolContext.was_file_read()`. The model must call `read_file` first.
2. **"Unknown tool"**: Check `_REGISTRY` in `tools/__init__.py`. Optional tools are loaded dynamically in `main.py:_register_optional_tools()` — if an import fails silently, the tool won't be available.
3. **"Blocked path"**: `config.py:BLOCKED_PATHS` prevents reading `/dev/zero`, `/dev/urandom`, etc.
4. **"Interactive command"**: `config.py:INTERACTIVE_CMDS` blocks vim, nano, less, etc. in `BashTool.validate()`
5. **Destructive command blocked**: `safety.py:check_destructive()` matched one of 14 patterns. In the REPL, user gets a confirmation prompt. Check which pattern matched from the warning message.

## Context Window Exhaustion

When responses degrade or stop mid-sentence:

1. Check token usage: type `/tokens` in the REPL
2. The 3-tier system in `conversation.py`:
   - 55%: old tool results replaced with stubs (automatic, no API call)
   - 65%: conversation sent to LLM for compaction summary (uses `COMPACTION_MODEL`)
   - 85%: emergency truncation — keeps last 20 messages
3. If compaction fails, check `COMPACTION_MODEL` in `config.py` — a smaller model may be more reliable
4. Force manual compaction: type `/compact` in the REPL
5. To debug token counts: `client.last_prompt_tokens` is set by Ollama's `prompt_eval_count` in the final streaming message

## REPL Input Issues

When keyboard shortcuts or input don't work:

1. Check prompt_toolkit: `python3 -c "from prompt_toolkit import PromptSession; print('OK')"`
2. If not installed, falls back to `input()` — no history, no multiline, no tab completion
3. Keybindings are in `repl.py`: Alt+Enter (multiline), Ctrl+D/Ctrl+X (exit), Ctrl+L (clear), Ctrl+U (clear line)
4. History file: `~/.shadow-code/prompt_history`

## Session Persistence Issues

When `/save` or `/load` doesn't work:

1. Check SQLite: `python3 -c "import sqlite3; print('OK')"`
2. Database location: `~/.shadow-code/sessions.db`
3. Check `_HAS_DB` flag in `main.py` — if False, db import failed
4. Common: permission error on `~/.shadow-code/` directory

## Skill Dispatch Issues

When `/commit` or other skills don't activate:

1. Skills are in `skills.py` — verify with `/skills` in REPL
2. The dispatch path in `main.py`: slash command -> `get_skill(name)` -> if found, replaces `user_input` with skill prompt and falls through to model (no `continue`)
3. If skill is "not found", check for typos — the name must match exactly what's in `register_skill()`

## Quick Diagnostic Script

Run this to check all subsystems:
```bash
python3 -c "
from shadow_code.config import MODEL_NAME, CONTEXT_WINDOW, OLLAMA_BASE_URL
from shadow_code.prompt import SYSTEM_PROMPT
from shadow_code.skills import list_skills
from shadow_code.tools import _REGISTRY
print(f'Model:    {MODEL_NAME}')
print(f'Ollama:   {OLLAMA_BASE_URL}')
print(f'Context:  {CONTEXT_WINDOW:,} tokens')
print(f'Prompt:   {len(SYSTEM_PROMPT):,} chars (~{len(SYSTEM_PROMPT)//4:,} tokens)')
print(f'Skills:   {len(list_skills())}')
print(f'Tools:    {list(_REGISTRY.keys()) if _REGISTRY else \"(none registered)\"}')
"
```
