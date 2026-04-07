import os

from .base import BaseTool, ToolResult


class WriteFileTool(BaseTool):
    name = "write_file"

    def __init__(self, ctx):  # ctx: ToolContext
        self.ctx = ctx

    def validate(self, params: dict) -> str | None:
        if "file_path" not in params:
            return "Missing required: file_path"
        if "content" not in params:
            return "Missing required: content"
        path = params["file_path"]
        if not isinstance(path, str) or not path.startswith("/"):
            return "file_path must be an absolute path (start with /)"
        return None

    def execute(self, params: dict) -> ToolResult:
        path = os.path.abspath(params["file_path"])
        content = params["content"]
        append = params.get("append", False)

        # Append mode: add to existing file (for chunked writes of large files)
        if append:
            if not os.path.exists(path):
                return ToolResult(False, f"Cannot append -- file does not exist: {path}")
            try:
                with open(path, "a", encoding="utf-8") as f:
                    f.write(content)
                new_size = os.path.getsize(path)
                return ToolResult(
                    True, f"Appended {len(content)} chars to {path} (now {new_size} bytes)"
                )
            except (PermissionError, OSError) as e:
                return ToolResult(False, f"Cannot append to file: {e}")

        existed = os.path.exists(path)
        old_size = 0
        if existed:
            if os.path.isdir(path):
                return ToolResult(False, f"Path is a directory: {path}")
            if not self.ctx.was_file_read(path):
                return ToolResult(
                    False,
                    f"File has not been read yet: {path}\n"
                    "You must use read_file before overwriting an existing file.",
                )
            try:
                old_size = os.path.getsize(path)
            except OSError:
                old_size = 0

        # Auto-create parent directories
        parent = os.path.dirname(path)
        try:
            os.makedirs(parent, exist_ok=True)
        except OSError as e:
            return ToolResult(False, f"Cannot create directory {parent}: {e}")

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        except PermissionError:
            return ToolResult(False, f"Permission denied: {path}")
        except OSError as e:
            return ToolResult(False, f"Cannot write file: {e}")

        new_size = os.path.getsize(path)

        if existed:
            return ToolResult(True, f"Updated file: {path} ({old_size} -> {new_size} bytes)")
        else:
            return ToolResult(True, f"Created new file: {path} ({new_size} bytes)")
