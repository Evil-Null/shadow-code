# shadow_code/main.py -- REPL, signal handling, startup health check
#
# Entry point for shadow-code. Orchestrates:
#   - Ollama health check on startup
#   - User input loop with slash commands (/help /clear /exit /tokens)
#   - Streaming LLM responses via OllamaClient
#   - Tool call detection and execution via parser + tool registry
#   - Environment prefix injection on first message (keeps system prompt static)
#   - 3-tier context management at end of each turn
#   - Ctrl+C signal handling for graceful interruption

import os
import platform
import signal
import sys
from datetime import datetime

from .config import CONTEXT_WINDOW, MAX_CONSECUTIVE_ERRORS, MAX_TOOL_TURNS, MODEL_NAME
from .conversation import Conversation
from .display import StreamDisplay
from .ollama_client import OllamaClient
from .parser import parse_tool_calls
from .prompt import SYSTEM_PROMPT  # static constant, NOT a function
from .tool_context import ToolContext
from . import tools as tool_reg


def main():
    cwd = os.getcwd()
    ctx = ToolContext(cwd)  # shared state for all tools

    # Register tools (Phase 1: only bash; Phase 2 adds the rest)
    from .tools.bash import BashTool
    tool_reg.register(BashTool(ctx))

    # Optional: register Phase 2 tools if available
    _register_optional_tools(ctx)

    client = OllamaClient()
    ok, msg = client.health_check()
    if not ok:
        print(f"Error: {msg}", file=sys.stderr)
        sys.exit(1)

    print(f"shadow-code v0.1.0 | {MODEL_NAME}")
    print(f"CWD: {cwd}")
    print("Commands: /help /clear /exit /tokens\n")

    conv = Conversation()
    display = StreamDisplay()
    interrupted = False
    first_message = True  # track first message for env prefix

    def on_sigint(signum, frame):
        nonlocal interrupted
        interrupted = True

    signal.signal(signal.SIGINT, on_sigint)

    while True:
        try:
            user_input = input("shadow> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue

        # Slash commands
        if user_input == "/exit":
            break
        if user_input == "/clear":
            conv.clear()
            first_message = True
            print("[Cleared]")
            continue
        if user_input == "/tokens":
            pct = (conv.total_prompt_tokens / CONTEXT_WINDOW * 100) if CONTEXT_WINDOW else 0
            print(f"Prompt: {conv.total_prompt_tokens} tokens "
                  f"({pct:.0f}% of {CONTEXT_WINDOW})")
            continue
        if user_input == "/help":
            print("Commands:")
            print("  /clear   -- Clear conversation history")
            print("  /exit    -- Exit shadow-code")
            print("  /tokens  -- Show token usage")
            print("  /help    -- Show this help")
            continue

        # Inject environment info on first message (keeps system prompt static for KV cache)
        if first_message:
            shell = os.environ.get("SHELL", "/bin/bash").rsplit("/", 1)[-1]
            env_prefix = (
                f"[Environment: CWD={ctx.cwd}, "
                f"Platform={platform.system()} {platform.release()}, "
                f"Shell={shell}, Date={datetime.now().strftime('%Y-%m-%d')}]\n\n"
            )
            conv.add_user(env_prefix + user_input)
            first_message = False
        else:
            conv.add_user(user_input)

        turns = 0
        errors = 0

        # Inner loop: LLM response -> parse tool calls -> execute -> feed results back
        while turns < MAX_TOOL_TURNS:
            interrupted = False
            display.reset()

            try:
                for chunk in client.chat_stream(conv.get_messages(), SYSTEM_PROMPT):
                    if interrupted:
                        break
                    display.feed(chunk)
            except KeyboardInterrupt:
                interrupted = True
            except Exception as e:
                print(f"\n[Error: {e}]")
                break

            display.flush()
            print()  # newline after streaming output

            resp = display.get_full_response()
            if not resp.strip():
                break

            conv.add_assistant(resp)
            conv.update_tokens(client.last_prompt_tokens)

            if interrupted:
                print("[Interrupted]")
                break

            # Parse tool calls from the response
            _, calls = parse_tool_calls(resp)
            if not calls:
                break  # No tool calls -- turn is done

            # Execute each tool call
            results = []
            for tc in calls:
                if tc.tool == "__invalid__":
                    r = tool_reg.ToolResult(False, tc.params.get("error", "Invalid tool call"))
                    print(f"  [error] {r.output}")
                else:
                    # Show brief tool invocation info
                    desc = tc.params.get("command",
                           tc.params.get("file_path",
                           str(tc.params)))[:80]
                    print(f"  [{tc.tool}] {desc}")
                    r = tool_reg.dispatch(tc.tool, tc.params)
                    # Show brief preview of result
                    preview = r.output[:200] + ("..." if len(r.output) > 200 else "")
                    for line in preview.split("\n")[:5]:
                        print(f"    {line}")

                results.append(tool_reg.format_result(tc.tool, r))
                errors = errors + 1 if not r.success else 0

            conv.add_tool_results("\n\n".join(results))
            turns += 1

            if errors >= MAX_CONSECUTIVE_ERRORS:
                print(f"[{errors} consecutive errors -- stopping tool loop]")
                break

        if turns >= MAX_TOOL_TURNS:
            print(f"[Tool limit ({MAX_TOOL_TURNS}) reached]")

        # === 3-Tier Context Management (Claude Code style) ===
        conv.update_tokens(client.last_prompt_tokens)

        # Tier 1: Clear old tool results (fast, no API call)
        if conv.needs_result_clearing():
            conv.clear_old_tool_results()

        # Tier 2: Auto-compaction (LLM summarization)
        if conv.needs_compaction():
            print("[Compacting conversation...]")
            try:
                from .compaction import compact
                summary = compact(client, conv.get_messages(), SYSTEM_PROMPT)
                conv.apply_compaction_summary(summary)
                print("[Compaction complete]")
            except ImportError:
                # compaction.py not yet implemented -- fall through to Tier 3
                pass
            except Exception as e:
                print(f"[Compaction failed: {e}]")

            # Tier 3: Emergency truncate (fallback if compaction failed or unavailable)
            if conv.needs_emergency_truncate():
                conv.emergency_truncate()
                print("[Emergency truncation applied]")


def _register_optional_tools(ctx):
    """Register Phase 2 tools if they're available. Silently skip if not."""
    optional_tools = [
        ("shadow_code.tools.read_file", "ReadFileTool"),
        ("shadow_code.tools.edit_file", "EditFileTool"),
        ("shadow_code.tools.write_file", "WriteFileTool"),
        ("shadow_code.tools.glob_tool", "GlobTool"),
        ("shadow_code.tools.grep_tool", "GrepTool"),
        ("shadow_code.tools.list_dir", "ListDirTool"),
    ]
    for module_path, class_name in optional_tools:
        try:
            import importlib
            mod = importlib.import_module(module_path)
            tool_class = getattr(mod, class_name)
            tool_reg.register(tool_class(ctx))
        except (ImportError, AttributeError):
            pass  # Tool not yet implemented -- skip silently


if __name__ == "__main__":
    main()
