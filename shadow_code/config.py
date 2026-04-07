import os

OLLAMA_BASE_URL = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
MODEL_NAME = os.environ.get("SHADOW_MODEL", "shadow-gemma:latest")
CONTEXT_WINDOW = 131_072
MAX_TOOL_TURNS = 20
MAX_CONSECUTIVE_ERRORS = 5
TOOL_OUTPUT_MAX_CHARS = 30_000
BASH_DEFAULT_TIMEOUT = 120
BASH_MAX_TIMEOUT = 600
MAX_LINES_TO_READ = 2000
INTERACTIVE_CMDS = {"vim", "vi", "nano", "less", "more", "top", "htop", "man"}
BLOCKED_PATHS = {
    "/dev/zero",
    "/dev/urandom",
    "/dev/random",
    "/dev/stdin",
    "/dev/stdout",
    "/dev/stderr",
}
# num_predict: max output tokens per response. Default ~2048 is too low for code generation.
# Set high so the model can write complete files without truncation.
MAX_OUTPUT_TOKENS = int(os.environ.get("SHADOW_MAX_TOKENS", "8192"))

MODEL_OPTIONS = {
    "temperature": 0.3,
    "num_ctx": CONTEXT_WINDOW,
    "num_predict": MAX_OUTPUT_TOKENS,
    "top_k": 40,
    "top_p": 0.9,
    "repeat_penalty": 1.1,
}

# --- Model Routing ---
# Override via SHADOW_MODEL env var or use these as guidance for model selection.
# The compaction model can be smaller/faster since it only summarizes conversation.
COMPACTION_MODEL = os.environ.get("SHADOW_COMPACTION_MODEL", MODEL_NAME)

# Recommended Ollama models by task complexity:
#
#   Task Type              Recommended Model         Why
#   --------------------   -----------------------   ----------------------------
#   Simple file ops        gemma3:4b, qwen3:4b       Fast, low memory, sufficient
#     (read, ls, grep)                                for tool dispatch
#
#   Standard coding        gemma3:27b, qwen3:14b     Good balance of speed and
#     (edit, debug, test)                             reasoning for most tasks
#
#   Complex reasoning      gemma3:27b, qwen3:32b     Multi-file refactoring,
#     (architecture,       deepseek-r1:32b            architectural decisions,
#      multi-step plans)                              long context synthesis
#
#   Compaction/summary     gemma3:4b, qwen3:4b       Only needs to summarize,
#                                                     not reason deeply
#
# Usage:
#   SHADOW_MODEL=gemma3:4b shadow-code           # lightweight mode
#   SHADOW_MODEL=deepseek-r1:32b shadow-code     # deep reasoning mode
#   SHADOW_COMPACTION_MODEL=gemma3:4b shadow-code # fast compaction
