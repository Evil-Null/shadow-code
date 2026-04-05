# vecmem Integration Analysis for shadow-code

## vecmem -- What It Does

vecmem is YOUR TypeScript/Node.js tool that:
1. **Parses** markdown files (heading-aware chunking via remark AST)
2. **Embeds** each chunk into 384-dim vectors (all-MiniLM-L6-v2, local ONNX)
3. **Stores** in SQLite (FTS5 full-text + BLOB embeddings)
4. **Searches** with BM25 + cosine similarity + RRF fusion
5. Everything **local** -- no API keys, no cloud

Key architecture:
```
.md files -> Parser (chunker) -> Embedder (384-dim) -> SQLite Store
                                                          |
                                          Query -> BM25 + Vector -> RRF Fusion -> Results
```

Tech: all-MiniLM-L6-v2 (23MB model), SQLite WAL mode, FTS5, ~100ms search, ~30 files/sec indexing.

---

## The Idea: RAG for System Prompt

**Current approach (PLAN_FINAL.md):**
```
Every request:
  System prompt (~2K tokens) = identity + ALL tool descriptions + ALL instructions + ALL examples
  + User message
  + Conversation history
  -> Ollama API
```

**vecmem approach:**
```
Every request:
  Core prompt (~500 tokens) = identity + tool format + tool names only
  + Semantic search: "what knowledge is relevant to this user query?"
  + Retrieved chunks (~500-1000 tokens, ONLY relevant ones)
  + User message
  + Conversation history
  -> Ollama API
```

**Token savings per request: ~1000-1500 tokens** -- that's ~1% of context window saved EVERY turn.
Over 20 turns = ~20-30K tokens saved = significantly more conversation space.

---

## What Gets Indexed as Knowledge

| Category | Content | Source |
|----------|---------|--------|
| Tool: bash | Full bash tool instructions, git rules, sandbox | Claude Code BashTool/prompt.ts |
| Tool: read_file | Read file instructions, line format, limits | Claude Code FileReadTool/prompt.ts |
| Tool: edit_file | Edit instructions, uniqueness rules | Claude Code FileEditTool/prompt.ts |
| Tool: write_file | Write instructions | Claude Code FileWriteTool/prompt.ts |
| Tool: glob | Glob pattern instructions | Claude Code GlobTool/prompt.ts |
| Tool: grep | Grep regex, output modes | Claude Code GrepTool/prompt.ts |
| Coding style | No gold-plating, no premature abstraction | Claude Code prompts.ts |
| Actions | Reversibility, blast radius, when to ask | Claude Code prompts.ts |
| Git workflow | Commit, PR creation, git safety protocol | Claude Code BashTool/prompt.ts |
| Security | OWASP top 10, injection prevention | Claude Code prompts.ts |
| Cyber risk | Authorized testing, CTF, defensive | Claude Code cyberRiskInstruction.ts |
| Examples | Tool usage examples, multi-tool chains | Custom |
| Georgian | Language-specific instructions | Custom |

Each category = 1-3 chunks in the vector DB. Total: ~30-50 chunks.

---

## How It Works at Runtime

```
User: "read main.py and fix the bug on line 10"

Step 1: Semantic search on user query
  -> Finds: "Tool: read_file" (score 0.91)
  -> Finds: "Tool: edit_file" (score 0.87)
  -> Finds: "Coding style" (score 0.72)
  -> Does NOT find: "Tool: grep", "Git workflow", etc.

Step 2: Build dynamic prompt
  Core (always present):
    - Identity
    - Tool call format
    - Tool names list

  + Retrieved knowledge:
    - read_file detailed instructions
    - edit_file detailed instructions
    - "Read code before modifying" rule

Step 3: Send to Ollama
  Much smaller prompt than sending ALL instructions
```

---

## Implementation: Python vecmem-lite

vecmem is TypeScript. We need Python equivalent. But we DON'T port everything -- only the core:

### What we reuse from vecmem:
- **SQLite schema** (compatible -- same schema.sql)
- **Chunking logic** (simplified -- our chunks are pre-defined, not parsed from arbitrary .md)
- **Embedding model** (same all-MiniLM-L6-v2 via sentence-transformers Python)
- **Hybrid search** (BM25 via FTS5 + cosine similarity + RRF)
- **Score normalization** (UnitScore [0,1])

### What we DON'T need:
- remark AST parser (our content is pre-structured)
- MCP server (shadow-code calls directly)
- CLI commands (init, status, doctor)
- File watcher / re-indexing

### New file: `shadow_code/knowledge.py`

```python
"""
Knowledge retrieval system for shadow-code.
Python implementation of vecmem's core: embed + store + search.

Uses same embedding model (all-MiniLM-L6-v2) and SQLite schema.
"""

class KnowledgeBase:
    def __init__(self, db_path: str):
        """Open/create SQLite DB with vecmem-compatible schema."""

    def index_chunk(self, category: str, title: str, content: str):
        """Embed and store a single knowledge chunk."""

    def search(self, query: str, top_k: int = 5) -> list[KnowledgeResult]:
        """Hybrid search: BM25 + vector + RRF fusion."""

    def build_prompt_context(self, query: str) -> str:
        """Search and format results as prompt-injectable text."""
```

### New file: `shadow_code/knowledge_data.py`

