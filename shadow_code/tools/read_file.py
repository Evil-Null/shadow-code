import os
from .base import BaseTool, ToolResult
from ..config import MAX_LINES_TO_READ, BLOCKED_PATHS


class ReadFileTool(BaseTool):
    name = "read_file"

    def __init__(self, ctx):  # ctx: ToolContext
        self.ctx = ctx

    def validate(self, params: dict) -> str | None:
        if "file_path" not in params:
            return "Missing required: file_path"
        path = params["file_path"]
        if not isinstance(path, str) or not path.startswith("/"):
            return "file_path must be an absolute path (start with /)"
        return None

    def execute(self, params: dict) -> ToolResult:
        path = os.path.abspath(params["file_path"])

        # Block dangerous paths
        for blocked in BLOCKED_PATHS:
            if path == blocked or path.startswith(blocked + "/"):
                return ToolResult(False, f"Blocked path: {path}")

        if not os.path.exists(path):
            return ToolResult(False, f"File not found: {path}")

        if os.path.isdir(path):
            return ToolResult(False, f"Path is a directory, not a file: {path}")

        # Binary detection: check first 8KB for null bytes
        try:
            with open(path, "rb") as f:
                chunk = f.read(8192)
            if b"\x00" in chunk:
                size = os.path.getsize(path)
                return ToolResult(False, f"Binary file detected ({size} bytes): {path}")
        except PermissionError:
            return ToolResult(False, f"Permission denied: {path}")
        except OSError as e:
            return ToolResult(False, f"Cannot read file: {e}")

        # Read with encoding fallback
        try:
            with open(path, "r", encoding="utf-8") as f:
                all_lines = f.readlines()
        except UnicodeDecodeError:
            with open(path, "r", encoding="latin-1") as f:
                all_lines = f.readlines()

        total = len(all_lines)
        offset = max(params.get("offset", 1), 1)  # 1-based, default 1
        limit = params.get("limit", MAX_LINES_TO_READ)

        # Slice lines (offset is 1-based)
        start_idx = offset - 1
        end_idx = start_idx + limit
        lines = all_lines[start_idx:end_idx]

        if not lines and total > 0:
            return ToolResult(False, f"Offset {offset} is beyond file length ({total} lines)")

        # Format with cat -n style line numbers (6-char right-aligned + tab)
        formatted = []
        for i, line in enumerate(lines, start=offset):
            # Remove trailing newline for consistent formatting
            content = line.rstrip("\n").rstrip("\r")
            formatted.append(f"{i:6d}\t{content}")

        self.ctx.mark_file_read(path)

        output = "\n".join(formatted)

        # Add truncation notice if file has more lines
        if end_idx < total:
            remaining = total - end_idx
            output += f"\n\n({remaining} more lines not shown. Use offset/limit to read more.)"

        return ToolResult(True, output if output else "(empty file)")
