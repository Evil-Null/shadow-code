import os
import re
import shutil
import subprocess  # nosec B404 - subprocess is required for running rg/grep

from .base import BaseTool, ToolResult

_DEFAULT_MAX_RESULTS = 200

# Directories to exclude from search
_EXCLUDE_DIRS = {".git", "node_modules", "__pycache__", ".venv"}

# Binary detection: check first 8KB for null bytes
_BINARY_CHECK_SIZE = 8192


class GrepTool(BaseTool):
    name = "grep"

    def __init__(self, ctx):  # ctx: ToolContext
        self.ctx = ctx

    def validate(self, params: dict) -> str | None:
        if "pattern" not in params:
            return "Missing required: pattern"
        pattern = params["pattern"]
        if not isinstance(pattern, str) or not pattern.strip():
            return "pattern must be a non-empty string"
        # Validate regex
        try:
            re.compile(pattern)
        except re.error as e:
            return f"Invalid regex: {e}"
        return None

    def execute(self, params: dict) -> ToolResult:
        pattern = params["pattern"]
        path = params.get("path", self.ctx.cwd)
        include = params.get("include")
        case_insensitive = params.get("case_insensitive", False)
        max_results = params.get("max_results", _DEFAULT_MAX_RESULTS)

        # Resolve relative paths
        if not os.path.isabs(path):
            path = os.path.join(self.ctx.cwd, path)
        path = os.path.normpath(path)

        if not os.path.exists(path):
            return ToolResult(False, f"Path not found: {path}")

        # Try 3-tier fallback
        result = _try_ripgrep(pattern, path, include, case_insensitive, max_results)
        if result is not None:
            return result

        result = _try_system_grep(pattern, path, include, case_insensitive, max_results)
        if result is not None:
            return result

        return _python_grep(pattern, path, include, case_insensitive, max_results)


def _try_ripgrep(
    pattern: str,
    path: str,
    include: str | None,
    case_insensitive: bool,
    max_results: int,
) -> ToolResult | None:
    """Tier 1: Try ripgrep (rg). Returns None if rg is not available."""
    rg = shutil.which("rg")
    if not rg:
        return None

    cmd = [rg, "--no-heading", "--line-number", "--color", "never", "--with-filename"]
    cmd += [f"--max-count={max_results}"]

    if case_insensitive:
        cmd.append("-i")

    # Exclude directories
    for d in _EXCLUDE_DIRS:
        cmd += [f"--glob=!{d}"]

    # File type filter
    if include:
        cmd += [f"--glob={include}"]

    cmd += [pattern, path]

    try:
        proc = subprocess.run(  # nosec B603 - cmd is constructed internally, not from user input
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        return None
    except subprocess.TimeoutExpired:
        return ToolResult(False, "Search timed out after 30s")
    except Exception:
        return None  # Fall through to next tier

    if proc.returncode == 2:
        # rg returns 2 on error
        return None  # Fall through

    output = proc.stdout.strip()
    if not output:
        return ToolResult(True, "No matches found.")

    lines = output.split("\n")
    if len(lines) > max_results:
        lines = lines[:max_results]
    return ToolResult(True, "\n".join(lines))


def _try_system_grep(
    pattern: str,
    path: str,
    include: str | None,
    case_insensitive: bool,
    max_results: int,
) -> ToolResult | None:
    """Tier 2: Try system grep -rn. Returns None if grep fails."""
    grep = shutil.which("grep")
    if not grep:
        return None

    cmd = [grep, "-rnH", "--color=never", "--binary-files=without-match"]

    if case_insensitive:
        cmd.append("-i")

    # Exclude directories
    for d in _EXCLUDE_DIRS:
        cmd += [f"--exclude-dir={d}"]

    # File type filter
    if include:
        cmd += [f"--include={include}"]

    cmd += [pattern, path]

    try:
        proc = subprocess.run(  # nosec B603 - cmd is constructed internally, not from user input
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        return None
    except subprocess.TimeoutExpired:
        return ToolResult(False, "Search timed out after 30s")
    except Exception:
        return None  # Fall through to Python

    if proc.returncode > 1:
        # grep returns 2+ on error
        return None

    output = proc.stdout.strip()
    if not output:
        return ToolResult(True, "No matches found.")

    lines = output.split("\n")
    if len(lines) > max_results:
        lines = lines[:max_results]
    return ToolResult(True, "\n".join(lines))


def _python_grep(
    pattern: str,
    path: str,
    include: str | None,
    case_insensitive: bool,
    max_results: int,
) -> ToolResult:
    """Tier 3: Pure Python fallback using re + os.walk. Always works."""
    import fnmatch

    flags = re.IGNORECASE if case_insensitive else 0
    try:
        compiled = re.compile(pattern, flags)
    except re.error as e:
        return ToolResult(False, f"Invalid regex: {e}")

    matches: list[str] = []

    # Handle single file
    if os.path.isfile(path):
        _search_file(path, compiled, matches, max_results)
        if not matches:
            return ToolResult(True, "No matches found.")
        return ToolResult(True, "\n".join(matches))

    for dirpath, dirnames, filenames in os.walk(path):
        # Prune excluded directories in place
        dirnames[:] = [d for d in dirnames if d not in _EXCLUDE_DIRS]

        for filename in filenames:
            # Apply include filter
            if include and not fnmatch.fnmatch(filename, include):
                continue

            filepath = os.path.join(dirpath, filename)
            _search_file(filepath, compiled, matches, max_results)

            if len(matches) >= max_results:
                break
        if len(matches) >= max_results:
            break

    if not matches:
        return ToolResult(True, "No matches found.")
    return ToolResult(True, "\n".join(matches))


def _search_file(
    filepath: str,
    compiled: re.Pattern,
    matches: list[str],
    max_results: int,
) -> None:
    """Search a single file, appending matches to the list."""
    if len(matches) >= max_results:
        return

    # Skip binary files
    try:
        with open(filepath, "rb") as f:
            chunk = f.read(_BINARY_CHECK_SIZE)
            if b"\x00" in chunk:
                return
    except (OSError, PermissionError):
        return

    try:
        with open(filepath, encoding="utf-8", errors="replace") as f:
            for line_num, line in enumerate(f, 1):
                if compiled.search(line):
                    # Strip trailing newline for clean output
                    matches.append(f"{filepath}:{line_num}:{line.rstrip()}")
                    if len(matches) >= max_results:
                        return
    except (OSError, PermissionError, UnicodeDecodeError):
        return
