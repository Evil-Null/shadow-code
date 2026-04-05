# Phase 0: Validation Results

Date: 2026-04-05

## Test 0.1: Format Comparison

| Format | Description | Score | Notes |
|--------|-------------|-------|-------|
| A | `<tool_call>` XML tags | 5/5 (simple), 0/5 (complex) | Model switches to B on complex prompts |
| B | ` ```tool_call ` markdown | **5/5 all cases** | Model's natural preference |
| C | `>>>TOOL ... TOOL<<<` | 3/3 | Works but unnatural |

**WINNER: Format B (markdown code blocks)**

The model (Gemma 3, 27.4B) naturally produces ```tool_call blocks even when instructed to use XML tags. This is likely from training data where code/JSON is in markdown blocks.

## Test 0.2: Multi-turn

Format B multi-turn: VALID on turn 2+
Model correctly uses read_file after bash results returned.

## Test 0.4: Temperature

| Temp | Score (Format B) |
|------|-----------------|
| 0.1  | 5/5 |
| 0.3  | 5/5 |
| 0.5  | 5/5 |
| 0.7  | 5/5 |

All temperatures reliable. Choosing **0.3** for precision.

## Decisions

- **Tool call format:** ` ```tool_call\n{JSON}\n``` `
- **Temperature:** 0.3
- **Parser regex:** ` ```tool_call\s*\n(.*?)\n``` `
- **Few-shot style:** JSON examples work perfectly (model follows format naturally)
- **Prompt length:** Short prompts work, full prompts also work (model doesn't degrade)

## Impact on PLAN_FINAL.md

1. Change all `<tool_call>` references to ` ```tool_call `
2. Change all `</tool_call>` to closing ` ``` `
3. Update parser.py regex
4. Update display.py buffer tags
5. Update tool result format (keep `<tool_result>` -- this is system-generated, not model-generated)
