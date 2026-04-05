# Shadow Code v2 -- სრულყოფილი იმპლემენტაციის გეგმა

> **Version:** 2.0 | **Date:** 2026-04-05
> **Status:** FINAL -- Reviewed by 5-Eye Team
> **Previous:** PLAN.md (v1) -> CHALLENGE.md -> this revision

---

## რა შეიცვალა v1-დან

| # | v1 ხარვეზი | v2 გამოსწორება |
|---|-----------|---------------|
| C1 | Prompt placeholder-ებით | სრული prompt ტექსტი სიტყვა-სიტყვით |
| C2 | Tool call ფორმატი არატესტირებული | ფაზა 0: ემპირიული ვალიდაცია |
| C3 | Streaming აჩვენებს raw JSON-ს | Streaming buffer + tool call detection |
| C4 | Token estimation არასანდო | Ollama prompt_eval_count-ზე დაფუძნებული |
| C5 | Tool results user როლით | კონტექსტის მინიშნება prefix-ით |
| C6 | Phase 0 არ არსებობდა | Phase 0: Validation დამატებული |
| C7 | shell=True undocumented | შეგნებული არჩევანი + interactive detection |
| H1 | cd არ მუშაობს bash-ში | CWD tracking bash.py-ში |
| H4 | pathlib.glob ნელი .git-ში | os.walk-ზე გადასვლა |
| H5 | edit_file blind edits | file-must-be-read tracking |
| H7 | infinite error loop | consecutive error counter |
| H8 | grep fallback ნელი | ripgrep -> system grep -> python chain |
| H9 | few-shot არ არის | 2 სრული few-shot მაგალითი prompt-ში |

---

## 1. პროექტის აღწერა

**shadow-code** -- Python CLI აპლიკაცია (coding assistant), რომელიც:
- ლოკალურ shadow-gemma:latest მოდელს (Ollama) იყენებს
- Claude Code-ის საუკეთესო prompt-ებს და workflow-ს ადაპტირებს
- 7 ინსტრუმენტს (bash, read_file, edit_file, write_file, glob, grep, list_dir) ასრულებს prompt-based tool calling-ით
- ქართულ და ინგლისურ ენებზე მუშაობს

---

## 2. გადამოწმებული ფაქტები

| პარამეტრი | მნიშვნელობა | წყარო |
|-----------|------------|-------|
| არქიტექტურა | Gemma 3, 27.4B, Q4_K_M | `ollama show` |
| ზომა | ~17GB | `ollama list` |
| Context window | 131,072 (128K) | `ollama show` -> context_length |
| Vision | დიახ (არ ვიყენებთ) | `ollama show` -> capabilities |
| Native tool calling | **არა** | API ტესტი: does not support tools |
| JSON output | შესაძლებელი | ტესტით დადასტურდა |
| Template | `<start_of_turn>user/model` | Modelfile |
| Stop token | `<end_of_turn>` | Modelfile |
| Temperature | 0.9 (Modelfile default) | Modelfile |
| Ollama API | `http://localhost:11434/api/chat` | სტანდარტული |

---

## 3. არქიტექტურა

```
+------------------+     +----------------+     +-------------+
|                  |     |                |     |             |
|   main.py        |---->| ollama_client  |---->|  Ollama API |
|   (REPL loop)    |     | (streaming)    |     |  (local)    |
|                  |<----| (buffer)       |<----|             |
+--------+---------+     +----------------+     +-------------+
         |
         | tool calls detected
         v
+--------+---------+
|   parser.py      |  <-- regex + JSON validate
+--------+---------+
         |  dispatch
         v
+--------+---------+     +------------------+
|   tools/         |---->|  subprocess      |
|   (registry)     |     |  filesystem      |
|   bash, read,    |     |  pathlib/re      |
|   edit, write,   |     +------------------+
|   glob, grep,    |
|   list_dir       |
+------------------+

+------------------+     +------------------+
|  conversation.py |     |  display.py      |
|  (history,       |     |  (streaming      |
|   tokens,        |     |   buffer,        |
|   truncation)    |     |   terminal UI)   |
+------------------+     +------------------+
```

### პროექტის ფაილური სტრუქტურა

