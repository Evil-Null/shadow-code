"""Auto-detect project language, framework, structure in one tool call.

Replaces 5-10 manual exploration turns with a single call that scans
well-known config files and produces a structured summary.
"""

import json
import os

from .base import BaseTool, ToolResult

# Config files that indicate language/framework
_INDICATORS = {
    "pyproject.toml": ("Python", None),
    "setup.py": ("Python", None),
    "requirements.txt": ("Python", None),
    "package.json": ("JavaScript/TypeScript", None),
    "tsconfig.json": ("TypeScript", None),
    "go.mod": ("Go", None),
    "Cargo.toml": ("Rust", None),
    "pom.xml": ("Java", "Maven"),
    "build.gradle": ("Java/Kotlin", "Gradle"),
    "Gemfile": ("Ruby", "Rails"),
    "composer.json": ("PHP", None),
    "mix.exs": ("Elixir", None),
    "pubspec.yaml": ("Dart", "Flutter"),
    "Makefile": (None, "Make"),
    "Dockerfile": (None, "Docker"),
    "docker-compose.yml": (None, "Docker Compose"),
    "docker-compose.yaml": (None, "Docker Compose"),
}

# Framework-specific config files
_FRAMEWORK_INDICATORS = {
    "next.config.js": "Next.js",
    "next.config.ts": "Next.js",
    "nuxt.config.ts": "Nuxt",
    "angular.json": "Angular",
    "vite.config.ts": "Vite",
    "vite.config.js": "Vite",
    "django": "Django",
    "flask": "Flask",
    "fastapi": "FastAPI",
}

_PRUNE_DIRS = {".git", "node_modules", "__pycache__", ".venv", "dist", "build", ".mypy_cache"}


class ProjectSummaryTool(BaseTool):
    name = "project_summary"

    def __init__(self, ctx):
        self.ctx = ctx

    def validate(self, params: dict) -> str | None:
        return None

    def execute(self, params: dict) -> ToolResult:
        root = params.get("path", self.ctx.cwd)
        if not os.path.isabs(root):
            root = os.path.join(self.ctx.cwd, root)

        if not os.path.isdir(root):
            return ToolResult(False, f"Not a directory: {root}")

        sections = []

        # Detect language and framework
        languages = set()
        frameworks = set()
        config_files = []

        for name, (lang, fw) in _INDICATORS.items():
            path = os.path.join(root, name)
            if os.path.exists(path):
                config_files.append(name)
                if lang:
                    languages.add(lang)
                if fw:
                    frameworks.add(fw)

        for name, fw in _FRAMEWORK_INDICATORS.items():
            if os.path.exists(os.path.join(root, name)):
                frameworks.add(fw)

        if languages:
            sections.append(f"Language: {', '.join(sorted(languages))}")
        if frameworks:
            sections.append(f"Framework: {', '.join(sorted(frameworks))}")
        if config_files:
            sections.append(f"Config files: {', '.join(sorted(config_files))}")

        # Extract dependencies from pyproject.toml or package.json
        deps = self._extract_deps(root)
        if deps:
            sections.append(f"Dependencies: {deps}")

        # Directory tree (2 levels)
        tree = self._dir_tree(root, max_depth=2)
        if tree:
            sections.append(f"Structure:\n{tree}")

        # Entry points
        entries = self._find_entries(root)
        if entries:
            sections.append(f"Entry points: {', '.join(entries)}")

        # Test config
        test_info = self._find_tests(root)
        if test_info:
            sections.append(f"Testing: {test_info}")

        # Git info
        git_info = self._git_info(root)
        if git_info:
            sections.append(f"Git: {git_info}")

        if not sections:
            return ToolResult(True, f"No project structure detected in {root}")

        output = f"Project: {os.path.basename(root)}\n" + "\n".join(sections)
        return ToolResult(True, output)

    def _extract_deps(self, root: str) -> str:
        # Try pyproject.toml
        pyproject = os.path.join(root, "pyproject.toml")
        if os.path.exists(pyproject):
            try:
                with open(pyproject) as f:
                    content = f.read()
                # Simple extraction -- find dependencies line
                for line in content.split("\n"):
                    if line.strip().startswith("dependencies"):
                        return line.strip()[:200]
            except OSError:
                pass

        # Try package.json
        pkgjson = os.path.join(root, "package.json")
        if os.path.exists(pkgjson):
            try:
                with open(pkgjson) as f:
                    data = json.load(f)
                deps = list(data.get("dependencies", {}).keys())[:10]
                if deps:
                    return ", ".join(deps)
            except (OSError, json.JSONDecodeError):
                pass

        return ""

    def _dir_tree(self, root: str, max_depth: int) -> str:
        lines = []

        def _walk(path: str, prefix: str, depth: int):
            if depth > max_depth:
                return
            try:
                entries = sorted(os.listdir(path))
            except PermissionError:
                return
            dirs = [
                e
                for e in entries
                if os.path.isdir(os.path.join(path, e))
                and e not in _PRUNE_DIRS
                and not e.startswith(".")
            ]
            files = [
                e
                for e in entries
                if os.path.isfile(os.path.join(path, e)) and not e.startswith(".")
            ]

            for d in dirs:
                lines.append(f"{prefix}{d}/")
                _walk(os.path.join(path, d), prefix + "  ", depth + 1)
            # Only show files at depth 0-1
            if depth <= 1:
                for f_name in files[:10]:
                    lines.append(f"{prefix}{f_name}")
                if len(files) > 10:
                    lines.append(f"{prefix}... ({len(files) - 10} more files)")

        _walk(root, "  ", 0)
        return "\n".join(lines[:50])

    def _find_entries(self, root: str) -> list[str]:
        candidates = [
            "main.py",
            "app.py",
            "index.ts",
            "index.js",
            "main.go",
            "main.rs",
            "server.py",
        ]
        found = []
        for c in candidates:
            if os.path.exists(os.path.join(root, c)):
                found.append(c)
            # Check in src/
            src = os.path.join(root, "src", c)
            if os.path.exists(src):
                found.append(f"src/{c}")
        return found

    def _find_tests(self, root: str) -> str:
        for d in ["tests", "test", "__tests__", "spec"]:
            if os.path.isdir(os.path.join(root, d)):
                count = sum(
                    1
                    for f in os.listdir(os.path.join(root, d))
                    if f.startswith("test")
                    or f.endswith((".test.ts", ".spec.ts", "_test.go", "_test.py"))
                )
                return f"{d}/ directory ({count} test files)"
        return ""

    def _git_info(self, root: str) -> str:
        git_dir = os.path.join(root, ".git")
        if not os.path.isdir(git_dir):
            return ""
        # Read current branch
        head = os.path.join(git_dir, "HEAD")
        try:
            with open(head) as f:
                ref = f.read().strip()
            if ref.startswith("ref: refs/heads/"):
                branch = ref.replace("ref: refs/heads/", "")
                return f"branch={branch}"
        except OSError:
            pass
        return "git repo"
