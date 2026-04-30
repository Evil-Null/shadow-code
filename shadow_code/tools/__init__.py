from ..config import TOOL_OUTPUT_MAX_CHARS
from .base import BaseTool, ToolResult

_REGISTRY: dict[str, BaseTool] = {}

# Per-tool output limits (override global TOOL_OUTPUT_MAX_CHARS)
_TOOL_OUTPUT_LIMITS: dict[str, int] = {
    "bash": 15_000,
    "read_file": 30_000,
    "multi_read": 30_000,
    "grep": 10_000,
    "list_dir": 5_000,
    "glob": 5_000,
    "edit_file": 5_000,
    "write_file": 2_000,
    "file_backup": 1_000,
    "file_restore": 1_000,
    "get_language_rules": 5_000,
    "project_summary": 10_000,
}


def register(tool: BaseTool):
    _REGISTRY[tool.name] = tool


def dispatch(name: str, params: dict) -> ToolResult:
    tool = _REGISTRY.get(name)
    if not tool:
        avail = ", ".join(_REGISTRY.keys())
        return ToolResult(False, f"Unknown tool: '{name}'. Available: {avail}")
    err = tool.validate(params)
    if err:
        return ToolResult(False, f"Invalid parameters: {err}")
    try:
        result = tool.execute(params)
        limit = _TOOL_OUTPUT_LIMITS.get(name, TOOL_OUTPUT_MAX_CHARS)
        result.output = _truncate(result.output, limit)
        return result
    except Exception as e:
        return ToolResult(False, f"Tool error: {type(e).__name__}: {e}")


def _truncate(text: str, max_chars: int = TOOL_OUTPUT_MAX_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    removed = len(text) - max_chars
    return text[:half] + f"\n\n[...{removed} chars truncated...]\n\n" + text[-half:]


def format_result(tool_name: str, result: ToolResult) -> str:
    s = "true" if result.success else "false"
    return f'<tool_result tool="{tool_name}" success="{s}">\n{result.output}\n</tool_result>'
