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
- Do NOT push unless explicitly asked"""
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

3. Fix any issues found directly. Don't just report -- fix them."""
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
4. Suggest fixes for each issue found"""
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
   Keep technical terms in English."""
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
6. Suggest how to verify the fix (run test, execute script, etc.)"""
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
5. Propose a concrete next step with specific code changes"""
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
- Return the PR URL when done"""
)
