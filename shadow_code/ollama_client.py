# shadow_code/ollama_client.py -- Streaming Ollama API client with token tracking
#
# Provides health_check() and chat_stream() for the main REPL loop.
# Tracks prompt_eval_count and eval_count from the final streaming message
# so conversation.py can manage context window usage.

import json
import requests

from .config import OLLAMA_BASE_URL, MODEL_NAME, MODEL_OPTIONS


class OllamaClient:
    """Client for the Ollama /api/chat streaming endpoint."""

    def __init__(self):
        self.last_prompt_tokens: int = 0
        self.last_eval_tokens: int = 0

    def health_check(self) -> tuple[bool, str]:
        """Verify Ollama is running and the configured model is available.

        Returns (ok, message) tuple.
        """
        try:
            resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
            resp.raise_for_status()
            models = [m["name"] for m in resp.json().get("models", [])]
            if MODEL_NAME not in models:
                # Also check without tag -- "shadow-gemma:latest" may appear as "shadow-gemma"
                base_name = MODEL_NAME.split(":")[0]
                found = [m for m in models if m.startswith(base_name)]
                if not found:
                    return False, f"Model '{MODEL_NAME}' not found. Available: {models}"
            return True, "OK"
        except requests.ConnectionError:
            return False, f"Cannot connect to Ollama at {OLLAMA_BASE_URL}"
        except requests.RequestException as e:
            return False, f"Ollama error: {e}"

    def chat_stream(self, messages: list[dict], system: str):
        """Stream a chat completion from Ollama.

        Args:
            messages: Conversation history (list of {"role": ..., "content": ...}).
            system: The system prompt (static string for KV cache).

        Yields:
            str: Content chunks as they arrive.

        After iteration completes, last_prompt_tokens and last_eval_tokens
        are updated from the final response's statistics.
        """
        payload = {
            "model": MODEL_NAME,
            "messages": [{"role": "system", "content": system}] + messages,
            "stream": True,
            "options": MODEL_OPTIONS,
        }
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload,
            stream=True,
            timeout=600,
        )
        resp.raise_for_status()

        for line in resp.iter_lines():
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            content = data.get("message", {}).get("content", "")
            if content:
                yield content

            if data.get("done"):
                self.last_prompt_tokens = data.get("prompt_eval_count", 0)
                self.last_eval_tokens = data.get("eval_count", 0)
