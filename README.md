# shadow-code

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Ollama](https://img.shields.io/badge/Ollama-local%20LLM-orange.svg)](https://ollama.com)

> Local AI coding assistant -- Claude Code's prompts and tools adapted for your own LLM

You have a local LLM running on Ollama. **shadow-code** gives it the same coding workflow as Claude Code: tool calling, file editing, git safety, context management -- all running on your machine, no API keys, no cloud.

## Quick Start

```bash
# Install
pip install -e .

# Optional: Rich UI + prompt_toolkit
pip install rich prompt_toolkit

# Run (from any directory)
shadow-code
```

## What It Does

```
shadow> find all python files with syntax errors

  > grep syntax error **/*.py
    src/parser.py:45: syntax error near "def"

  > read_file src/parser.py
    ...line 45 shown with context...

  > edit_file src/parser.py
    Fixed: missing colon after function definition

  [===========--------] 45K/131K (34%)
```

shadow-code sends your question to the local LLM, which decides what tools to use, executes them, reads the results, and continues until the task is done.

## Features

| Feature | Description |
|---------|-------------|
| **7 Tools** | bash, read_file, edit_file, write_file, glob, grep, list_dir |
| **13 Skills** | /commit, /review, /debug, /test, /refactor, /explain, and more |
| **Context Management** | 3-tier: result clearing, LLM compaction, emergency truncate |
| **Git Safety** | Never skips hooks, never force pushes, never amends without asking |
| **Destructive Warnings** | Confirms before rm -rf, git reset --hard, drop table |
| **Session Persistence** | Save/load conversations with SQLite |
| **Georgian + English** | Responds in the language you write in |
| **Rich UI** | Markdown rendering, spinners, color-coded context bar |

## Commands

```
/help          Show all commands
/clear         Clear conversation
/tokens        Show context usage
/info          Session info
/cd [path]     Change working directory
/compact       Manually compact conversation
/history       Show recent messages
/save [name]   Save session
/load [id]     Load session
/list          List saved sessions
/skills        List available skills
/version       Version info
/exit          Exit
```

## Skills

```
/commit        Create a git commit
/pr            Create a pull request
/review        Review code for bugs and security
/simplify      Review for code quality
/test          Run tests and analyze results
/debug         Debug an error
/explain       Explain code in detail
/refactor      Refactor while preserving behavior
/search        Deep codebase search
/verify        Verify changes actually work
/init          Explore a new project
/remember      Save info for later
/stuck         Get help when stuck
```

## Requirements

- Python 3.10+
- [Ollama](https://ollama.com) with a local model
- Default model: `shadow-gemma:latest` (configurable via `SHADOW_MODEL` env var)

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `SHADOW_MODEL` | `shadow-gemma:latest` | Ollama model to use |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama API URL |

## Architecture

```
shadow-code/
  shadow_code/
    main.py           Entry point, REPL, context management
    prompt.py          System prompt (Claude Code adapted, 17K chars)
    parser.py          Tool call detection (```tool_call format)
    ollama_client.py   Ollama API streaming client
    conversation.py    Message history, 3-tier context management
    display.py         Streaming buffer (hides tool JSON from user)
    compaction.py      LLM-based conversation summarization
    skills.py          Skill system (/commit, /review, etc.)
    safety.py          Destructive command detection
    ui.py              Rich terminal rendering
    streaming.py       Rich Live streaming display
    repl.py            prompt_toolkit REPL with history
    db.py              SQLite session persistence
    tool_context.py    Shared state (CWD, read files)
    tools/
      bash.py          Shell commands with CWD tracking
      read_file.py     File reading with line numbers
      edit_file.py     Exact string replacement
      write_file.py    File creation/overwrite
      glob_tool.py     File pattern matching
      grep_tool.py     Content search (rg -> grep -> python)
      list_dir.py      Directory listing
```

## How It Works

1. **System prompt** (adapted from Claude Code) tells the LLM about available tools, coding best practices, and behavioral rules
2. **Tool calling** uses ` ```tool_call ` markdown format (validated with the actual model)
3. **Context management** follows Claude Code's pattern: clear old results at 55%, LLM summarization at 65%, emergency truncate at 85%
4. **KV cache** optimization: system prompt is 100% static for Ollama cache hits

## License

[MIT](LICENSE)
