import os

from ..rules_loader import rule_for_filename
from .base import BaseTool, ToolResult


def _is_nontrivial_edit(content: str) -> bool:
    """True if the edit is substantive enough to warrant a language-rules nudge."""
    if len(content) > 200:
        return True
    return any(kw in content for kw in ("def ", "function ", "class ", "fn ", "func "))


def _rule_hint(ctx, path: str, content: str) -> str:
    """Return a short hint pointing the model at language rules, or empty string.

    Session-scoped dedup: each rule hinted at most once per ToolContext.
    """
    if not _is_nontrivial_edit(content):
        return ""
    rule_name = rule_for_filename(path)
    if rule_name is None:
        return ""
    rules_loaded = getattr(ctx, "rules_loaded", None)
    if rules_loaded is None or rule_name in rules_loaded:
        return ""
    rules_loaded.add(rule_name)
    return (
        f"\n\n[💡 Tip: for non-trivial {rule_name} edits, call get_language_rules "
        f"with name='{rule_name}' if you have not already this session.]"
    )


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

        # Show post-edit context so model can verify the edit looks correct
        msg = f"Replaced {replaced} occurrence(s) in {path}"
        edit_pos = new_content.find(new_string)
        if edit_pos >= 0:
            # Show ~5 lines around the edit
            before = new_content[:edit_pos]
            start = before.rfind("\n", max(0, len(before) - 300)) + 1
            after_end = new_content.find(
                "\n", min(len(new_content), edit_pos + len(new_string) + 300)
            )
            if after_end == -1:
                after_end = len(new_content)
            context = new_content[start:after_end]
            lines = context.split("\n")
            # Add line numbers
            start_line = new_content[:start].count("\n") + 1
            numbered = [f"{start_line + i:6d}\t{ln}" for i, ln in enumerate(lines)]
            msg += "\n\nContext after edit:\n" + "\n".join(numbered[:15])
        msg += _rule_hint(self.ctx, path, new_string)
        return ToolResult(True, msg)
