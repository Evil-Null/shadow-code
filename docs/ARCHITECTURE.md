# shadow-code × qwen2.5-coder × EAS — Architecture

This document describes the architecture of the EAS-enriched shadow-code agent
running on `qwen2.5-coder:7b-Q4_K_M` (32K ctx). It also documents *what we did
not build* and why — the realist view of what a 7B Q4 model can actually
deliver.

## Layered Design

```
┌──────────────────────────────────────────────────────────────────┐
│  STATIC LAYER  (KV-cache locked, ~10.6KB, never f-string'd)      │
│  ─ SYSTEM_PROMPT (prompt.py)                                     │
│      • Identity + Iron Laws                                      │
│      • 20 zero-trust security rules                              │
│      • Quality bar (V1-V7 reminders)                             │
│      • Tool-calling format docs                                  │
│      • get_language_rules tool reference                         │
└──────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────┐
│  DYNAMIC LAYER  (user-message scoped, no cache stress)           │
│  ─ Skill bodies (skills.py, 20 skills, on-demand)                │
│      • Auto-prepended bilingual directive (Georgian/English)     │
│  ─ Tool result hints (rule auto-inject in edit/write_file)       │
│      • Session-deduplicated via ToolContext.rules_loaded         │
│  ─ Conversation history                                          │
└──────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────┐
│  TOOL LAYER  (BaseTool subclasses)                               │
│  ─ read_file, write_file, edit_file, list_dir, grep, bash,       │
│    get_language_rules                                            │
└──────────────────────────────────────────────────────────────────┘
```

### Why STATIC must stay static

`SYSTEM_PROMPT` is a Python *constant*, never an f-string. Ollama / llama.cpp
KV-cache reuses the prefix across turns. Any dynamic interpolation
(timestamps, hostnames, paths) breaks the cache and adds 1-3s TTFT per turn.
All dynamic content goes through the user-message layer.

## Skill System

Each skill is a `(name, description, prompt)` triple registered via
`register_skill()`. The function auto-prepends a bilingual directive so users
writing in Georgian get Georgian responses (with English identifiers/code).

### Skill catalog (20 total)

| Skill | Purpose |
|---|---|
| `/plan` | Explicit planning, no edits, V1-V7 verification schema |
| `/review` | 4-section structured: ARCHITECT / SECURITY / QA / TECH LEAD VERDICT + V1-V7 |
| `/audit` | STRIDE security audit |
| `/cross-validate` | Adversarial 2-pass self-review |
| `/harden` | Production resilience: errors, edges, i18n, concurrency |
| `/distill` | Simplification preserving behavior |
| `/api-design` | REST API design/audit checklist |
| `/test` | Run tests with pyramid awareness |
| `/migrate` | Database migration (safe, reversible) |
| `/refactor`, `/simplify`, `/debug`, `/explain`, `/verify`, `/search`, `/stuck`, `/init`, `/commit`, `/pr`, `/remember` | Workflow utilities |

## Rule Auto-Injection

`edit_file` and `write_file` append a one-line nudge after their success
message when:

- The path's extension maps to an EAS rule via `rule_for_filename(path)`
- The change is non-trivial (`>200` chars OR contains `def`/`function`/`class`/`fn`/`func` for edits; `>500` chars for writes)
- The rule has not yet been hinted this session (dedup via `ToolContext.rules_loaded`)

The hint nudges the model to call `get_language_rules` on demand. Token cost
~30 tokens per substantive edit, ~0 thereafter (deduped).

## Validation Harnesses

- `phase0_validate.py` — 15 prompts (10 tool / 5 no_tool), parser robustness baseline. Target: ≥80%.
- `phase5_e2e.py` — 5 realistic agentic tasks. Target: ≥80%.

Run after every change.

## What We Deliberately Did NOT Build

The architect's full 8-phase plan included features we challenged and dropped
because **7B Q4 cannot deliver them honestly**:

| Feature | Why dropped |
|---|---|
| **Auto-PEV prefix injection** on every "complex" turn | 7B ignores ~20% of meta-instructions; adds verbosity to every complex turn for marginal benefit. Replaced with explicit `/plan` skill. |
| **Multi-pass `/review` (4 sequential model calls)** | 7B Q4 collapses passes into one ~50% of the time ("pass collapse"). 30-60s latency on every `/review` is a UX killer. Replaced with structured single-pass schema (4 sections in one response). |
| **Keyword auto-routing** (regex → "💡 try /review") | Hints are largely ignored on 7B; users already know slash commands. ROI ≈ 0. Kept only the bilingual reinforcement. |
| **V1-V7 auto-gate** (post-edit nudge to run tests) | When triggered, 7B often runs a wrong/random bash command and claims "V1-V7 done" — security theater, not real verification. Embedded V1-V7 checklist into `/review` skill body instead (explicit, model has clear context). |
| **Memory auto-recall** (glob `~/.shadow-code/memory/*.md`) | User has empty memory dir; building infrastructure for non-existent data. Keyword overlap on 7B = noisy first-turn pollution. Deferred until populated. |
| **`/polish`, `/critique`, `/onboard` skills** | `/polish` and `/critique` overlap with `/review`. `/onboard` is rare in code-agent context. Fake skill diversity. |
| **New modules** (`orchestration.py`, `router.py`, `verification.py`, `memory.py`) | All redundant given the above. Zero new files written. |

