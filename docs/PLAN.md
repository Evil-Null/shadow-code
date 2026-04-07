# Shadow Code - სრული იმპლემენტაციის გეგმა

## პროექტის აღწერა

**shadow-code** - Python CLI აპლიკაცია, რომელიც Claude Code-ის პროფესიონალურ prompt-ებს, tool სისტემას და საუკეთესო პრაქტიკებს ადაპტირებს ლოკალური `shadow-gemma:latest` მოდელისთვის (Ollama).

---

## გადამოწმებული ფაქტები (shadow-gemma:latest)

| პარამეტრი | მნიშვნელობა | წყარო |
|-----------|------------|-------|
| არქიტექტურა | Gemma 3 | `ollama show shadow-gemma:latest` |
| პარამეტრები | 27.4B | `ollama show` |
| კვანტიზაცია | Q4_K_M | `ollama show` |
| ზომა | ~17GB | `ollama list` |
| Context window | 131,072 (128K) | `ollama show` → `context_length` |
| Vision | დიახ | `ollama show` → capabilities: `vision` |
| Native tool calling | **არა** | API ტესტი → `"does not support tools"` |
| JSON output | დიახ | ტესტით დადასტურდა |
| ქართული ენა | მხარდაჭერილი | არსებული system prompt-ში |
| Template ფორმატი | `<start_of_turn>user` / `<start_of_turn>model` | Modelfile |
| Stop token | `<end_of_turn>` | Modelfile |
| Ollama API | `http://localhost:11434/api/chat` | სტანდარტული |
| Temperature | 0.9 (ამჟამად) | Modelfile |

---

## Claude Code-ის არქიტექტურა (კვლევის შედეგი)

### სისტემური prompt-ის სტრუქტურა

Claude Code-ის სისტემური prompt აწყობილია **მოდულურად** - ცალკეული სექციები, რომლებიც შეერთებულია ერთ prompt-ად. ფაილი: `src/constants/prompts.ts` (915 ხაზი).

**სტატიკური სექციები** (ყოველთვის იგივე):
1. **Intro** - იდენტობა + უსაფრთხოების ინსტრუქცია (CYBER_RISK_INSTRUCTION)
2. **System** - ზოგადი სისტემური წესები (markdown, permissions, hooks, compression)
3. **Doing Tasks** - კოდირების სტილი და ქცევის წესები
4. **Actions** - უსაფრთხო მოქმედებების ინსტრუქციები (reversibility, blast radius)
5. **Using Your Tools** - ინსტრუმენტების გამოყენების წესები
6. **Tone and Style** - კომუნიკაციის სტილი
7. **Output Efficiency** - ლაკონიურობის ინსტრუქცია

**დინამიკური სექციები** (სესიაზე დამოკიდებული):
8. **Session Guidance** - სესიის სპეციფიკური ინსტრუქციები
9. **Memory** - მეხსიერების სისტემა
10. **Environment Info** - CWD, OS, git status
11. **Language** - ენის პრეფერენცია
12. **Scratchpad** - დროებითი ფაილების დირექტორია

### ინსტრუმენტთა სისტემა

Claude Code-ში **44+ ინსტრუმენტი** არის. თითოეულს აქვს:
- `prompt.ts` - ინსტრუქცია მოდელისთვის (როგორ გამოიყენოს)
- `inputSchema` - Zod schema შეტანის ვალიდაციისთვის
- `outputSchema` - გამოტანის ვალიდაცია
- `call()` - შესრულების ლოგიკა
- `checkPermissions()` - უფლებების შემოწმება

**ჩვენთვის საჭირო 7 ინსტრუმენტი:**

| # | Tool | Claude Code ეკვივალენტი | ფაილი |
|---|------|------------------------|-------|
| 1 | `bash` | BashTool | `src/tools/BashTool/` |
| 2 | `read_file` | FileReadTool | `src/tools/FileReadTool/` |
| 3 | `edit_file` | FileEditTool | `src/tools/FileEditTool/` |
| 4 | `write_file` | FileWriteTool | `src/tools/FileWriteTool/` |
| 5 | `glob` | GlobTool | `src/tools/GlobTool/` |
| 6 | `grep` | GrepTool | `src/tools/GrepTool/` |
| 7 | `list_dir` | (Bash `ls`) | N/A |

### API კომუნიკაცია

Claude Code იყენებს Anthropic SDK-ს streaming-ით:
```
anthropic.beta.messages.create({ stream: true, ... })
```
ჩვენ გამოვიყენებთ Ollama API-ს:
```
POST http://localhost:11434/api/chat { "model": "shadow-gemma:latest", "stream": true, ... }
```

---

## მთავარი არქიტექტურული გადაწყვეტილებები

### 1. Tool Calling ფორმატი

**პრობლემა:** shadow-gemma-ს არ აქვს native tool calling. Ollama API აბრუნებს: `"does not support tools"`.

**გადაწყვეტა:** Prompt-based tool calling `<tool_call>` ტეგებით.

მოდელი ინსტრუმენტს ასე გამოიძახებს:
```
ვნახოთ რა ფაილები გვაქვს.

<tool_call>
{"tool": "bash", "params": {"command": "ls -la"}}
</tool_call>
```

