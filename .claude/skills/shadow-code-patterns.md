---
name: shadow-code-patterns
description: Coding patterns and conventions extracted from the shadow-code repository
version: 1.0.0
source: local-git-analysis
analyzed_commits: 24
---

# Shadow Code Patterns

## Project Identity

Shadow Code is a local AI coding assistant CLI built in Python that mirrors Claude Code's architecture and UX but runs against a local Ollama model. The system prompt (`prompt.py`) is the project's heart -- it must match Claude Code's coverage 1:1 for all applicable sections.

## Commit Conventions

This project uses **imperative, descriptive commit messages** without conventional commit prefixes:

- Phase milestones: `Phase N COMPLETE: <summary of what was built>`
- Feature additions: `Add <feature>` or `Complete <feature>`
- Bug fixes: `Fix <what was broken>` or `Fix N bugs: <details>`
- Refinements: `Improve <what>` or `<module> REWRITTEN: <why>`
- Preparation: `Prepare for <what>: <details>`

Commit messages include specifics (e.g. "Fix 2 critical bugs: skill dispatch + streaming display").

**Only 4% of commits use conventional commit format.** The project prefers descriptive natural-language messages.

## Code Architecture

```
shadow_code/
  __init__.py          # Package marker
  config.py            # Constants: model, context window, timeouts, limits
  main.py              # REPL orchestrator -- imports & wires all modules
  prompt.py            # THE HEART: static SYSTEM_PROMPT constant (no f-strings)
  parser.py            # tool_call markdown block parser (regex-based)
  conversation.py      # Message history with context management
  compaction.py        # 3-tier context management (result clearing, compaction, truncate)
  ollama_client.py     # Ollama HTTP streaming client
  display.py           # Stream display with Rich fallback
  streaming.py         # Rich Live streaming controller
  ui.py                # Rich panels, markdown rendering
  repl.py              # prompt_toolkit REPL (history, multiline, completion)
  db.py                # SQLite session persistence
  safety.py            # Destructive command detection (14 patterns)
  skills.py            # /command skill registry and built-in skills
  tool_context.py      # Shared tool state (cwd, read_files)
  tools/
    __init__.py        # Registry: register(), dispatch(), format_result()
    base.py            # BaseTool ABC + ToolResult dataclass
    bash.py            # Shell execution with cwd tracking, timeout, stderr
    read_file.py       # File reading with line numbers
    write_file.py      # File creation/overwrite
    edit_file.py       # String replacement editing
    glob_tool.py       # File pattern matching
    grep_tool.py       # Content search (regex)
    list_dir.py        # Directory listing
tests/
  test_parser.py       # 41 unit tests (parser, conversation, context, registry, bash)
docs/
  PLAN.md, PLAN_v2.md, PLAN_FINAL.md  # Evolution of architecture plans
  ROLE.md              # Project role definition
  CHALLENGE.md         # Design challenges and solutions
  WORKFLOW.md          # Multi-agent workflow used during development
  VALIDATION_RESULTS.md # Phase 0 format validation
  VECMEM_ANALYSIS.md   # Vector memory analysis
```

## Key Design Patterns

### 1. Tool Registry Pattern

Tools register into a global `_REGISTRY` dict via `register(tool)`. Dispatch is centralized through `dispatch(name, params) -> ToolResult`. Every tool inherits `BaseTool(ABC)` with `name`, `execute()`, and optional `validate()`.

```python
# Adding a new tool:
class MyTool(BaseTool):
    name = "my_tool"
    def execute(self, params: dict) -> ToolResult:
        return ToolResult(True, "output")
    def validate(self, params: dict) -> str | None:
        if "required_key" not in params:
            return "Missing required_key"
        return None
```

### 2. Graceful Degradation

`main.py` wraps optional imports in try/except blocks. The app runs in plain-text mode if `rich` or `prompt_toolkit` are not installed. Features degrade independently:

```python
try:
    from .ui import UIRenderer, HAS_RICH
    _RICH = HAS_RICH
except ImportError:
    _RICH = False
```

### 3. Static System Prompt

`prompt.py` uses a module-level string constant `SYSTEM_PROMPT` with zero dynamic content. Dynamic info (CWD, date, shell) is injected as the first user message in `main.py`. This ensures Ollama KV cache hits across requests.

### 4. Tool Call Format

Models output tool calls as markdown code blocks with the `tool_call` language tag:

````
```tool_call
{"tool": "bash", "params": {"command": "ls"}}
```
````

Results return as XML-like tags:
```
<tool_result tool="bash" success="true">
...output...
</tool_result>
```

### 5. 3-Tier Context Management

1. **Result clearing**: Replace old tool results with "[cleared to save context]"
2. **Compaction**: Summarize conversation when approaching context limits
3. **Emergency truncate**: Keep only `KEEP_RECENT_MESSAGES` when critically low

### 6. Skill System

Skills are prompt templates registered with `register_skill(name, description, prompt)`. Activated via `/command` in the REPL. Each skill guides the model through a specific workflow using available tools.

## Workflows

### Adding a New Tool

1. Create `shadow_code/tools/my_tool.py` inheriting `BaseTool`
2. Implement `name`, `execute()`, and optionally `validate()`
3. Register in `main.py` via `tool_reg.register(MyTool(ctx))`
4. Add tool documentation to `prompt.py` SYSTEM_PROMPT
5. Add tests in `tests/test_tools.py`

### Adding a New Skill

1. Add `register_skill("name", "description", """prompt template""")` in `skills.py`
2. Reference available tools in the prompt template
3. No registration in main.py needed -- skills auto-load with the module

### Modifying the System Prompt

**CRITICAL**: `prompt.py` is the heart of the project.
- Must remain 100% static (no f-strings, no variables, no dynamic content)
- Must match Claude Code coverage for all applicable sections
- Changes must be validated against Claude Code source
- Dynamic info goes in main.py's first user message, NOT in the prompt

## Testing Patterns

- **Framework**: `unittest` (standard library, no external dependency)
- **Test location**: `tests/test_parser.py` (single file currently)
- **Structure**: `TestCase` classes grouped by module/concern
- **Run**: `python3 -m pytest tests/`
- **Coverage**: Parser (14 tests), Conversation (5), ToolContext (3), ToolRegistry (5), BashTool (9) = 41 total
- **Gap**: Only parser, conversation, tool_context, registry, and bash tool are tested. 12+ modules untested.

## Configuration Pattern

All config lives in `config.py` as module-level constants. Environment variables override defaults:

```python
OLLAMA_BASE_URL = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
MODEL_NAME = os.environ.get("SHADOW_MODEL", "shadow-gemma:latest")
```

## File Co-Change Patterns

Files that frequently change together (from git history):
- `main.py` + `ui.py` (UI changes require orchestrator updates)
- `main.py` + `streaming.py` (display pipeline)
- `prompt.py` alone (prompt is self-contained, changed independently)
- `skills.py` + `config.py` + `main.py` (new features wire through all three)
