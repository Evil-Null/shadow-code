Run the full verification pipeline for shadow-code. Execute each step sequentially and stop on first failure.

## Steps

1. **Lint**: `ruff check shadow_code/ tests/`
2. **Format**: `ruff format --check shadow_code/ tests/`
3. **Type check**: `mypy shadow_code/ --ignore-missing-imports --disable-error-code=import-untyped`
4. **Security scan**: `bandit -r shadow_code/ -c pyproject.toml -q`
5. **Tests + coverage**: `python3 -m pytest tests/ --cov=shadow_code --cov-report=term-missing --cov-fail-under=80 -q`

## Output

Report each step as PASS or FAIL with the error output. At the end, print a summary:

```
Verify: 5/5 PASS  (or N/5 PASS, list failures)
```

If any step fails, show the first 20 lines of error output and suggest the fix command (e.g. `ruff check --fix` for lint errors, `ruff format` for format errors).

## Arguments

$ARGUMENTS - optional: `--fix` to auto-fix lint and format issues before checking