```
shadow-code/
+-- pyproject.toml
+-- shadow_code/
|   +-- __init__.py
|   +-- main.py            # Entry point, REPL, signals
|   +-- config.py           # Constants, env overrides
|   +-- ollama_client.py    # Streaming API client
|   +-- prompt.py           # System prompt (FULL TEXT)
|   +-- parser.py           # Tool call detection
|   +-- conversation.py     # History, tokens, truncation
|   +-- display.py          # Streaming buffer, terminal UI
|   +-- tools/
|       +-- __init__.py     # Registry, dispatch
|       +-- base.py         # BaseTool, ToolResult
|       +-- bash.py         # Shell (CWD tracking)
|       +-- read_file.py    # File read (line numbers)
|       +-- edit_file.py    # String replacement
|       +-- write_file.py   # File create/overwrite
|       +-- glob_tool.py    # Pattern match (os.walk)
|       +-- grep_tool.py    # Search (rg/grep/python)
|       +-- list_dir.py     # Directory listing
+-- tests/
    +-- test_parser.py
```

---

## 4. ფაზა 0: ემპირიული ვალიდაცია (კოდის წინ)

**მიზანი:** დავადასტუროთ shadow-gemma-ს tool call ფორმატის საიმედოობა.

### ტესტი 0.1: ფორმატის არჩევა

3 ფორმატი, 5-ჯერ თითოეული. curl-ით, `stream: false`, `temperature: 0.3`.

**A: XML** -- `<tool_call>{...JSON...}</tool_call>`
**B: Markdown** -- triple-backtick tool_call block
**C: Custom** -- `---TOOL_CALL---` / `---END_CALL---`

ტესტის მეთოდი:
```bash
curl -s http://localhost:11434/api/chat -d '{
  "model": "shadow-gemma:latest",
  "messages": [
    {"role": "system", "content": "[prompt with format X + examples]"},
    {"role": "user", "content": "list files in current directory"}
  ],
  "stream": false,
  "options": {"temperature": 0.3, "num_ctx": 8192}
}'
```

შეფასება: ფორმატის სიზუსტე (5/5), JSON ვალიდურობა, tool/params სისწორე.

### ტესტი 0.2: Multi-turn tool calling

3-turn საუბარი -- მოდელი ინარჩუნებს ფორმატს მეორე/მესამე turn-ზე?

### ტესტი 0.3: Few-shot vs Zero-shot

10 ტესტი მაგალითებით vs 10 მაგალითების გარეშე.

### ტესტი 0.4: Temperature ოპტიმიზაცია

0.1, 0.3, 0.5, 0.7 -- რომელი ყველაზე საიმედო?

### ტესტი 0.5: Prompt სიგრძის გავლენა

მოკლე (~2K char) vs სრული (~5K char) prompt. ხარისხი იგივეა?

**შედეგი:** `VALIDATION_RESULTS.md` -- არჩეული ფორმატი, temperature, ტესტების შედეგები.

---

## 5. ფაზა 1: მინიმალური სამუშაო ვერსია

**მიზანი:** გაშვება -> შეკითხვა -> bash tool -> პასუხი (end-to-end loop)

### ფაილი 1: `pyproject.toml`

```toml
[project]
name = "shadow-code"
version = "0.1.0"
description = "Local AI coding assistant powered by shadow-gemma"
requires-python = ">=3.10"
dependencies = ["requests>=2.31.0"]

[project.optional-dependencies]
full = ["rich>=13.0.0", "prompt_toolkit>=3.0.0"]

[project.scripts]
shadow-code = "shadow_code.main:main"
```

### ფაილი 2: `shadow_code/config.py`

