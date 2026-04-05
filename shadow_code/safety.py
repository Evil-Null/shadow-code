"""Destructive command detection and user warnings.

Scans commands for dangerous patterns (rm -rf, git push --force, etc.)
and returns a warning message so the caller can prompt for confirmation.

Usage:
    from .safety import check_destructive

    warning = check_destructive("rm -rf /")
    if warning:
        # prompt user for confirmation before executing
        print(warning)
"""

import re

# Each entry: (compiled regex, human-readable description)
_DESTRUCTIVE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r'\brm\s+.*-[a-zA-Z]*r[a-zA-Z]*f\b|\brm\s+.*-[a-zA-Z]*f[a-zA-Z]*r\b|\brm\s+-rf\b'),
     "Recursive force delete (rm -rf)"),
    (re.compile(r'\bgit\s+push\s+.*--force\b|\bgit\s+push\s+-f\b'),
     "Force push (overwrites remote history)"),
    (re.compile(r'\bgit\s+reset\s+--hard\b'),
     "Hard reset (discards uncommitted changes)"),
    (re.compile(r'\bgit\s+clean\s+.*-[a-zA-Z]*f'),
     "Git clean -f (deletes untracked files)"),
    (re.compile(r'\bgit\s+branch\s+.*-D\b'),
     "Force delete branch (git branch -D)"),
    (re.compile(r'\bdrop\s+table\b', re.IGNORECASE),
     "DROP TABLE (irreversible data loss)"),
    (re.compile(r'\btruncate\s+table\b', re.IGNORECASE),
     "TRUNCATE TABLE (deletes all rows)"),
    (re.compile(r'\bdrop\s+database\b', re.IGNORECASE),
     "DROP DATABASE (irreversible data loss)"),
    (re.compile(r'\bmkfs\b'),
     "Format filesystem (mkfs)"),
    (re.compile(r'\bdd\s+if='),
     "Raw disk write (dd)"),
    (re.compile(r'\b:\(\)\s*\{\s*:\|\:\s*&\s*\}\s*;\s*:'),
     "Fork bomb"),
    (re.compile(r'>\s*/dev/sd[a-z]'),
     "Direct write to block device"),
    (re.compile(r'\bchmod\s+.*-R\s+777\b'),
     "Recursive world-writable permissions"),
    (re.compile(r'\bsudo\s+rm\b'),
     "Privileged delete (sudo rm)"),
]


def check_destructive(command: str) -> str | None:
    """Check if a command matches any destructive pattern.

    Args:
        command: The shell command string to check.

    Returns:
        A warning message string if the command is potentially destructive,
        or None if the command appears safe.
    """
    if not command or not command.strip():
        return None

    matched: list[str] = []
    for pattern, description in _DESTRUCTIVE_PATTERNS:
        if pattern.search(command):
            matched.append(description)

    if not matched:
        return None

    warnings = "; ".join(matched)
    return f"WARNING: Destructive command detected -- {warnings}. Command: {command}"
