"""Theme system for shadow-code CLI.

Centralized color palette and unicode symbols with terminal compatibility.
Designed for Gemma 3's coding assistant UI -- Claude Code inspired aesthetics.
"""

import os
import sys
from dataclasses import dataclass


def _supports_unicode() -> bool:
    """Check if the terminal supports unicode output."""
    if os.name == "nt":
        return os.environ.get("WT_SESSION") is not None  # Windows Terminal
    encoding = getattr(sys.stdout, "encoding", "") or ""
    return "utf" in encoding.lower()


@dataclass(frozen=True)
class Theme:
    """Semantic color palette for the shadow-code UI."""

    # Brand identity
    brand: str = "#d77757"  # Claude orange
    brand_dim: str = "#a85a3e"

    # Text hierarchy
    text_primary: str = "#e0e0e0"
    text_secondary: str = "#aaaaaa"
    text_dim: str = "#888888"
    text_muted: str = "#666666"

    # Status colors
    success: str = "#5faf5f"
    success_dim: str = "#3d7a3d"
    error: str = "#d75f5f"
    error_dim: str = "#a84545"
    warning: str = "#d7af5f"
    warning_dim: str = "#a8873d"
    info: str = "#5f87d7"
    info_dim: str = "#4568a8"

    # Semantic
    tool: str = "#5f87d7"
    accent: str = "#af87d7"
    thinking: str = "#d7af5f"
    highlight: str = "#5fd7ff"

    # Diff colors
    diff_added: str = "#5faf5f"
    diff_added_bg: str = "#1a3a1a"
    diff_removed: str = "#d75f5f"
    diff_removed_bg: str = "#3a1a1a"
    diff_context: str = "#888888"

    # Effort level
    effort_low: str = "#5faf5f"
    effort_mid: str = "#d7af5f"
    effort_high: str = "#d75f5f"

    # Context bar
    bar_low: str = "#5faf5f"
    bar_mid: str = "#d7af5f"
    bar_high: str = "#d75f5f"


class Symbols:
    """Unicode symbols with automatic ASCII fallback."""

    def __init__(self, unicode_supported: bool | None = None):
        use_unicode = unicode_supported if unicode_supported is not None else _supports_unicode()

        if use_unicode:
            # Status
            self.thinking = "\u23fa"  # ⏺
            self.success = "\u2713"  # ✓
            self.error = "\u2717"  # ✗
            self.warning = "\u26a0"  # ⚠
            self.info = "\u2139"  # ℹ

            # Navigation
            self.tool = "\u25b6"  # ▶
            self.arrow = "\u25b8"  # ▸
            self.diamond_filled = "\u25c6"  # ◆
            self.diamond_empty = "\u25c7"  # ◇
            self.lightning = "\u21af"  # ↯

            # Decorative
            self.bar = "\u258e"  # ▎
            self.line_heavy = "\u2501"  # ━
            self.line_light = "\u254c"  # ╌
            self.dot = "\u2219"  # ∙
            self.bullet = "\u2022"  # •

            # Effort level
            self.effort_low = "\u25cb"  # ○
            self.effort_mid = "\u25d0"  # ◐
            self.effort_high = "\u25cf"  # ●

            # Progress bar
            self.progress_fill = "\u2501"  # ━
            self.progress_empty = "\u254c"  # ╌
        else:
            # ASCII fallback
            self.thinking = "*"
            self.success = "+"
            self.error = "x"
            self.warning = "!"
            self.info = "i"

            self.tool = ">"
            self.arrow = ">"
            self.diamond_filled = "#"
            self.diamond_empty = "o"
            self.lightning = "!"

            self.bar = "|"
            self.line_heavy = "="
            self.line_light = "-"
            self.dot = "."
            self.bullet = "*"

            self.effort_low = "o"
            self.effort_mid = "O"
            self.effort_high = "@"

            self.progress_fill = "="
            self.progress_empty = "-"


# Module-level singletons
THEME = Theme()
SYMBOLS = Symbols()

# File extension -> syntax highlighting language
EXT_TO_LANG: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "jsx",
    ".tsx": "tsx",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".kt": "kotlin",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".rb": "ruby",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".md": "markdown",
    ".html": "html",
    ".css": "css",
    ".sql": "sql",
    ".xml": "xml",
    ".dockerfile": "dockerfile",
    ".makefile": "makefile",
    ".r": "r",
    ".php": "php",
    ".swift": "swift",
    ".lua": "lua",
}

# Known error patterns -> actionable suggestions
ERROR_SUGGESTIONS: dict[str, str] = {
    "Cannot connect to Ollama": "Run 'ollama serve' or check OLLAMA_HOST env var",
    "Model not found": "Run 'ollama pull <model>' to download it",
    "Permission denied": "Check file permissions or run with appropriate access",
    "File not found": "Verify the path. Use glob to search.",
    "File has not been read yet": "Use read_file first, then edit_file.",
    "old_string not found": "Re-read the file -- content may have changed since last read.",
    "Timed out": "Increase timeout or break the command into smaller steps.",
    "Invalid regex": "Check regex syntax. Escape special chars with \\\\.",
}