```python
import os

OLLAMA_BASE_URL = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_CHAT_ENDPOINT = f"{OLLAMA_BASE_URL}/api/chat"
MODEL_NAME = os.environ.get("SHADOW_MODEL", "shadow-gemma:latest")

CONTEXT_WINDOW = 131_072
TRUNCATION_THRESHOLD_RATIO = 0.75
MAX_OUTPUT_TOKENS = 8_192

MAX_TOOL_TURNS = 20
MAX_CONSECUTIVE_ERRORS = 3
TOOL_OUTPUT_MAX_CHARS = 30_000
TOOL_OUTPUT_TRUNCATE_HEAD = 14_000
TOOL_OUTPUT_TRUNCATE_TAIL = 14_000

BASH_DEFAULT_TIMEOUT = 120
BASH_MAX_TIMEOUT = 600
INTERACTIVE_COMMANDS = {"vim", "vi", "nano", "less", "more", "top", "htop", "man"}

MAX_LINES_TO_READ = 2000
BLOCKED_PATHS = {"/dev/zero", "/dev/urandom", "/dev/random", "/dev/stdin"}

MODEL_OPTIONS = {"temperature": 0.3, "num_ctx": CONTEXT_WINDOW}
```

### ფაილი 3: `shadow_code/prompt.py` -- პროექტის გული

**ეს არის ყველაზე კრიტიკული ფაილი.** სრული prompt ტექსტი, არანაირი placeholder.

Python ფაილის სტრუქტურა:

```python
import os, platform
from datetime import datetime

def get_system_prompt(working_directory: str) -> str:
    env_block = (
        "# Environment\n"
        f"- Working directory: {working_directory}\n"
        f"- Platform: {platform.system()} {platform.release()}\n"
        f"- Shell: {os.environ.get('SHELL', '/bin/bash')}\n"
        f"- Date: {datetime.now().strftime('%Y-%m-%d')}"
    )
    return SYSTEM_PROMPT + "\n\n" + env_block + "\n\n" + LANGUAGE_BLOCK

LANGUAGE_BLOCK = (
    "# Language\n"
    "Respond in the same language the user writes in. "
    "You understand Georgian and English. "
    "Technical terms and code identifiers remain in English."
)

SYSTEM_PROMPT = r\'\'\'...the full text below...\'\'\'
```

**SYSTEM_PROMPT -- სრული ტექსტი (ყოველი სიტყვა ზუსტად ასე გადაეცემა მოდელს):**

