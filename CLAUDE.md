# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Shadow Code is a local AI coding assistant CLI that adapts Claude Code's prompt engineering and tool architecture to run against a local Ollama model. It gives a local LLM the same coding workflow: tool calling, file editing, git safety, context management -- all offline, no API keys.

## Commands

```bash
# Install (editable, dev mode)
pip install -e .

# Install with Rich UI + prompt_toolkit
pip install -e ".[full]"

# Install dev dependencies (lint, type check, security scan, pre-commit)
pip install -e ".[dev]"

# Run
shadow-code

# Run tests
python3 -m pytest tests/

# Run tests with coverage (80% enforced)
python3 -m pytest tests/ --cov=shadow_code --cov-report=term-missing

# Run a single test class
python3 -m pytest tests/test_parser.py::TestParseToolCalls

# Run a single test
python3 -m pytest tests/test_parser.py::TestBashTool::test_simple_command

# Lint + format
ruff check shadow_code/ tests/
ruff format --check shadow_code/ tests/

# Type check
mypy shadow_code/ --ignore-missing-imports --disable-error-code=import-untyped

# Security scan
bandit -r shadow_code/ -c pyproject.toml -q

# Run all pre-commit hooks (ruff, format, mypy, bandit, trailing whitespace, secrets)
pre-commit run --all-files
```

## Quality Gates

Pre-commit hooks and CI (`.github/workflows/ci.yml`) enforce these on every commit:
- **ruff** lint + format (line-length 100, rules: E/F/W/I/UP/B/SIM/S)
- **mypy** type checking
- **bandit** security scan
- **pytest** with 80% coverage minimum
- `prompt.py` is exempt from E501 (long static string); tests are exempt from S101/S108/SIM115

## Architecture

### Request Flow

```
User input -> main.py (REPL loop)
  -> Conversation.add_user() (with env prefix on first message)
  -> OllamaClient.chat_stream() (sends system prompt + messages to Ollama)
  -> StreamDisplay/StreamController (renders streaming tokens)
  -> parser.parse_tool_calls() (extracts ```tool_call blocks from response)
  -> tools.dispatch() (validates + executes via BaseTool registry)
  -> safety.check_destructive() (confirms dangerous bash commands)
  -> Conversation.add_tool_results() (wraps in <tool_result> tags)
  -> Loop back to OllamaClient until no more tool calls
  -> Context management check (3-tier: result clearing -> compaction -> truncate)
```

### prompt.py Is Sacred

`SYSTEM_PROMPT` in `prompt.py` is a **100% static string constant** -- no f-strings, no `os.environ`, no `datetime`, no variables of any kind. This is deliberate: Ollama reuses KV cache when the system prompt is byte-identical across requests. Dynamic info (CWD, date, shell, platform) is injected as the first user message in `main.py`. Breaking this invariant degrades performance.

The prompt is adapted from Claude Code's `src/constants/prompts.ts` and `src/tools/*/prompt.ts`. Changes must be validated against the Claude Code source (see memory file `reference_claude_code.md` for the local path).

### Tool System

All tools inherit `BaseTool` (in `tools/base.py`) which defines:
- `name: str` -- tool identifier used in JSON dispatch
- `execute(params: dict) -> ToolResult` -- does the work
- `validate(params: dict) -> str | None` -- optional pre-execution check

The registry in `tools/__init__.py` handles dispatch, validation, output truncation (at `TOOL_OUTPUT_MAX_CHARS`), and error wrapping. Tools are registered in `main.py` -- `BashTool` is always registered; the other 6 (read_file, write_file, edit_file, glob, grep, list_dir) are loaded dynamically via `importlib` so missing dependencies don't crash the app.

### Tool Call Format

Models emit tool calls as ` ```tool_call ` markdown code blocks (not XML, not function_call). This format was chosen in Phase 0 after validation against Gemma 3 27B's natural output patterns. The parser in `parser.py` uses a single regex (`TOOL_CALL_RE`) to extract them. Results return as `<tool_result>` XML tags (system-generated, not model-generated).

### Graceful Degradation

`main.py` wraps `rich`, `prompt_toolkit`, and `sqlite3` imports in try/except. The app runs in plain-text mode with zero optional dependencies -- only `requests` is required. Each optional feature has an independent `_HAS_*` / `_RICH` flag.

### 3-Tier Context Management

Managed in `conversation.py` with thresholds from Claude Code:
1. **55%** -- `clear_old_tool_results()`: replace old `<tool_result>` messages with stubs (no API call)
2. **65%** -- `compact()` in `compaction.py`: send conversation to LLM for 9-section structured summary
3. **85%** -- `emergency_truncate()`: keep only last 20 messages (fallback if compaction fails)

### Skill System

Skills in `skills.py` are prompt templates registered with `register_skill(name, desc, prompt)`. They activate via `/command` in the REPL. The skill prompt replaces the user input and falls through to normal message handling. No separate dispatch path.

### Model Routing

The default model is set via `SHADOW_MODEL` env var (default: `shadow-gemma:latest`). Compaction uses `SHADOW_COMPACTION_MODEL` which can be a smaller, faster model since it only summarizes.

| Task Complexity | Recommended Models | Rationale |
|----------------|-------------------|-----------|
| Simple file ops (read, ls, grep) | `gemma3:4b`, `qwen3:4b` | Fast, low memory, sufficient for tool dispatch |
| Standard coding (edit, debug, test) | `gemma3:27b`, `qwen3:14b` | Good speed/reasoning balance |
| Complex reasoning (architecture, multi-step) | `gemma3:27b`, `deepseek-r1:32b` | Multi-file refactoring, deep analysis |
| Compaction/summary | `gemma3:4b`, `qwen3:4b` | Only needs to summarize, not reason |

```bash
SHADOW_MODEL=gemma3:4b shadow-code              # lightweight
SHADOW_MODEL=deepseek-r1:32b shadow-code         # deep reasoning
SHADOW_COMPACTION_MODEL=gemma3:4b shadow-code     # fast compaction
```

## Key Invariants

- **Config centralization**: all limits, timeouts, and URLs live in `config.py` as module-level constants. Environment overrides: `OLLAMA_HOST`, `SHADOW_MODEL`.
- **Safety before execution**: bash commands pass through `safety.check_destructive()` (14 regex patterns) before execution. Interactive commands (vim, nano, etc.) are blocked in `BashTool.validate()`.
- **ToolContext sharing**: `tool_context.py` holds shared state (CWD, set of read files) passed to all tool constructors. `edit_file` and `write_file` enforce read-before-write via `ctx.was_file_read()`.
- **Coverage floor**: 80% enforced via `pyproject.toml` `[tool.coverage.report] fail_under`. The `main()` REPL loop and `except ImportError` blocks are excluded from coverage calculation.
