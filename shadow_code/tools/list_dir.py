import os

from .base import BaseTool, ToolResult


class ListDirTool(BaseTool):
    name = "list_dir"

    def __init__(self, ctx):  # ctx: ToolContext
        self.ctx = ctx

    def validate(self, params: dict) -> str | None:
        # path is optional (defaults to cwd), nothing required
        return None

    def execute(self, params: dict) -> ToolResult:
        path = params.get("path", self.ctx.cwd)

        # Resolve relative paths
        if not os.path.isabs(path):
            path = os.path.join(self.ctx.cwd, path)
        path = os.path.normpath(path)

        if not os.path.exists(path):
            return ToolResult(False, f"Path not found: {path}")

        if not os.path.isdir(path):
            return ToolResult(False, f"Not a directory: {path}")

        try:
            entries = os.listdir(path)
        except PermissionError:
            return ToolResult(False, f"Permission denied: {path}")
        except OSError as e:
            return ToolResult(False, f"Error reading directory: {e}")

        dirs = []
        files = []

        for entry in entries:
            fullpath = os.path.join(path, entry)
            try:
                stat = os.lstat(fullpath)
            except (OSError, PermissionError):
                # Entry exists but can't stat -- list it as unknown
                files.append((entry, "???"))
                continue

            if os.path.isdir(fullpath):
                dirs.append(entry)
            else:
                size = _human_size(stat.st_size)
                files.append((entry, size))

        # Alphabetical sort within each group (case-insensitive)
        dirs.sort(key=str.lower)
        files.sort(key=lambda x: x[0].lower())

        lines = []
        for d in dirs:
            lines.append(f"{d}/")
        for name, size in files:
            lines.append(f"{name}  ({size})")

        if not lines:
            return ToolResult(True, "(empty directory)")

        return ToolResult(True, "\n".join(lines))


def _human_size(size_bytes: int) -> str:
    """Convert byte count to human-readable string."""
    if size_bytes < 0:
        return "0 B"

    if size_bytes < 1024:
        return f"{size_bytes} B"

    size: float = float(size_bytes)
    for unit in ("KB", "MB", "GB", "TB"):
        size /= 1024.0
        if size < 1024.0 or unit == "TB":
            if size == int(size):
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"

    return f"{size:.1f} TB"
