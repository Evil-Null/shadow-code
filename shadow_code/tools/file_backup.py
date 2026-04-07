"""In-memory file backup and restore for safe editing.

Allows the model to backup a file before risky edits, then restore
if the edit breaks something. No disk writes for backups.
"""

import os

from .base import BaseTool, ToolResult


class FileBackupTool(BaseTool):
    name = "file_backup"

    def __init__(self, ctx):
        self.ctx = ctx

    def validate(self, params: dict) -> str | None:
        if "file_path" not in params:
            return "Missing required: file_path"
        path = params["file_path"]
        if not isinstance(path, str) or not path.startswith("/"):
            return "file_path must be an absolute path"
        return None

    def execute(self, params: dict) -> ToolResult:
        path = os.path.abspath(params["file_path"])

        if not os.path.exists(path):
            return ToolResult(False, f"File not found: {path}")
        if os.path.isdir(path):
            return ToolResult(False, f"Path is a directory: {path}")

        try:
            with open(path, "rb") as f:
                content = f.read()
        except (PermissionError, OSError) as e:
            return ToolResult(False, f"Cannot read file: {e}")

        self.ctx.backups[path] = content
        return ToolResult(True, f"Backed up {path} ({len(content)} bytes)")


class FileRestoreTool(BaseTool):
    name = "file_restore"

    def __init__(self, ctx):
        self.ctx = ctx

    def validate(self, params: dict) -> str | None:
        if "file_path" not in params:
            return "Missing required: file_path"
        return None

    def execute(self, params: dict) -> ToolResult:
        path = os.path.abspath(params["file_path"])

        if path not in self.ctx.backups:
            available = list(self.ctx.backups.keys())
            if available:
                return ToolResult(False, f"No backup for {path}. Available: {', '.join(available)}")
            return ToolResult(False, f"No backup for {path}. No backups exist.")

        try:
            with open(path, "wb") as f:
                f.write(self.ctx.backups[path])
        except (PermissionError, OSError) as e:
            return ToolResult(False, f"Cannot restore file: {e}")

        size = len(self.ctx.backups[path])
        del self.ctx.backups[path]
        return ToolResult(True, f"Restored {path} from backup ({size} bytes)")
