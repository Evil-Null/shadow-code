"""Skill system for shadow-code.

Skills are pre-built prompt templates activated by /command.
Adapted from Claude Code's bundled skills system.

Usage in REPL:
    /commit          -- create a git commit
    /simplify        -- review changed code for quality
    /review          -- review a specific file
    /explain         -- explain code in detail
    /debug           -- debug an error or issue
    /stuck           -- get help when stuck

Each skill injects a detailed prompt that guides the model
through a specific workflow with the available tools.
"""

# Skill registry: name -> (description, prompt_template)
_SKILLS: dict[str, tuple[str, str]] = {}


def register_skill(name: str, description: str, prompt: str):
    """Register a skill with its prompt template."""
    _SKILLS[name] = (description, prompt)


def get_skill(name: str) -> tuple[str, str] | None:
    """Get skill (description, prompt) by name, or None if not found."""
    return _SKILLS.get(name)


def list_skills() -> list[tuple[str, str]]:
    """Return list of (name, description) for all registered skills."""
    return [(name, desc) for name, (desc, _) in sorted(_SKILLS.items())]


# ==========================================================================
# Built-in Skills (adapted from Claude Code bundled skills)
# ==========================================================================

register_skill(
    "commit",
    "Create a git commit with staged changes",
    """Create a git commit. Follow these steps:

1. Run git status and git diff to see all changes (staged and unstaged).
2. Run git log --oneline -5 to see recent commit message style.
3. Analyze the changes and draft a concise commit message:
   - Focus on WHY, not WHAT
   - 1-2 sentences maximum
   - Match the repository's existing commit style
4. Do NOT commit files that likely contain secrets (.env, credentials.json)
5. Stage specific files by name (not git add -A or git add .)
6. Create the commit

Git Safety:
- NEVER skip hooks (--no-verify)
- NEVER amend unless explicitly asked
- If pre-commit hook fails, fix the issue and create a NEW commit
- Do NOT push unless explicitly asked""",
)

register_skill(
    "simplify",
    "Review changed code for reuse, quality, and efficiency",
    """Review all changed files for code quality. Follow these steps:

1. Run git diff (or git diff HEAD for staged changes) to see what changed.
2. For each change, check:

Code Reuse:
- Search for existing utilities that could replace new code
- Flag duplicated functionality
- Flag inline logic that could use existing helpers

Code Quality:
- Redundant state or unnecessary caching
- Copy-paste with slight variation (should be unified)
- Leaky abstractions
- Unnecessary comments (WHAT not WHY)

Efficiency:
- Redundant computations or repeated file reads
- N+1 patterns
- Unnecessary string concatenation in loops
- Large objects copied when a reference would work

3. Fix any issues found directly. Don't just report -- fix them.""",
)

register_skill(
    "review",
    "Review a specific file for bugs, quality, security",
    """Review the specified file (or recently modified files if none specified).

1. Read the file completely with read_file
2. Check for:
   - Logic bugs and edge cases
   - Security vulnerabilities (injection, path traversal, etc.)
   - Error handling gaps
   - Performance issues
   - Code style and readability
3. Report findings with file_path:line_number references
4. Suggest fixes for each issue found""",
)

register_skill(
    "explain",
    "Explain code in detail",
    """Explain the specified code file or function in detail.

1. Read the file with read_file
2. Explain:
   - Purpose and high-level design
   - Key functions and their roles
   - Data flow and control flow
   - Dependencies and interactions with other modules
   - Any non-obvious logic or clever patterns
3. Use clear language. If the user writes in Georgian, explain in Georgian.
   Keep technical terms in English.""",
)

register_skill(
    "debug",
    "Debug an error or issue",
    """Help debug the reported error or issue.

1. Read any error messages or logs the user provided
2. Read the relevant source files with read_file
3. Search for related code with grep if needed
4. Identify the root cause:
   - Check the error location (file:line)
   - Trace the data flow that leads to the error
   - Check edge cases and error handling
5. Fix the issue with edit_file
6. Suggest how to verify the fix (run test, execute script, etc.)""",
)

register_skill(
    "stuck",
    "Get help when stuck on a problem",
    """The user is stuck. Help them get unstuck.

1. Ask clarifying questions if the problem is unclear
2. Read relevant code with read_file
3. Search the codebase with grep/glob for related patterns
4. Consider multiple approaches:
   - What's the simplest solution?
   - What does the existing codebase do in similar cases?
   - Are there any constraints or requirements being missed?
5. Propose a concrete next step with specific code changes""",
)

register_skill(
    "pr",
    "Create a pull request",
    """Create a pull request. Follow these steps:

1. Run these commands to understand the branch:
   - git status (see all changes)
   - git diff main...HEAD (or appropriate base branch)
   - git log main..HEAD --oneline (all commits on this branch)

2. Analyze ALL commits (not just the latest) and draft:
   - PR title: short, under 70 characters
   - PR body: summary (1-3 bullets), test plan (checklist)

3. Push and create PR:
   - Push with -u flag if needed
   - Use gh pr create with the title and body

Important:
- Look at ALL commits, not just the most recent
- Return the PR URL when done""",
)