```text
You are Shadow, a local AI coding assistant. You help users with software
engineering tasks by using the tools available to you.

IMPORTANT: Assist with authorized security testing, defensive security, CTF
challenges, and educational contexts. Refuse requests for destructive
techniques, DoS attacks, mass targeting, supply chain compromise, or detection
evasion for malicious purposes. Dual-use security tools require clear
authorization context.

# System
- All text you output outside of tool calls is displayed to the user. Use
  Github-flavored markdown for formatting.
- When you need to perform an action, use a tool call.
- Tool results will be returned to you in <tool_result> tags. Use them to
  continue working on the user's task.
- Do not fabricate tool results or file contents. If you need information,
  use a tool to get it.

# Tool Calling Format

To use a tool, write:

<tool_call>
{"tool": "tool_name", "params": {"param1": "value1"}}
</tool_call>

Rules:
- JSON must have exactly two keys: "tool" (string) and "params" (object).
- You may include text before or after a tool call.
- You may make multiple tool calls in one response.
- NEVER write <tool_call> in explanations or examples. Only use it to
  actually invoke a tool.
- Always use valid JSON with double-quoted keys.

## Example 1: Reading a file

User: "show me main.py"

Assistant:
Let me read that file.

<tool_call>
{"tool": "read_file", "params": {"file_path": "/home/user/project/main.py"}}
</tool_call>

[Tool result arrives]

Assistant:
Here is main.py:
[shows content and explains]

## Example 2: Running a command then using the result

User: "what git branch am I on?"

Assistant:

<tool_call>
{"tool": "bash", "params": {"command": "git branch --show-current"}}
</tool_call>

[Tool result arrives: main]

Assistant:
You are on the `main` branch.

# Available Tools

## bash
Executes a bash command and returns its output.

Parameters:
- command (required): The shell command to execute.
- timeout (optional): Timeout in seconds. Default 120, max 600.

Usage:
- The working directory persists between commands but shell state does not.
- Avoid using bash to read files, search code, or edit files when dedicated
  tools (read_file, grep, edit_file) can do it.
- For commands that may hang (vim, less, top), this tool will reject them.
- Try to maintain the working directory by using absolute paths.

## read_file
Reads a file from the local filesystem with line numbers.

Parameters:
- file_path (required): Absolute path to the file.
- offset (optional): Line number to start from (1-based). Default: 1.
- limit (optional): Number of lines to read. Default: 2000.

Usage:
- The file_path must be an absolute path, not relative.
- Results are returned in cat -n format with line numbers starting at 1.
- When you already know which part of the file you need, use offset/limit.
- This tool can only read files, not directories.

## edit_file
Performs exact string replacement in a file.

Parameters:
- file_path (required): Absolute path to the file.
- old_string (required): The exact text to find and replace.
- new_string (required): The replacement text.
- replace_all (optional): Replace all occurrences. Default: false.

Usage:
- You must read the file with read_file before editing it.
- Preserve the exact indentation from the file when specifying old_string.
- The edit will FAIL if old_string is not unique. Provide more context
  to make it unique, or use replace_all.
- Prefer editing existing files over creating new ones.

## write_file
Creates a new file or overwrites an existing file.

Parameters:
- file_path (required): Absolute path to the file.
- content (required): The full content to write.

Usage:
- If this is an existing file, you must read it first with read_file.
- This tool overwrites the entire file. Prefer edit_file for modifications.
- Only use write_file to create new files or for complete rewrites.
- Parent directories will be created automatically.

## glob
Fast file pattern matching. Finds files by name patterns.

Parameters:
- pattern (required): Glob pattern, e.g. "**/*.py" or "src/**/*.ts".
- path (optional): Base directory to search. Default: working directory.

Usage:
- Returns matching file paths sorted by modification time.
- Use this when you need to find files by name or extension.

## grep
Searches file contents using regex patterns.

Parameters:
- pattern (required): Regex pattern to search for.
- path (optional): Directory to search in. Default: working directory.
- glob (optional): File filter, e.g. "*.py".
- case_insensitive (optional): Default false.
- max_results (optional): Default 250.

Usage:
- Use grep for content search instead of bash grep or rg.
- Supports full regex syntax.
- Output format: file:line_number:matched_line.

## list_dir
Lists directory contents with file types and sizes.

Parameters:
- path (optional): Directory path. Default: working directory.

Usage:
- Shows directories first, then files.
- Includes file sizes.

# Doing Tasks
- Users primarily request software engineering tasks: solving bugs, adding
  features, refactoring, explaining code.
- Do not propose changes to code you have not read. Read files first.
- Do not add features, refactor, or make improvements beyond what was asked.
  A bug fix does not need surrounding code cleaned up.
- Do not add error handling or validation for scenarios that cannot happen.
- Do not create helpers or abstractions for one-time operations. Three
  similar lines are better than a premature abstraction.
- Prefer editing existing files over creating new ones.
- If an approach fails, diagnose why before switching tactics. Read the
  error, check assumptions, try a focused fix.

# Executing Actions with Care
- Consider the reversibility and blast radius of actions.
- For local, reversible actions (editing files, running tests) -- proceed.
- For hard-to-reverse or destructive actions (rm -rf, force-push, dropping
  tables) -- ask the user for confirmation first.
- When you encounter an obstacle, do not use destructive actions as a
  shortcut. Investigate root causes instead.

# Using Your Tools
- Do NOT use bash when a dedicated tool can do the job:
  - To read files: use read_file, not cat/head/tail
  - To edit files: use edit_file, not sed/awk
  - To create files: use write_file, not echo/cat redirect
  - To find files: use glob, not find/ls
  - To search content: use grep, not bash grep/rg
- Reserve bash for system commands and terminal operations.
- You can make multiple tool calls in one response. If they are
  independent, make them all at once.

# Tone and Style
- Do not use emojis unless the user asks for them.
- Keep responses short and concise.
- When referencing code, include the file path and line number.

# Output Efficiency
Go straight to the point. Try the simplest approach first. Be concise.
Lead with the answer or action, not the reasoning. Skip filler words.
If you can say it in one sentence, do not use three.
```

**Prompt-ის სავარაუდო ზომა:** ~3,800 სიმბოლო (~1,200 tokens). 128K context-ის ~1%-ს იკავებს.
