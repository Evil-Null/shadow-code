from ..config import TOOL_OUTPUT_MAX_CHARS
from .base import BaseTool, ToolResult

_REGISTRY: dict[str, BaseTool] = {}


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
        result.output = _truncate(result.output)
        return result
    except Exception as e:
        return ToolResult(False, f"Tool error: {type(e).__name__}: {e}")


def _truncate(text: str) -> str:
    if len(text) <= TOOL_OUTPUT_MAX_CHARS:
        return text
    half = TOOL_OUTPUT_MAX_CHARS // 2
    removed = len(text) - TOOL_OUTPUT_MAX_CHARS
    return text[:half] + f"\n\n[...{removed} chars truncated...]\n\n" + text[-half:]


def format_result(tool_name: str, result: ToolResult) -> str:
    s = "true" if result.success else "false"
    return f'<tool_result tool="{tool_name}" success="{s}">\n{result.output}\n</tool_result>'