სისტემა შედეგს ასე დააბრუნებს:
```
<tool_result tool="bash" success="true">
total 48
drwxr-xr-x 5 user user 4096 Apr 5 10:00 .
drwxr-xr-x 3 user user 4096 Apr 4 09:00 ..
-rw-r--r-- 1 user user 1234 Apr 5 09:30 main.py
</tool_result>
```

შეცდომის შემთხვევაში:
```
<tool_result tool="read_file" success="false">
Error: File not found: /path/to/nonexistent.py
</tool_result>
```

**რატომ ეს ფორმატი:**
- `<tool_call>` / `<tool_result>` ტეგები უნიკალურია - ჩვეულებრივ ტექსტში არ გამოჩნდება
- JSON ობიექტი მარტივია 27B მოდელისთვის
- regex-ით ადვილად ამოიცნობა: `<tool_call>\s*(\{.*?\})\s*</tool_call>`
- რამდენიმე tool call ერთ პასუხში - რამდენიმე `<tool_call>` ბლოკი

### 2. Temperature

**ამჟამინდელი:** 0.9 (Modelfile-ში)
**რეკომენდაცია:** 0.3-0.5 კოდირებისთვის (precision > creativity)
**გადაწყვეტა:** API-ში გადავცემთ `"options": {"temperature": 0.4}`, Modelfile არ შევეხებით

### 3. Context Window ბიუჯეტი

მთლიანი: **128K tokens** (~512K სიმბოლო)

| კომპონენტი | ტოკენები | სიმბოლოები |
|-----------|---------|-----------|
| სისტემური prompt | ~4,000 | ~16,000 |
| Tool აღწერები prompt-ში | ~2,000 | ~8,000 |
| მოდელის პასუხის რეზერვი | ~8,000 | ~32,000 |
| საუბრის ისტორია | ~114,000 | ~456,000 |
| **Truncation ზღვარი** | **100,000** | - |

Truncation სტრატეგია: როცა ისტორია 100K ტოკენს გადააჭარბებს, ძველი მესიჯები (პირველიდან) იშლება, ბოლო 20 შენარჩუნდება.

---

## პროექტის სტრუქტურა

```
/home/n00b/makho/shadow-code/
├── PLAN.md                      # ეს ფაილი
├── pyproject.toml               # Python პაკეტის კონფიგურაცია
├── shadow_code/
│   ├── __init__.py              # პაკეტი + ვერსია
│   ├── main.py                  # Entry point, REPL loop
│   ├── config.py                # კონფიგურაცია (model, URL, limits, timeouts)
│   ├── ollama_client.py         # Ollama API კლიენტი (streaming + non-streaming)
│   ├── prompt.py                # სისტემური prompt (Claude Code-დან ადაპტირებული)
│   ├── parser.py                # Tool call-ების ამოცნობა model output-იდან
│   ├── conversation.py          # საუბრის ისტორიის მენეჯმენტი + truncation
│   └── tools/
│       ├── __init__.py          # Tool რეგისტრი, dispatch, ToolResult
│       ├── base.py              # BaseTool აბსტრაქტული კლასი
│       ├── bash.py              # Shell ბრძანებების გაშვება (subprocess)
│       ├── read_file.py         # ფაილების წაკითხვა (line numbers, offset/limit)
│       ├── edit_file.py         # ტექსტის ზუსტი ჩანაცვლება ფაილში
│       ├── write_file.py        # ფაილების შექმნა/გადაწერა
│       ├── glob_tool.py         # ფაილების ძებნა pattern-ით (pathlib.glob)
│       ├── grep_tool.py         # ფაილების შიგთავსის ძებნა (regex, subprocess rg)
│       └── list_dir.py          # დირექტორიის შიგთავსის ჩვენება
```

---

## ფაილ-ფაილად იმპლემენტაციის გეგმა

### ფაზა 1: მინიმალური სამუშაო ვერსია (9 ფაილი)

**მიზანი:** გაშვება → შეკითხვა → bash tool → პასუხი (end-to-end loop)

---

#### ფაილი 1: `pyproject.toml`

```toml
[project]
name = "shadow-code"
version = "0.1.0"
description = "Local AI coding assistant powered by shadow-gemma"
requires-python = ">=3.10"
dependencies = [
    "requests>=2.31.0",
]

[project.optional-dependencies]
rich = ["rich>=13.0.0"]
full = ["rich>=13.0.0", "prompt_toolkit>=3.0.0"]

[project.scripts]
shadow-code = "shadow_code.main:main"
```

**Dependencies:**
- `requests` - HTTP კლიენტი (მსუბუქი, სტანდარტული)
- `rich` (optional) - markdown rendering ტერმინალში
- `prompt_toolkit` (optional) - REPL ისტორია, autocompletion

---

#### ფაილი 2: `shadow_code/__init__.py`

```python
__version__ = "0.1.0"
```

---

#### ფაილი 3: `shadow_code/config.py`

კონსტანტები და კონფიგურაცია:

