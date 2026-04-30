# shadow-code × qwen2.5-coder × EAS

> **Setup guide for running shadow-code with `qwen2.5-coder` (Ollama) plus
> EAS (Elite Agent System) engineering rules and skills.**

This variant pairs the local `qwen2.5-coder:7b` model with shadow-code's
agentic loop and selectively imports rules + skills from
[`elite-agent-system`](https://github.com/Evil-Null/elite-agent-system) at
`~/.copilot/`.

## What you get

| Capability | How |
|---|---|
| Local function-calling agent | shadow-code's parser + tool registry |
| qwen-tuned generation | `Modelfile.qwen` (ChatML, 32K ctx, temp 0.2) |
| EAS Iron Laws + security baseline | injected into `SYSTEM_PROMPT` (~2KB) |
| On-demand language rules | `get_language_rules` tool reads `~/.copilot/rules/*.md` |
| Distilled EAS workflows | `/review`, `/test`, `/audit`, `/migrate` skills |

## Prerequisites

```bash
# 1. Ollama with qwen2.5-coder
ollama pull qwen2.5-coder:latest

# 2. EAS rules installed at ~/.copilot/rules/
# (only required if you want the get_language_rules tool to return content)
ls ~/.copilot/rules/   # should list common-security.md, python.md, ...
```

## Build the qwen-tuned model

```bash
cd shadow-code
ollama create shadow-qwen -f Modelfile.qwen
```

`Modelfile.qwen` sets:
- `FROM qwen2.5-coder:latest`
- `parameter num_ctx 32768`
- `parameter temperature 0.2`
- `parameter top_p 0.9`
- `parameter num_predict 8192`
- `parameter stop "<|im_end|>"` (qwen ChatML stop)

## Install & run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
pip install rich prompt_toolkit  # optional UI deps

SHADOW_MODEL=shadow-qwen:latest shadow-code
```

## What's qwen-specific

| File | Change |
|---|---|
| `Modelfile.qwen` | New: qwen2.5 ChatML stop tokens, 32K ctx |
| `shadow_code/parser.py` | 3-pass extraction: canonical fence → lenient fence → unclosed-fence fallback. Tolerates qwen's tendency to label fences as ` ```bash ` / ` ```json ` |
| `shadow_code/prompt.py` | Anti-hallucination block (don't fabricate `<tool_result>`); EAS baseline (Iron Laws + 11 security rules); `get_language_rules` tool documentation |
| `shadow_code/rules_loader.py` | New: extension→rule mapping + cached summary loader from `~/.copilot/rules/` |
| `shadow_code/tools/get_language_rules.py` | New: BaseTool for on-demand rule fetch |
| `shadow_code/skills.py` | `/review` enriched with 5-Eye protocol; `/test` enriched with testing pyramid + `--e2e`; new `/audit` (STRIDE security) and `/migrate` (DB migrations) |

## Skills overview

```
/review     5-Eye review (architect/dev/security/qa/lead)
/test       Run tests; --e2e for Playwright
/audit      Security audit: STRIDE + scans + manual checks
/migrate    Safe DB migrations (PG/MySQL/Prisma/Drizzle/Django/golang-migrate)
/refactor   Behavior-preserving cleanup
/debug      Root-cause + fix
/review …   (and 9 more — see `/skills` in REPL)
```

## Tools

`bash`, `read_file`, `edit_file`, `write_file`, `glob`, `grep`, `list_dir`,
`multi_read`, `project_summary`, `file_backup`, `file_restore`,
**`get_language_rules`**.

`get_language_rules` accepts `{"extension": ".py"}` or `{"name": "python"}`,
returns a ~1.5KB summary. Pass `{"full": true}` for the full rule.

## Validation

| Phase | Suite | Result |
|---|---|---|
| 0 | 15 prompt tool-format probe | 15/15 (100%), avg 3.0s |
| 5 | 5 realistic agentic tasks (read/grep/ls/rules/bash) | 5/5 (100%), avg 3.8s |

Run yourself:

```bash
python phase0_validate.py    # tool-format reliability
python phase5_e2e.py         # realistic task probes
```

## Token budget

| Component | Tokens | % of 32K |
|---|---|---|
| System prompt | ~2,250 | 6.8% |
| One skill (avg) | ~210 | 0.6% |
| **Fixed total** | **~2,460** | **7.5%** |
| Available for work | ~30,300 | 92.5% |

## Limitations

- 7B Q4 != Principal Engineer. Good for small-to-medium tasks; unreliable on
  large multi-file refactors or subtle architecture work.
- Tool-format reliability across runs varies 87–100% on the 15-prompt probe
  due to model stochasticity (temperature 0.2 doesn't fully eliminate it).
- The model occasionally recites EAS rules from memory instead of calling
  `get_language_rules`. Strongly worded "CALL THIS TOOL" in the prompt
  mitigates but doesn't eliminate this.
- 5-Eye review pipeline is simulated within the `/review` skill prompt;
  there is no multi-agent infrastructure here (out of scope for a single
  local model).

## Comparison vs. base shadow-code

| | Base | qwen variant |
|---|---|---|
| Default model | gemma3:27b | shadow-qwen (qwen2.5-coder:7b) |
| Modelfile | gemma stops | ChatML stops |
| Parser passes | 1 | 3 |
| EAS baseline | none | injected |
| Rule loader | none | `get_language_rules` |
| Skills | 13 | 15 (+audit, +migrate; review/test enriched) |
| Anti-hallucination block | none | yes |
