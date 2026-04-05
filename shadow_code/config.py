import os

OLLAMA_BASE_URL = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
MODEL_NAME = os.environ.get("SHADOW_MODEL", "shadow-gemma:latest")
CONTEXT_WINDOW = 131_072
MAX_TOOL_TURNS = 20
MAX_CONSECUTIVE_ERRORS = 3
TOOL_OUTPUT_MAX_CHARS = 30_000
BASH_DEFAULT_TIMEOUT = 120
BASH_MAX_TIMEOUT = 600
MAX_LINES_TO_READ = 2000
INTERACTIVE_CMDS = {"vim", "vi", "nano", "less", "more", "top", "htop", "man"}
BLOCKED_PATHS = {"/dev/zero", "/dev/urandom", "/dev/random", "/dev/stdin", "/dev/stdout", "/dev/stderr"}
MODEL_OPTIONS = {"temperature": 0.3, "num_cty": CONTEXT_WINDOW}