```python
# Ollama API
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_CHAT_ENDPOINT = f"{OLLAMA_BASE_URL}/api/chat"
MODEL_NAME = "shadow-gemma:latest"

# Context window (shadow-gemma: 128K)
CONTEXT_WINDOW = 131_072
MAX_OUTPUT_TOKENS = 8_192
TRUNCATION_THRESHOLD = 100_000  # tokens, სადაც ისტორიის truncation იწყება
KEEP_RECENT_MESSAGES = 20       # truncation-ის დროს ამდენი ბოლო მესიჯი შენარჩუნდება

# Tool execution
MAX_TOOL_TURNS = 25             # მაქსიმალური თანმიმდევრული tool call turns
TOOL_OUTPUT_MAX_CHARS = 30_000  # tool output-ის მაქსიმალური სიგრძე
TOOL_OUTPUT_HEAD = 15_000       # შეკვეცისას პირველი N სიმბოლო
TOOL_OUTPUT_TAIL = 15_000       # შეკვეცისას ბოლო N სიმბოლო

# Bash tool
BASH_DEFAULT_TIMEOUT = 120      # წამი
BASH_MAX_TIMEOUT = 600          # წამი (10 წუთი)

# Read tool
MAX_LINES_TO_READ = 2000        # default ხაზების რაოდენობა

# Model options (override Modelfile defaults)
MODEL_OPTIONS = {
    "temperature": 0.4,         # precision-oriented (Modelfile-ში 0.9-ია)
    "top_k": 40,
    "top_p": 0.9,
    "num_ctx": CONTEXT_WINDOW,
}
```

---

#### ფაილი 4: `shadow_code/ollama_client.py`

Ollama API კლიენტი.

**ფუნქციონალი:**
- `chat_stream(messages, system_prompt)` → generator, yields ტექსტის ნაწილებს
- `chat(messages, system_prompt)` → სრული პასუხი ერთიანად
- Connection error handling → მკაფიო შეტყობინება
- Timeout handling

**API ფორმატი (Ollama Chat):**
```json
{
  "model": "shadow-gemma:latest",
  "messages": [
    {"role": "system", "content": "...system prompt..."},
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."},
    {"role": "user", "content": "..."}
  ],
  "stream": true,
  "options": {
    "temperature": 0.4,
    "num_ctx": 131072
  }
}
```

**Streaming response ფორმატი:**
```json
{"message": {"role": "assistant", "content": "ტექსტის"}, "done": false}
{"message": {"role": "assistant", "content": " ნაწილი"}, "done": false}
{"message": {"role": "assistant", "content": ""}, "done": true, "eval_count": 150, "prompt_eval_count": 3200}
```

**მნიშვნელოვანი:** `eval_count` = output tokens, `prompt_eval_count` = input tokens. ეს მნიშვნელობები truncation-ის ლოგიკისთვის არის საჭირო.

---

#### ფაილი 5: `shadow_code/prompt.py`

სისტემური prompt - Claude Code-ის prompt-ებიდან ადაპტირებული.

**წყაროები და რა ვიღებთ თითოეულიდან:**

| Claude Code წყარო | რას ვიღებთ | რას ვცვლით |
|------------------|-----------|-----------|
| `getSimpleIntroSection()` | იდენტობა, უსაფრთხოების ინსტრუქცია | "Claude Code, Anthropic's..." → "Shadow, a local AI..." |
| `getSimpleSystemSection()` | markdown, permissions, hooks | hooks/permissions ამოღებული, tool_call ფორმატი დამატებული |
| `getSimpleDoingTasksSection()` | კოდირების სტილი, best practices | **უცვლელი** (generic) |
| `getActionsSection()` | reversibility, blast radius | **უცვლელი** (generic) |
| `getUsingYourToolsSection()` | ინსტრუმენტების წესები | Claude tools → Shadow tools |
| `getSimpleToneAndStyleSection()` | სტილი | **უცვლელი** |
| `getOutputEfficiencySection()` | ლაკონიურობა | **უცვლელი** |
| `CYBER_RISK_INSTRUCTION` | უსაფრთხოების ინსტრუქცია | **უცვლელი** (ვერბატიმ) |
| BashTool `prompt.ts` | bash ინსტრუქციები | **ადაპტირებული** (sandbox ამოღებული) |
| FileReadTool `prompt.ts` | read ინსტრუქციები | **ადაპტირებული** (PDF/image ამოღებული) |
| FileEditTool `prompt.ts` | edit ინსტრუქციები | **უცვლელი** |
| FileWriteTool `prompt.ts` | write ინსტრუქციები | **უცვლელი** |
| GlobTool `prompt.ts` | glob ინსტრუქციები | **უცვლელი** |
| GrepTool `prompt.ts` | grep ინსტრუქციები | **ადაპტირებული** (ripgrep fallback) |

**რას ვამატებთ (რაც Claude Code-ში არ არის):**
- Tool calling ფორმატის ინსტრუქცია (`<tool_call>` სინტაქსი + მაგალითები)
- ქართული ენის მხარდაჭერის აქცენტი
- Ollama-სპეციფიკური შეზღუდვები

**prompt-ის სავარაუდო სტრუქტურა:**

