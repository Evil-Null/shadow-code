# Shadow Code Architecture Upgrade Plan

> Status: Phase 1 complete, Phase 2-4 pending
> Model: Gemma 3 27B Q4_K_M (131K context)

## Phase 1: Quick Wins (DONE)

- [x] num_predict 2048 -> 8192 -> 16384
- [x] repeat_penalty 1.1 -> 1.05
- [x] temperature 0.9 -> 0.3
- [x] penalize_newline = false
- [x] min_p = 0.05
- [x] Remove Modelfile SYSTEM prompt conflict
- [x] Remove "short and concise" from prompt
- [x] Remove 6 restrictive instructions from prompt
- [x] Add "write COMPLETE PRODUCTION-READY code"
- [x] Compress tool descriptions 88 -> 20 lines
- [x] Relax context thresholds (55->65%, 65->75%, 85->90%)
- [x] Simplify compaction prompt (9 -> 4 sections)

## Phase 2: Core Tools & Context (TODO)

### New Tools
- [ ] `multi_read` -- read up to 10 files in one call (saves 5-9 turns per task)
- [ ] `project_summary` -- auto-detect language/framework/structure in one call
- [ ] `file_backup` / `file_restore` -- in-memory undo for risky edits
- [ ] `write_file` append mode -- chunked writes for files >150 lines

### Context Intelligence
- [ ] Differentiated result clearing (read_file priority 3, list_dir priority 0)
- [ ] Proactive context budget checking (before sending to Ollama, not after)
- [ ] Per-tool output size limits (bash 15K, grep 10K, list_dir 5K)
- [ ] Progress-aware tool results: `[Turn 5/20]` prefix
- [ ] Original request echo in early turns

### Edit Quality
- [ ] Post-edit context in edit_file results (show surrounding lines after edit)
- [ ] Smarter compaction with "Files Modified" + "Key Code Details" sections

## Phase 3: Intelligence Layer (TODO)

### Self-Correction
- [ ] Auto-verification injection after write_file/edit_file (syntax check suggestion)
- [ ] Error reflection injection at 3 consecutive errors (forced reasoning)
- [ ] Error pattern detection (same tool failing -> specific guidance)

### Reasoning Scaffold
- [ ] "Before Acting" section: STATE goal, LIST steps, EXECUTE, VERIFY
- [ ] "Common Mistakes" section before prompt closing (recency effect)
- [ ] Per-tool JSON examples in system prompt (7 tools x ~200 tokens each)

### Codebase Awareness
- [ ] `.shadow-code/project.json` -- cached project index (language, structure, deps)
- [ ] Auto-inject CLAUDE.md/SHADOW.md into first message
- [ ] Python import dependency graph for navigation

## Phase 4: Polish (TODO)

- [ ] Adaptive turn limits per skill (commit=10, refactor=30)
- [ ] `diff` tool -- dedicated file comparison
- [ ] `search_replace` tool -- multi-file refactoring in one call
- [ ] Sliding window message management
- [ ] Dynamic temperature (higher when stuck in error loops)
- [ ] Structured response format guidance (Analysis -> Plan -> Implement -> Verify)

## Impact Estimates

| Metric | Before | After Phase 1 | After Phase 4 |
|--------|--------|---------------|---------------|
| Max output tokens | 2,048 | 16,384 | 16,384 |
| Tool call success rate | ~60% | ~80% | ~95% |
| Multi-step completion | ~30% | ~50% | ~80% |
| Session startup turns | 5-10 | 5-10 | 0-1 |
| Prompt tokens | 4,481 | 2,261 | ~3,500 |
| Useful context retention | ~50% | ~70% | ~90% |

## Key Principle

ყველა ცვლილება მოდელის **ხელებს ხსნის** -- არ ამატებს ახალ შესაძლებლობებს,
არამედ აშორებს ბარიერებს რომლებიც Claude Code-ის prompt-იდან მოვიდა.
Gemma 3 27B ≠ Claude 3.5 Sonnet. სხვა მოდელს სხვა ინსტრუქციები სჭირდება.