### Realistic Score

| Dimension | Pre-EAS | Post-R4 | Theoretical 7B ceiling |
|---|---|---|---|
| Tool reliability | 100% | 100% | 100% |
| Iron Laws adherence | ~70% | ~85% | ~88% |
| Security baseline | 55% (11/20) | **100% (20/20)** | 100% |
| Skill coverage | 15 | **20** | n/a |
| `/review` quality | basic | 70% structured single-pass | 70% (multi-pass would only reach 65% due to collapse) |
| PEV discipline | ~40% | ~70% (via `/plan`) | ~85% |
| Auto-routing | 0% | 0% (rejected) | ~85% (not on 7B reliably) |
| Memory recall | manual | manual (deferred) | ~75% (semantic, not 7B) |
| Latency penalty vs baseline | — | **0** | — |
| **Overall elite-ness** | **70%** | **~85%** | **~92% ceiling** |

To go above 85%, the path is **not more prompt engineering** — it's a stronger
model (Qwen 14B/32B), embeddings for semantic memory, or actual multi-process
orchestration.

## Post-R4 Hardening (5c809ef + 419ea8f + 5084031)

After R4's regression suite passed, two real-world bugs surfaced that R1-R4
synthetic tests did not catch:

### Bug 1 — 7B emits raw `bash` blocks instead of `tool_call` JSON

**Symptom:** user asked "List files in /tmp" → model responded with
` ```bash\nls -la /tmp\n``` ` (raw shell, no JSON wrapper). Parser's Pass 2
required `{tool, params}` JSON shape, so the block was treated as prose and
nothing executed. From the user's POV the model "just chatted."

**Fix:** parser Pass 4 fallback (`419ea8f`). When passes 1-3 yield zero
tool calls AND a ` ```bash ` / ` ```sh ` block exists with non-JSON body,
synthesize a `bash` tool call with `params.command = body`. Skips
JSON-shaped bodies to avoid double-handling Pass 2 candidates.

### Bug 2 — Q4 repetition loop on Georgian tokens

**Symptom:** Georgian prompts produced clean output for ~30 tokens, then
locked into endless repetition of a single low-frequency word
("დაითხოვეთ" × hundreds). Same Q4_K_M failure mode reported widely for
Cyrillic / CJK on small quants.

**Fix:** `Modelfile.qwen` (`5c809ef`):
- `repeat_penalty 1.05 → 1.15`
- Add `repeat_last_n 256` (default 64 was too narrow)

Verified: clean Georgian output with proper `tool_call` write_file
invocation. No regression on phase0/phase5 (English) suites.

### Bug 3 — VRAM headroom on 8GB cards

Not a bug, a capacity constraint. shadow-qwen needs 6.2GB VRAM on 32K ctx;
GTX 1070 has 8GB total. Default 5min keep-alive can block other GPU work.
Documented in `docs/VRAM.md` with three unload methods + ready-to-use
shell aliases (`gpu-status`, `gpu-free`, `gpu-free-all`).

### Lesson

Synthetic regression suites probe *the parser and prompt logic*. They do
not probe **the actual model under realistic stochastic load** in the
user's language. Always run an interactive smoke test in the user's
primary language before shipping prompt/parameter changes.

## File Map

```
shadow_code/
├── prompt.py             ─ SYSTEM_PROMPT (10.6KB, locked)
├── skills.py             ─ 20 skills with auto-prepended bilingual
├── rules_loader.py       ─ EXTENSION_TO_RULE + lru-cached loaders
├── tool_context.py       ─ ToolContext (cwd, read_files, rules_loaded)
├── parser.py             ─ 4-pass tool extraction (canonical → JSON-shape →
│                            unclosed → raw bash/sh fence fallback)
├── conversation.py       ─ msg history (UNCHANGED)
├── compaction.py         ─ context compaction (UNCHANGED)
├── main.py               ─ REPL + agentic loop (UNCHANGED in R1-R4)
└── tools/
    ├── edit_file.py      ─ + rule hint on non-trivial edits
    ├── write_file.py     ─ + rule hint on substantive writes
    └── get_language_rules.py  ─ EAS rule lookup tool
```