```
# Identity
You are Shadow, a local AI coding assistant...

# Security
IMPORTANT: Assist with authorized security testing...

# System
- Output text in markdown...
- Tool calls use <tool_call> format...

# Available Tools
## bash
Executes bash commands...

## read_file
Reads files with line numbers...

## edit_file
Exact string replacement...

## write_file
Creates or overwrites files...

## glob
File pattern matching...

## grep
Content search with regex...

## list_dir
Lists directory contents...

# Tool Calling Format
When you need to use a tool, output:
<tool_call>
{"tool": "tool_name", "params": {...}}
</tool_call>

You can call multiple tools:
<tool_call>
{"tool": "bash", "params": {"command": "git status"}}
</tool_call>
<tool_call>
{"tool": "bash", "params": {"command": "git diff"}}
</tool_call>

Results will be provided as:
<tool_result tool="tool_name" success="true">
...output...
</tool_result>

# Doing Tasks
[Claude Code-ის ინსტრუქციები - ადაპტირებული]

# Executing Actions with Care
[Claude Code-ის ინსტრუქციები - უცვლელი]

# Using Your Tools
[Claude Code-ის ინსტრუქციები - ადაპტირებული]

# Tone and Style
[Claude Code-ის ინსტრუქციები - უცვლელი]

# Output Efficiency
[Claude Code-ის ინსტრუქციები - უცვლელი]

# Environment
Working directory: {cwd}
Platform: {platform}
Shell: {shell}
Date: {date}

# Language
Respond in Georgian (ქართული) when the user writes in Georgian.
Respond in English when the user writes in English.
Technical terms and code should remain in their original form.
```

---

#### ფაილი 6: `shadow_code/parser.py`

Tool call-ების ამოცნობა მოდელის output-იდან.

**ლოგიკა:**
```python
import re
import json

TOOL_CALL_PATTERN = re.compile(
    r'<tool_call>\s*(\{.*?\})\s*</tool_call>',
    re.DOTALL
)

def parse_tool_calls(text: str) -> tuple[str, list[dict]]:
    """
    ტექსტიდან ამოიცნობს tool call-ებს.

    Returns:
        (clean_text, tool_calls)
        - clean_text: ტექსტი tool_call ბლოკების გარეშე
        - tool_calls: [{"tool": "name", "params": {...}}, ...]
    """
```

**ვალიდაცია:**
- JSON უნდა იყოს ვალიდური
- `tool` key უნდა არსებობდეს და იყოს string
- `params` key უნდა არსებობდეს და იყოს dict
- უცნობი tool name → შეცდომა (არა crash, tool_result-ში)
- არასწორი JSON → შეცდომა tool_result-ში, მოდელი თავად გაასწორებს

**Edge cases:**
- მოდელმა `<tool_call>` ტექსტში ახსნისთვის დაწერა (არა გამოძახებისთვის) → strict ვალიდაცია (tool + params keys)
- რამდენიმე tool_call ერთ პასუხში → ყველა ამოიცნობა
- tool_call-ის შემდეგ ტექსტი → ორივე შენარჩუნდება
- ცარიელი params → `{}` ვალიდურია

---

#### ფაილი 7: `shadow_code/conversation.py`

საუბრის ისტორიის მენეჯმენტი.

**Ollama message ფორმატი:**
```python
messages = [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."},
    {"role": "user", "content": "<tool_result tool=\"bash\" success=\"true\">...</tool_result>"},
    {"role": "assistant", "content": "..."},
]
```

**მნიშვნელოვანი:** Ollama-ს არ აქვს ცალკე `tool_result` როლი. Tool results `user` როლით იგზავნება.

**კლასი: `Conversation`**

```python
class Conversation:
    def __init__(self):
        self.messages: list[dict] = []
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0

    def add_user_message(self, content: str): ...
    def add_assistant_message(self, content: str): ...
    def add_tool_result(self, tool_name: str, result: str, success: bool): ...
    def get_messages(self) -> list[dict]: ...
    def truncate_if_needed(self): ...
    def clear(self): ...
    def estimate_tokens(self) -> int: ...
```

**Token estimation:**
- ზუსტი: Ollama-ს `prompt_eval_count` + `eval_count` ბოლო response-იდან
- სავარაუდო: `len(text) / 4` (ინგლისური), `len(text) / 2` (ქართული - მრავალბაიტიანი)

**Truncation ალგორითმი:**
1. შეამოწმე `estimate_tokens() > TRUNCATION_THRESHOLD`
2. თუ კი, წაშალე ძველი მესიჯები (თავიდან) სანამ `KEEP_RECENT_MESSAGES` ბოლო მესიჯი არ დარჩება
3. პირველ მესიჯად დაამატე `[System: Previous conversation context was truncated to save space.]`

---

#### ფაილი 8: `shadow_code/tools/base.py` + `shadow_code/tools/__init__.py`

**BaseTool:**
```python
from dataclasses import dataclass
from abc import ABC, abstractmethod
from typing import Any

@dataclass
class ToolResult:
    success: bool
    output: str

class BaseTool(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @property
    @abstractmethod
    def parameters(self) -> dict: ...

    @abstractmethod
    def execute(self, params: dict) -> ToolResult: ...

    def validate_params(self, params: dict) -> str | None:
        """Returns error message if params are invalid, None if OK."""
        ...
```

