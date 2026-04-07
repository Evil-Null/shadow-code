import os

from .base import BaseTool, ToolResult


class EditFileTool(BaseTool):
    name = "edit_file"

    def __init__(self, ctx):  # ctx: ToolContext
        self.ctx = ctx

    def validate(self, params: dict) -> str | None:
        if "file_path" not in params:
            return "Missing required: file_path"
        if "old_string" not in params:
            return "Missing required: old_string"
        if "new_string" not in params:
            return "Missing required: new_string"
        path = params["file_path"]
        if not isinstance(path, str) or not path.startswith("/"):
            return "file_path must be an absolute path (start with /)"
        return None

    def execute(self, params: dict) -> ToolResult:
        path = os.path.abspath(params["file_path"])
        old_string = params["old_string"]
        new_string = params["new_string"]
        replace_all = params.get("replace_all", False)

        # Must have read the file first
        if not self.ctx.was_file_read(path):
            return ToolResult(
                False,
                f"File has not been read yet: {path}\n"
                "You must use read_file before editing a file.",
            )

        if old_string == new_string:
            return ToolResult(False, "old_string and new_string are identical")

        if not os.path.exists(path):
            return ToolResult(False, f"File not found: {path}")

        if os.path.isdir(path):
            return ToolResult(False, f"Path is a directory: {path}")

        # Read current content
        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(path, encoding="latin-1") as f:
                content = f.read()
        except PermissionError:
            return ToolResult(False, f"Permission denied: {path}")
        except OSError as e:
            return ToolResult(False, f"Cannot read file: {e}")

        count = content.count(old_string)

        if count == 0:
            return ToolResult(False, f"old_string not found in {path}")

        if not replace_all and count > 1:
            return ToolResult(
                False,
                f"old_string appears {count} times in {path}. "
                "Use replace_all=true to replace all, or provide a more unique string.",
            )

        # Perform replacement
        if replace_all:
            new_content = content.replace(old_string, new_string)
            replaced = count
        else:
            new_content = content.replace(old_string, new_string, 1)
            replaced = 1

        # Write back
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)
        except PermissionError:
            return ToolResult(False, f"Permission denied: {path}")
        except OSError as e:
            return ToolResult(False, f"Cannot write file: {e}")

        return ToolResult(True, f"Replaced {replaced} occurrence(s) in {path}")