register_skill(
    "remember",
    "Save important information for future reference",
    """The user wants to save something for future reference.

1. Understand what they want to remember:
   - A decision that was made and why
   - A pattern or convention used in this project
   - A bug fix approach that worked
   - A configuration detail
   - User preferences for how to work

2. Create or update a memory file:
   - Save to ~/.shadow-code/memory/ directory
   - Use descriptive filenames (e.g., "db-migration-pattern.md", "user-preferences.md")
   - Include: WHAT, WHY, and WHEN (date)
   - Keep it concise but complete enough to be useful later

3. If the user says "remember that..." or "don't forget...", extract the key
   information and save it without asking unnecessary questions.

4. If asked "what do you remember about X?", search the memory directory
   with glob and grep for relevant files.""",
)

register_skill(
    "verify",
    "Verify that code changes actually work",
    """Verify that recent code changes work correctly.

1. Identify what was changed:
   - Run git diff to see recent changes
   - Or check the conversation for files that were edited

2. For each change, determine how to verify:
   - If tests exist: run them (e.g., pytest, npm test, go test)
   - If it's a script: execute it and check output
   - If it's a server: start it and check it responds
   - If it's a build: run the build and check for errors

3. Run the verification:
   - Execute the appropriate test/build/run command
   - Capture and analyze the output
   - Report: PASS (with evidence) or FAIL (with error details)

4. If verification fails:
   - Identify the root cause
   - Fix the issue
   - Re-verify

IMPORTANT: Actually run the verification. Do not claim "should work" --
prove it works by executing code and showing output.""",
)

register_skill(
    "init",
    "Initialize shadow-code for a new project",
    """Set up shadow-code for working with a new project directory.

1. Explore the project structure:
   - Run list_dir to see top-level files and directories
   - Look for configuration files (package.json, pyproject.toml, Makefile, etc.)
   - Look for README.md or documentation
   - Check if it's a git repository (git status)

2. Identify the project type:
   - Language (Python, JavaScript/TypeScript, Go, Rust, etc.)
   - Framework (React, Django, FastAPI, etc.)
   - Build system (npm, pip, cargo, make, etc.)
   - Test framework (pytest, jest, go test, etc.)

3. Report findings to the user:
   - Project type and language
   - Key directories and their purpose
   - Available commands (build, test, run)
   - Any issues found (missing dependencies, broken config)

4. Suggest next steps based on what was found.""",
)

register_skill(
    "test",
    "Run tests and analyze results",
    """Run the project's test suite and analyze results.

1. Detect the test framework:
   - Python: look for pytest.ini, setup.cfg, pyproject.toml [tool.pytest]
   - JavaScript: look for jest.config, vitest.config, package.json scripts
   - Go: go test ./...
   - Rust: cargo test
   - Or ask the user if unclear

2. Run the tests:
   - Use the appropriate command (pytest, npm test, etc.)
   - Capture full output including failures

3. Analyze results:
   - Count passed/failed/skipped
   - For failures: show the error, identify the failing test, suggest fix
   - For errors: distinguish between test bugs and code bugs

4. If tests fail:
   - Read the failing test file
   - Read the source code being tested
   - Identify the root cause
   - Fix and re-run""",
)

register_skill(
    "refactor",
    "Refactor code while preserving behavior",
    """Refactor the specified code (file, function, or module).

1. Read and understand the code completely with read_file
2. Identify what to improve:
   - Long functions that should be split
   - Duplicated code that should be extracted
   - Complex conditionals that should be simplified
   - Poor naming that should be clarified
   - Tight coupling that should be loosened

3. Plan the refactoring:
   - List each change you'll make
   - Ensure behavior is preserved (no functional changes)
   - Consider: will existing tests still pass?

4. Execute changes with edit_file:
   - Make one logical change at a time
   - After each change, verify the code is still valid

5. Verify:
   - If tests exist, run them
   - If no tests, explain what you changed and why it's safe""",
)

register_skill(
    "search",
    "Deep search across the codebase",
    """Perform a thorough search across the codebase.

1. Understand what the user is looking for:
   - A specific function, class, or variable?
   - A pattern or convention?
   - Where something is used?
   - How something is implemented?

2. Use multiple search strategies:
   - grep for exact text matches
   - glob for file name patterns
   - grep with regex for pattern matching
   - Read key files that are likely relevant

3. Report findings:
   - List all matches with file_path:line_number
   - Show relevant code context
   - Explain how the pieces connect

4. If searching for usage: trace the call chain from definition to all callers.""",
)