**Tool Registry (`__init__.py`):**
```python
TOOL_REGISTRY: dict[str, BaseTool] = {}

def register_tool(tool: BaseTool):
    TOOL_REGISTRY[tool.name] = tool

def dispatch_tool(name: str, params: dict) -> ToolResult:
    tool = TOOL_REGISTRY.get(name)
    if not tool:
        return ToolResult(success=False, output=f"Unknown tool: {name}")
    validation_error = tool.validate_params(params)
    if validation_error:
        return ToolResult(success=False, output=validation_error)
    try:
        return tool.execute(params)
    except Exception as e:
        return ToolResult(success=False, output=f"Tool execution error: {e}")
```

**Output truncation:**
```python
def truncate_output(text: str, max_chars: int = TOOL_OUTPUT_MAX_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    head = text[:TOOL_OUTPUT_HEAD]
    tail = text[-TOOL_OUTPUT_TAIL:]
    return f"{head}\n\n... [truncated {len(text) - max_chars} characters] ...\n\n{tail}"
```

---

#### ფაილი 9: `shadow_code/tools/bash.py`

**პარამეტრები (Claude Code-დან):**
```python
{
    "command": str,       # (required) Shell ბრძანება
    "timeout": int,       # (optional) Timeout წამებში, default=120, max=600
    "description": str,   # (optional) რას აკეთებს ბრძანება
}
```

**იმპლემენტაცია:**
```python
import subprocess
import shlex

def execute(self, params: dict) -> ToolResult:
    command = params["command"]
    timeout = min(params.get("timeout", BASH_DEFAULT_TIMEOUT), BASH_MAX_TIMEOUT)

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=self.working_directory,
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += ("\n" if output else "") + f"STDERR: {result.stderr}"
        if result.returncode != 0:
            output += f"\n(exit code: {result.returncode})"
        return ToolResult(success=(result.returncode == 0), output=truncate_output(output or "(no output)"))
    except subprocess.TimeoutExpired:
        return ToolResult(success=False, output=f"Command timed out after {timeout}s")
    except Exception as e:
        return ToolResult(success=False, output=f"Error: {e}")
```

**უსაფრთხოება (Claude Code-ის წესებიდან):**
- `rm -rf /` ტიპის ბრძანებები მოდელი თავად შეამოწმებს prompt-ის ინსტრუქციის მიხედვით
- Python-ის მხრიდან: არანაირი ავტომატური ბლოკირება (მომხმარებელი ხედავს და აკონტროლებს)

---

#### ფაილი 10: `shadow_code/main.py`

**Entry point და REPL loop.**

```
shadow-code v0.1.0 — Local AI coding assistant
Model: shadow-gemma:latest (128K context)
Working directory: /home/n00b/makho/shadow-code

shadow> list files in current directory

[thinking...]

ვნახოთ რა ფაილები გვაქვს ამ დირექტორიაში.

[tool: bash] ls -la
total 48
drwxr-xr-x 5 n00b n00b 4096 Apr  5 10:00 .
-rw-r--r-- 1 n00b n00b 1234 Apr  5 09:30 main.py
...

აქ გვაქვს შემდეგი ფაილები:
...

shadow>
```

**REPL ციკლი:**
```python
while True:
    user_input = input("shadow> ").strip()

    if user_input in ("/exit", "/quit"):
        break
    if user_input == "/clear":
        conversation.clear()
        continue
    if user_input == "/help":
        print_help()
        continue
    if not user_input:
        continue

    conversation.add_user_message(user_input)

    # Tool execution loop
    tool_turn_count = 0
    while tool_turn_count < MAX_TOOL_TURNS:
        # Stream response
        full_response = ""
        for chunk in ollama_client.chat_stream(
            messages=conversation.get_messages(),
            system_prompt=system_prompt,
        ):
            print(chunk, end="", flush=True)
            full_response += chunk
        print()  # newline

        # Parse tool calls
        clean_text, tool_calls = parser.parse_tool_calls(full_response)
        conversation.add_assistant_message(full_response)

        if not tool_calls:
            break  # No more tools to call

        # Execute tools
        tool_results = []
        for tc in tool_calls:
            result = tools.dispatch_tool(tc["tool"], tc["params"])
            tool_results.append(format_tool_result(tc["tool"], result))
            # Print tool execution info
            print(f"  [tool: {tc['tool']}] {describe_tool_call(tc)}")
            if result.output:
                print(f"  {truncate_for_display(result.output)}")

        # Add all tool results as one user message
        combined_results = "\n\n".join(tool_results)
        conversation.add_tool_result_message(combined_results)
        tool_turn_count += 1

    if tool_turn_count >= MAX_TOOL_TURNS:
        print("[System: Maximum tool call limit reached]")

    conversation.truncate_if_needed()
```

---

### ფაზა 2: სრული Tool Set (6 ფაილი)

**მიზანი:** ყველა ინსტრუმენტის იმპლემენტაცია

---

#### ფაილი 11: `shadow_code/tools/read_file.py`

