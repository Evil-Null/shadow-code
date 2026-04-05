# Agent Workflow Rules

## Agent Structure (per task)

```
Task
  |
  v
Agent A + Agent B (implementors, parallel, isolated files)
  |          |
  |   RULE 1: Read ROLE.md + PLAN_FINAL.md FIRST
  |   RULE 2: Verify what needs to be done BEFORE coding
  |   RULE 3: Work on non-overlapping files (no conflicts)
  |   RULE 4: Implement to elite standard
  |
  v
Agent C + Agent D (verifiers, parallel)
  |          |
  |   Same RULE 1: Read ROLE.md + PLAN_FINAL.md
  |   Verify implementors' output against the plan
  |   Check: correctness, completeness, edge cases
  |   Report: PASS / FAIL with details
  |
  v
Main (me) -- final verification
  |
  |   Trust nothing. Verify everything.
  |   Read actual files, run tests, check edge cases.
  |   Fix any issues found.
  |
  v
DONE (only when I confirm)
```

## Agent Mandatory Preamble

Every agent MUST start with:
1. Read /home/n00b/makho/shadow-code/ROLE.md
2. Read /home/n00b/makho/shadow-code/PLAN_FINAL.md (relevant section)
3. Verify understanding of the task
4. Then and ONLY then start implementation/verification

## File Ownership (no conflicts)

Agents working in parallel MUST NOT edit the same file.
Split by file ownership -- Agent A owns files X,Y; Agent B owns files Z,W.

## Verification Standard

Verifiers check:
- Code matches PLAN_FINAL.md specification exactly
- All edge cases from Error Handling matrix covered
- No placeholder code, no TODO/FIXME
- Imports resolve, types correct, logic sound
- Consistent with other files in the project
