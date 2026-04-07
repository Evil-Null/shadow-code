import fnmatch
import os

from .base import BaseTool, ToolResult

# Directories to skip during walk -- never descend into these
_PRUNE_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    ".mypy_cache",
    ".tox",
    "dist",
    "build",
}

_MAX_RESULTS = 100


class GlobTool(BaseTool):
    name = "glob"

    def __init__(self, ctx):  # ctx: ToolContext
        self.ctx = ctx

    def validate(self, params: dict) -> str | None:
        if "pattern" not in params:
            return "Missing required: pattern"
        pattern = params["pattern"]
        if not isinstance(pattern, str) or not pattern.strip():
            return "pattern must be a non-empty string"
        return None

    def execute(self, params: dict) -> ToolResult:
        pattern = params["pattern"].strip()
        root = params.get("path", self.ctx.cwd)

        # Resolve relative paths against cwd
        if not os.path.isabs(root):
            root = os.path.join(self.ctx.cwd, root)
        root = os.path.normpath(root)

        if not os.path.isdir(root):
            return ToolResult(False, f"Not a directory: {root}")

        # Split pattern into directory parts and the filename glob.
        # Supports patterns like "**/*.py", "src/**/*.ts", "*.txt"
        matches = []
        has_globstar = "**" in pattern

        for dirpath, dirnames, filenames in os.walk(root):
            # Prune unwanted directories IN PLACE so os.walk skips them
            dirnames[:] = [d for d in dirnames if d not in _PRUNE_DIRS]

            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                # Get path relative to root for matching
                relpath = os.path.relpath(filepath, root)

                if _match(relpath, pattern, has_globstar):
                    try:
                        mtime = os.path.getmtime(filepath)
                    except OSError:
                        mtime = 0.0
                    matches.append((filepath, mtime))

        # Sort by modification time, newest first
        matches.sort(key=lambda x: x[1], reverse=True)

        # Cap results
        matches = matches[:_MAX_RESULTS]

        if not matches:
            return ToolResult(True, "No files matched.")

        lines = [m[0] for m in matches]
        return ToolResult(True, "\n".join(lines))


def _match(relpath: str, pattern: str, has_globstar: bool) -> bool:
    """Match a relative path against a glob pattern.

    Handles ** (globstar) by trying the filename-only part against
    the non-** portion of the pattern, and also does full path matching
    for patterns with directory components.
    """
    # Normalize to forward slashes for consistent matching
    relpath = relpath.replace(os.sep, "/")
    pattern = pattern.replace(os.sep, "/")

    if has_globstar:
        # For "**/*.py" style: ** matches any number of directories
        # Strategy: split pattern on "**/" and match the suffix against
        # every possible sub-path of relpath
        parts = pattern.split("**/")
        if len(parts) == 2:
            prefix_pattern, suffix_pattern = parts
            # prefix_pattern might be empty (pattern starts with **/)
            # or might be a dir like "src/"
            if prefix_pattern and not relpath.startswith(prefix_pattern.rstrip("/")):
                return False
            # The suffix_pattern should match the filename or trailing path
            # Try matching against every suffix of the relpath
            segments = relpath.split("/")
            for i in range(len(segments)):
                candidate = "/".join(segments[i:])
                if fnmatch.fnmatch(candidate, suffix_pattern):
                    return True
            return False
        else:
            # Multiple ** in pattern -- rare but handle it:
            # Fall back to trying fnmatch on each segment combination
            return _recursive_globstar_match(relpath, pattern)
    else:
        # No globstar -- straightforward match
        return fnmatch.fnmatch(relpath, pattern)


def _recursive_globstar_match(relpath: str, pattern: str) -> bool:
    """Handle patterns with multiple ** by expanding them."""
    # Replace ** with a marker, then try matching
    # ** should match zero or more directory segments
    import re as _re

    # Convert glob pattern to regex
    # First, split on **
    parts = pattern.split("**")
    regex_parts = []
    for _i, part in enumerate(parts):
        # Convert each non-** part from glob to regex
        converted = ""
        for ch in part:
            if ch == "*":
                converted += "[^/]*"
            elif ch == "?":
                converted += "[^/]"
            elif ch in ".+^${}\\|()":
                converted += "\\" + ch
            else:
                converted += ch
        regex_parts.append(converted)

    # Join with "anything including slashes" for **
    regex_str = "(?:.*/)?".join(regex_parts)
    regex_str = "^" + regex_str + "$"

    try:
        return bool(_re.match(regex_str, relpath))
    except _re.error:
        return False