```python
"""
Pre-defined knowledge chunks adapted from Claude Code.
Each chunk is a focused piece of knowledge that can be
independently retrieved via semantic search.
"""

KNOWLEDGE_CHUNKS = [
    {
        "category": "tool",
        "title": "bash tool instructions",
        "content": """Executes bash commands. Parameters: command (required), timeout (optional).
Prefer dedicated tools over bash: read_file over cat, edit_file over sed, write_file over echo.
For multiple independent commands, make multiple tool calls.
Git safety: never skip hooks, prefer new commits over amending, never force push unless asked."""
    },
    {
        "category": "tool",
        "title": "read_file tool instructions",
        "content": """Reads a file with line numbers (cat -n format).
Parameters: file_path (absolute, required), offset (1-based, optional), limit (default 2000, optional).
Can only read files, not directories. Always use absolute paths."""
    },
    # ... more chunks
]
```

### Dependencies addition:

```toml
[project.optional-dependencies]
knowledge = ["sentence-transformers>=2.2.0"]
full = ["rich>=13.0.0", "prompt_toolkit>=3.0.0", "sentence-transformers>=2.2.0"]
```

sentence-transformers includes: torch + transformers + numpy. Heavy (~500MB), but:
- Runs completely locally
- Same model as vecmem (all-MiniLM-L6-v2)
- Embedding takes ~10ms per chunk
- One-time download

### Alternative: ONNX Runtime (lighter)

```toml
dependencies = ["onnxruntime>=1.16.0", "tokenizers>=0.15.0", "numpy>=1.24.0"]
```

~50MB instead of ~500MB. Same model, same results, faster inference.
This is what vecmem uses internally (@huggingface/transformers with ONNX).

---

## Architecture with vecmem Integration

```
                     STARTUP
                        |
                        v
              knowledge.py: index all chunks
              (one-time, ~2 seconds)
                        |
                        v
                   SQLite DB ready
                   (~50 chunks indexed)


                  EACH USER TURN
                        |
                        v
              knowledge.search(user_query)
              (~100ms, returns top 5 chunks)
                        |
                        v
              prompt.py: build_dynamic_prompt(
                core_prompt + retrieved_chunks
              )
                        |
                        v
              ollama_client: send to model
```

### Prompt structure changes:

**BEFORE (static, ~2K tokens every time):**
```
[identity + security]
[tool format + examples]
[ALL 7 tool descriptions - detailed]
[ALL coding instructions]
[ALL action safety rules]
[ALL tone/style rules]
[environment]
```

**AFTER (dynamic, ~800 tokens average):**
```
[identity + security]           <- always (200 tokens)
[tool format + tool names]      <- always (200 tokens)
[retrieved: relevant tools]     <- dynamic (200-400 tokens)
[retrieved: relevant rules]     <- dynamic (100-200 tokens)
[environment]                   <- always (100 tokens)
```

---

## Updated Phase Plan

### Phase 0: Validation (unchanged)

### Phase 1: Minimal version (unchanged -- static prompt)

### Phase 1.5: Knowledge Integration (NEW)
1. Install sentence-transformers or onnxruntime
2. Create `knowledge.py` (KnowledgeBase class)
3. Create `knowledge_data.py` (all chunks from Claude Code)
4. Modify `prompt.py` to use dynamic retrieval
5. Test: same queries, compare token usage before/after

### Phase 2: Full tools (unchanged)

### Phase 3: Polish (unchanged)

---

## Critical Questions

### Q1: Is the overhead worth it?
**Analysis:**
- Startup: +2 seconds (one-time embedding of ~50 chunks)
- Per-turn: +100ms (search)
- Dependency: +50MB (onnxruntime) or +500MB (sentence-transformers)
- Token savings: ~1000-1500 per turn x 20 turns = 20-30K saved

**Verdict:** YES, if the model performs well with dynamic prompts. Must test in Phase 0.

### Q2: Will partial knowledge hurt model performance?
**Risk:** Model only sees "relevant" tool instructions. If search misses something, model won't know the rule.
**Mitigation:**
- Core prompt always has tool names + format
- Safety rules (security, destructive warnings) always included
- search top_k=5 is generous (out of ~50 chunks = 10%)
- Fallback: if search returns nothing relevant, include a "general" chunk

### Q3: Python or reuse vecmem directly?
**Python reimplementation** is better because:
- No Node.js dependency
- Tighter integration (no subprocess overhead)
- We only need 20% of vecmem's functionality
- Same embedding model, compatible DB schema

### Q4: Can we share the SQLite DB with vecmem?
**Yes** -- same schema, same embedding model (all-MiniLM-L6-v2, 384-dim).
If user runs `vecmem index` on .md files, shadow-code can search them too.
And vice versa: shadow-code's indexed knowledge is searchable by vecmem CLI.

---

## Token Budget Comparison

### Without vecmem (current PLAN_FINAL):
```
System prompt:    ~2,000 tokens (every turn)
20-turn session:  ~40,000 tokens on prompts alone
Context budget:   128K - 40K = 88K for conversation
```

### With vecmem:
```
Core prompt:      ~700 tokens (every turn)
Retrieved:        ~400 tokens (varies per turn)
Total prompt:     ~1,100 tokens/turn
20-turn session:  ~22,000 tokens on prompts
Context budget:   128K - 22K = 106K for conversation
Savings:          +18K tokens for conversation (20% more room)
```

---

## Summary

vecmem integration is a **strong upgrade** for shadow-code:
1. **Token efficiency** -- ~50% less prompt tokens per turn
2. **Scalability** -- can add unlimited knowledge without bloating prompt
3. **Compatibility** -- same DB format as vecmem, interoperable
4. **Local** -- no API keys, no cloud, everything on machine

Implementation as Phase 1.5, after basic system works but before full tool set.