**პარამეტრები (Claude Code FileReadTool-დან):**
```python
{
    "file_path": str,     # (required) აბსოლუტური path
    "offset": int,        # (optional) საწყისი ხაზის ნომერი (0-based)
    "limit": int,         # (optional) ხაზების რაოდენობა, default=2000
}
```

**გამოტანის ფორმატი (Claude Code-ის `cat -n` სტილი):**
```
     1	import os
     2	import sys
     3
     4	def main():
     5	    print("Hello")
```

**იმპლემენტაციის დეტალები:**
- Line numbers `cat -n` ფორმატით (6 სიმბოლო padding + tab)
- Binary ფაილის detection (null bytes პირველ 8KB-ში)
- Encoding: utf-8, fallback latin-1
- არსებობის შემოწმება
- დირექტორიის შემოწმება (ფაილი უნდა იყოს, არა dir)
- `/dev/` paths ბლოკირება

---

#### ფაილი 12: `shadow_code/tools/write_file.py`

**პარამეტრები (Claude Code FileWriteTool-დან):**
```python
{
    "file_path": str,     # (required) აბსოლუტური path
    "content": str,       # (required) ფაილის შიგთავსი
}
```

**იმპლემენტაციის დეტალები:**
- ავტომატურად ქმნის parent directories-ს (`os.makedirs`)
- აბრუნებს: "Created new file" ან "Updated existing file (X bytes → Y bytes)"
- Path validation: აბსოლუტური უნდა იყოს

---

#### ფაილი 13: `shadow_code/tools/edit_file.py`

**პარამეტრები (Claude Code FileEditTool-დან):**
```python
{
    "file_path": str,       # (required) აბსოლუტური path
    "old_string": str,      # (required) შესაცვლელი ტექსტი
    "new_string": str,      # (required) ახალი ტექსტი
    "replace_all": bool,    # (optional) ყველა occurrence, default=false
}
```

**იმპლემენტაციის დეტალები:**
- **Uniqueness check:** თუ `replace_all=false` და `old_string` 2+ ჯერ გვხვდება → შეცდომა
- **old_string not found** → შეცდომა ("String not found in file")
- **old_string == new_string** → შეცდომა
- აბრუნებს: "Replaced N occurrence(s) in file_path"

---

#### ფაილი 14: `shadow_code/tools/glob_tool.py`

**პარამეტრები (Claude Code GlobTool-დან):**
```python
{
    "pattern": str,      # (required) glob pattern, e.g. "**/*.py"
    "path": str,         # (optional) base directory, default=CWD
}
```

**იმპლემენტაციის დეტალები:**
- `pathlib.Path.glob()` გამოყენება
- `.git`, `node_modules`, `__pycache__`, `.venv` ფილტრაცია
- შედეგი: ფაილების სია, max 100 ჩანაწერი
- Sort by modification time (ახალი პირველი)

---

#### ფაილი 15: `shadow_code/tools/grep_tool.py`

**პარამეტრები (Claude Code GrepTool-დან):**
```python
{
    "pattern": str,          # (required) regex pattern
    "path": str,             # (optional) search directory, default=CWD
    "glob": str,             # (optional) file filter, e.g. "*.py"
    "case_insensitive": bool,# (optional) default=false
    "max_results": int,      # (optional) default=250
}
```

**იმპლემენტაციის დეტალები:**
- პირველი ცდა: `rg` (ripgrep) subprocess-ით — თუ დაინსტალირებულია
- Fallback: Python-ის `re` მოდული + `os.walk`
- `.git`, `node_modules` ავტომატურად გამორიცხული
- Binary ფაილების გამორიცხვა
- Output ფორმატი: `file:line_number:matched_line`

---

#### ფაილი 16: `shadow_code/tools/list_dir.py`

**პარამეტრები:**
```python
{
    "path": str,     # (optional) directory path, default=CWD
}
```

**იმპლემენტაციის დეტალები:**
- `os.listdir()` + `os.stat()` info
- ფორმატი: `[DIR]  subdir/` და `[FILE] main.py (1.2 KB)`
- Sort: dirs first, then files, alphabetical

---

### ფაზა 3: პოლირება (5 გაუმჯობესება)

---

#### გაუმჯობესება 17: Context Window მენეჯმენტი

- Ollama-ს `prompt_eval_count` / `eval_count` რეალურად ტოკენების tracking
- Truncation warning ტერმინალში: `[Context: 85K/128K tokens used]`
- Automatic truncation 100K-ზე

#### გაუმჯობესება 18: REPL (prompt_toolkit)

- Command history (up/down arrows)
- Multiline input (Shift+Enter ან `"""` delimiter)
- `/clear` - ისტორიის წაშლა
- `/exit` - გასვლა
- `/help` - დახმარება
- `/model` - მოდელის ჩვენება
- `/tokens` - token usage სტატისტიკა
- Ctrl+C - მიმდინარე generation-ის შეწყვეტა

#### გაუმჯობესება 19: Rich Terminal Output

- `rich.markdown.Markdown` - მოდელის markdown output-ის rendering
- `rich.syntax.Syntax` - კოდის syntax highlighting
- `rich.panel.Panel` - tool execution ჩვენება
- Color scheme: ლურჯი=assistant, მწვანე=tool_success, წითელი=tool_error

