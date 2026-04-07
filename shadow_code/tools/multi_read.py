"""Read multiple files in a single tool call.

Saves 5-9 turns when orienting in a new project. Instead of calling
read_file 10 times (10 turns), call multi_read once (1 turn).
"""

import os

from ..config import BLOCKED_PATHS, MAX_LINES_TO_READ
from .base import BaseTool, ToolResult

_MAX_FILES = 10
_PER_FILE_LINE_LIMIT = 200  # Shorter per-file to fit multiple files in output


class MultiReadTool(BaseTool):
    name = "multi_read"

    def __init__(self, ctx):
        self.ctx = ctx

    def validate(self, params: dict) -> str | None:
        if "paths" not in params:
            return "Missing required: paths (list of absolute file paths)"
        paths = params["paths"]
        if not isinstance(paths, list) or not paths:
            return "paths must be a non-empty list of file paths"
        if len(paths) > _MAX_FILES:
            return f"Maximum {_MAX_FILES} files per call"
        for p in paths:
            if not isinstance(p, str) or not p.startswith("/"):
                return f"All paths must be absolute (start with /): {p}"
        return None

    def execute(self, params: dict) -> ToolResult:
        paths = params["paths"]
        limit = min(params.get("limit", _PER_FILE_LINE_LIMIT), MAX_LINES_TO_READ)
        results = []

        for path in paths:
            path = os.path.abspath(path)

            # Block dangerous paths
            if any(path == b or path.startswith(b + "/") for b in BLOCKED_PATHS):
                results.append(f"=== {path} ===\n[BLOCKED PATH]")
                continue

            if not os.path.exists(path):
                results.append(f"=== {path} ===\n[NOT FOUND]")
                continue

            if os.path.isdir(path):
                results.append(f"=== {path} ===\n[IS A DIRECTORY]")
                continue

            # Binary check
            try:
                with open(path, "rb") as f:
                    if b"\x00" in f.read(8192):
                        results.append(f"=== {path} ===\n[BINARY FILE]")
                        continue
            except (OSError, PermissionError):
                results.append(f"=== {path} ===\n[PERMISSION DENIED]")
                continue

            # Read file
            try:
                with open(path, encoding="utf-8") as f:
                    lines = f.readlines()
            except UnicodeDecodeError:
                with open(path, encoding="latin-1") as f:
                    lines = f.readlines()

            total = len(lines)
            shown = lines[:limit]
            formatted = []
            for i, line in enumerate(shown, start=1):
                formatted.append(f"{i:6d}\t{line.rstrip()}")

            header = f"=== {path} ({total} lines) ==="
            body = "\n".join(formatted)
            if total > limit:
                body += f"\n\n({total - limit} more lines not shown)"
            results.append(f"{header}\n{body}")

            self.ctx.mark_file_read(path)

        return ToolResult(True, "\n\n".join(results))