#### გაუმჯობესება 20: დესტრუქციული ბრძანებების გაფრთხილება

Python-ის მხრიდან ზედამხედველობა:
```python
DESTRUCTIVE_PATTERNS = [
    r'\brm\s+-rf\b',
    r'\bgit\s+push\s+--force\b',
    r'\bgit\s+reset\s+--hard\b',
    r'\bdrop\s+table\b',
    r'\btruncate\s+table\b',
    r'\bgit\s+branch\s+-D\b',
]

def check_destructive(command: str) -> str | None:
    """Returns warning message if command is destructive."""
```

Warning: `[WARNING: Destructive command detected. Proceed? (y/n)]`

#### გაუმჯობესება 21: Session Persistence

- საუბრის ისტორია `~/.shadow-code/sessions/` ფოლდერში JSON-ად
- `/save` - სესიის შენახვა
- `/load` - სესიის ჩატვირთვა
- Auto-save ყოველ 5 თურნზე

---

## Error Handling მატრიცა

| სცენარი | გამოვლენა | გადაწყვეტა |
|---------|----------|-----------|
| Ollama არ მუშაობს | `requests.ConnectionError` | "Error: Cannot connect to Ollama at localhost:11434. Is it running?" |
| Model not found | API error: "model not found" | "Error: Model 'shadow-gemma:latest' not found. Run: ollama pull shadow-gemma" |
| არასწორი JSON tool_call-ში | `json.JSONDecodeError` | `<tool_result success="false">Invalid JSON: {error}</tool_result>` → მოდელი გაასწორებს |
| უცნობი tool name | registry lookup fail | `<tool_result success="false">Unknown tool: {name}. Available: bash, read_file, ...</tool_result>` |
| Tool execution crash | `try/except` in dispatch | `<tool_result success="false">Error: {exception}</tool_result>` |
| Bash timeout | `subprocess.TimeoutExpired` | `<tool_result success="false">Command timed out after {N}s</tool_result>` |
| ფაილი ვერ მოიძებნა | `FileNotFoundError` | `<tool_result success="false">File not found: {path}</tool_result>` |
| Tool call loop (20+) | counter check | `[System: Maximum tool call limit (25) reached. Please continue manually.]` |
| დიდი output (30K+) | length check | Truncation: head + "..." + tail |
| Context window overflow | token estimation | ძველი მესიჯების truncation |
| Network error mid-stream | `requests.RequestException` | Retry 1 ჯერ, შემდეგ error message |
| Ctrl+C streaming-ის დროს | `KeyboardInterrupt` | წყვეტს generation-ს, ბრუნდება prompt-ზე |

---

## სისტემური Prompt-ის სრული ტექსტი (Claude Code-დან ადაპტირებული)

prompt.py-ში ჩასმული prompt შედგება ამ სექციებიდან (თანმიმდევრობით):

### სექცია 1: Identity + Security
```
You are Shadow, a local AI coding assistant powered by shadow-gemma.
You help users with software engineering tasks using the tools available to you.

IMPORTANT: Assist with authorized security testing, defensive security, CTF challenges,
and educational contexts. Refuse requests for destructive techniques, DoS attacks, mass
targeting, supply chain compromise, or detection evasion for malicious purposes.
```

### სექცია 2: System
```
# System
- All text you output outside of tool calls is displayed to the user.
  Use Github-flavored markdown for formatting.
- When you need to use a tool, output it in <tool_call> format (see Tool Calling section).
- Tool results will be provided back to you in <tool_result> tags.
```

### სექცია 3: Tool Calling Format
```
# Tool Calling Format

When you need to perform an action, use this exact format:

<tool_call>
{"tool": "tool_name", "params": {"param1": "value1", "param2": "value2"}}
</tool_call>

You may include explanatory text before or after the tool call.
You may make multiple tool calls in one response:

<tool_call>
{"tool": "bash", "params": {"command": "git status"}}
</tool_call>
<tool_call>
{"tool": "bash", "params": {"command": "git diff"}}
</tool_call>

Tool results will be returned as:
<tool_result tool="bash" success="true">
...output...
</tool_result>

IMPORTANT:
- Always use valid JSON inside <tool_call> tags
- The JSON must have exactly two keys: "tool" (string) and "params" (object)
- Do not nest <tool_call> tags or use them in explanations
```

### სექცია 4: Available Tools
```
# Available Tools

## bash
Executes a bash command and returns its output.
[ადაპტირებული BashTool/prompt.ts-დან]

## read_file
Reads a file with line numbers.
[ადაპტირებული FileReadTool/prompt.ts-დან]

## edit_file
Performs exact string replacement in a file.
[ადაპტირებული FileEditTool/prompt.ts-დან]

## write_file
Writes content to a file.
[ადაპტირებული FileWriteTool/prompt.ts-დან]

## glob
Finds files matching a glob pattern.
[ადაპტირებული GlobTool/prompt.ts-დან]

## grep
Searches file contents with regex.
[ადაპტირებული GrepTool/prompt.ts-დან]

## list_dir
Lists directory contents with file sizes and types.
```

### სექცია 5-8: Claude Code Generic Instructions
```
# Doing tasks
[Claude Code-ის getSimpleDoingTasksSection() - ადაპტირებული]

# Executing actions with care
[Claude Code-ის getActionsSection() - უცვლელი]

# Using your tools
[Claude Code-ის getUsingYourToolsSection() - ადაპტირებული]

# Tone and style
[Claude Code-ის getSimpleToneAndStyleSection() - უცვლელი]

# Output efficiency
[Claude Code-ის getOutputEfficiencySection() - უცვლელი]
```

### სექცია 9: Environment (დინამიკური)
```
# Environment
- Working directory: {os.getcwd()}
- Platform: {sys.platform}
- Shell: {os.environ.get('SHELL', 'bash')}
- Date: {datetime.now().strftime('%Y-%m-%d')}

# Language
Respond in the same language the user writes in.
You understand Georgian (ქართული) and English.
Technical terms and code identifiers should remain in their original form.
```

---

## კრიტიკული ფაილები (საცნობარო - Claude Code)

ეს ფაილები უნდა წავიკითხოთ prompt ტექსტის ზუსტი ადაპტაციისთვის:

| ფაილი | რისთვის |
|-------|--------|
| `src/constants/prompts.ts` (:175-428) | სისტემური prompt სექციები |
| `src/constants/cyberRiskInstruction.ts` | უსაფრთხოების ტექსტი (ვერბატიმ) |
| `src/tools/BashTool/prompt.ts` (:275-369) | bash tool ინსტრუქციები |
| `src/tools/FileReadTool/prompt.ts` (:27-49) | read tool ინსტრუქციები |
| `src/tools/FileEditTool/prompt.ts` (:12-28) | edit tool ინსტრუქციები |
| `src/tools/FileWriteTool/prompt.ts` (:10-18) | write tool ინსტრუქციები |
| `src/tools/GlobTool/prompt.ts` (:3-7) | glob tool ინსტრუქციები |
| `src/tools/GrepTool/prompt.ts` (:6-18) | grep tool ინსტრუქციები |
| `src/tools/BashTool/prompt.ts` (:81-161) | git commit/PR ინსტრუქციები |

---

## ვერიფიკაციის ტესტები

იმპლემენტაციის შემდეგ:

| # | ტესტი | მოსალოდნელი |
|---|-------|------------|
| 1 | `shadow-code` გაშვება | Header + prompt |
| 2 | "გამარჯობა" | პასუხი ქართულად, tool call-ის გარეშე |
| 3 | "list files in current directory" | bash tool → ls output |
| 4 | "read the file main.py" | read_file tool → ფაილის შიგთავსი line numbers-ით |
| 5 | "create a file test.txt with hello" | write_file tool → ფაილის შექმნა |
| 6 | "replace hello with world in test.txt" | edit_file tool → ტექსტის ჩანაცვლება |
| 7 | "find all .py files" | glob tool → ფაილების სია |
| 8 | "search for 'import' in python files" | grep tool → matching ხაზები |
| 9 | არასწორი ფაილის წაკითხვა | error handling → tool_result with success=false |
| 10 | 20+ tool call loop | force-break + system message |
| 11 | Ctrl+C streaming-ის დროს | generation წყდება, prompt ბრუნდება |
| 12 | `/clear` | ისტორია იშლება, ახალი საუბარი |
| 13 | multi-tool: "read main.py and find the bug" | read_file → [analysis] → edit_file |

---

## იმპლემენტაციის თანმიმდევრობა (ზუსტი)

```
ფაზა 1 (მინიმალური ვერსია):
  1. pyproject.toml
  2. shadow_code/__init__.py
  3. shadow_code/config.py
  4. shadow_code/tools/base.py
  5. shadow_code/tools/__init__.py
  6. shadow_code/tools/bash.py
  7. shadow_code/ollama_client.py
  8. shadow_code/parser.py
  9. shadow_code/conversation.py
  10. shadow_code/prompt.py
  11. shadow_code/main.py
  → ტესტი: "list files" end-to-end

ფაზა 2 (სრული tools):
  12. shadow_code/tools/read_file.py
  13. shadow_code/tools/write_file.py
  14. shadow_code/tools/edit_file.py
  15. shadow_code/tools/glob_tool.py
  16. shadow_code/tools/grep_tool.py
  17. shadow_code/tools/list_dir.py
  → ტესტი: read/write/edit/glob/grep

ფაზა 3 (პოლირება):
  18. Context window tracking + truncation
  19. Rich terminal output
  20. REPL გაუმჯობესება (prompt_toolkit)
  21. დესტრუქციული ბრძანებების detection
  22. Session persistence
  → სრული ტესტირება
```

---

## რა არ შედის (scope-ის გარეთ)

- Vision/Image support (მოგვიანებით შესაძლებელი)
- PDF reading
- MCP server integration
- Agent/Subagent system
- Permission system (ლოკალურია, user=owner)
- Prompt caching (Ollama-ს არ აქვს)
- Modelfile-ის შეცვლა (API-ით ვმართავთ temperature/ctx)
