# shadow_code/main.py -- Full integrated REPL
#
# Orchestrates all modules:
#   - Rich UI (panels, markdown, spinners) via ui.py + streaming.py
#   - prompt_toolkit REPL (history, multiline, completion) via repl.py
#   - SQLite session persistence via db.py
#   - Destructive command warnings via safety.py
#   - 3-tier context management (result clearing, compaction, emergency truncate)
#   - Ollama streaming with tool_call buffer via display.py
#   - All 7 tools via tool registry
#
# Falls back to plain-text mode if rich/prompt_toolkit not installed.

import os
import platform
import signal
import sys
from datetime import datetime

from . import tools as tool_reg
from .config import CONTEXT_WINDOW, MAX_CONSECUTIVE_ERRORS, MAX_TOOL_TURNS, MODEL_NAME
from .conversation import Conversation
from .display import StreamDisplay
from .ollama_client import OllamaClient
from .parser import parse_tool_calls
from .prompt import SYSTEM_PROMPT
from .safety import check_destructive
from .skills import get_skill, list_skills
from .tool_context import ToolContext

# Optional imports -- graceful fallback
try:
    from rich.console import Console

    from .streaming import StreamCancelled, StreamController
    from .ui import HAS_RICH, UIRenderer

    _RICH = HAS_RICH
except ImportError:
    _RICH = False

try:
    from .repl import create_prompt_session, get_input

    _HAS_REPL = True
except ImportError:
    _HAS_REPL = False

try:
    from .db import Database

    _HAS_DB = True
except ImportError:
    _HAS_DB = False


def main():
    cwd = os.getcwd()
    ctx = ToolContext(cwd)

    # Register all tools
    from .tools.bash import BashTool

    tool_reg.register(BashTool(ctx))
    _register_optional_tools(ctx)

    # Ollama health check
    client = OllamaClient()
    ok, msg = client.health_check()
    if not ok:
        print(f"Error: {msg}", file=sys.stderr)
        sys.exit(1)

    # Setup UI
    if _RICH:
        console = Console()
        ui = UIRenderer()
        display = StreamDisplay()
        stream_ctrl = StreamController(client, ui, console, display)
        console.print(ui.render_welcome())
    else:
        console = None
        ui = None
        display = StreamDisplay()
        stream_ctrl = None
        print(f"shadow-code v0.1.0 | {MODEL_NAME}")
        print(f"CWD: {cwd}")

    # Setup REPL
    prompt_session = create_prompt_session() if _HAS_REPL else None

    # Setup DB
    db = None
    session_id = None
    if _HAS_DB:
        try:
            db = Database()
            session_id = db.create_session(MODEL_NAME)
        except Exception as e:
            print(f"[DB warning: {e}]")
            db = None

    print("Commands: /help /clear /exit /tokens /save /load /list /info\n")

    conv = Conversation()
    interrupted = False
    first_message = True

    def on_sigint(signum, frame):
        nonlocal interrupted
        interrupted = True

    signal.signal(signal.SIGINT, on_sigint)

    while True:
        # Get input
        if _HAS_REPL:
            user_input = get_input(prompt_session, MODEL_NAME)
            if user_input is None:
                break
        else:
            try:
                user_input = input("shadow> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

        if not user_input:
            continue

        # === Slash commands ===
        if user_input == "/exit":
            break

        if user_input == "/clear":
            conv.clear()
            first_message = True
            if _RICH:
                console.clear()
                console.print(ui.render_welcome())
            print("[Cleared]")
            continue

        if user_input == "/tokens":
            used = conv.total_prompt_tokens
            if _RICH:
                console.print(ui.render_context_status(used, CONTEXT_WINDOW))
            else:
                pct = (used / CONTEXT_WINDOW * 100) if CONTEXT_WINDOW else 0
                print(f"Context: {used} tokens ({pct:.0f}% of {CONTEXT_WINDOW})")
            continue

        if user_input == "/info":
            print(f"  Model:    {MODEL_NAME}")
            print(f"  CWD:      {ctx.cwd}")
            print(f"  Messages: {len(conv.get_messages())}")
            print(f"  Tokens:   {conv.total_prompt_tokens}")
            print(f"  Tools:    {', '.join(tool_reg._REGISTRY.keys())}")
            print(f"  Skills:   {len(list_skills())}")
            if session_id:
                print(f"  Session:  #{session_id}")
            continue

        if user_input.startswith("/cd"):
            target = user_input[3:].strip()
            if not target:
                print(f"  CWD: {ctx.cwd}")
            else:
                import os as _os

                new = _os.path.normpath(_os.path.join(ctx.cwd, _os.path.expanduser(target)))
                if _os.path.isdir(new):
                    ctx.cwd = new
                    print(f"  CWD: {ctx.cwd}")
                else:
                    print(f"  Not a directory: {new}")
            continue

        if user_input == "/version":
            from . import __version__

            print(f"  shadow-code v{__version__}")
            print(f"  Model: {MODEL_NAME}")
            print(f"  Context: {CONTEXT_WINDOW // 1024}K")
            continue

        if user_input == "/history":
            msgs = conv.get_messages()
            if not msgs:
                print("  No messages yet")
            else:
                for i, m in enumerate(msgs[-10:], max(1, len(msgs) - 9)):
                    role = m["role"]
                    preview = m["content"][:80].replace("\n", " ")
                    print(f"  {i:3}. [{role:9}] {preview}...")
            continue

        if user_input == "/compact":
            if conv.total_prompt_tokens > 0:
                print("[Compacting conversation...]")
                try:
                    from .compaction import compact

                    summary = compact(client, conv.get_messages(), SYSTEM_PROMPT)
                    conv.apply_compaction_summary(summary)
                    print("[Compaction complete]")
                except Exception as e:
                    print(f"[Compaction failed: {e}]")
            else:
                print("  Nothing to compact")
            continue

        if user_input == "/help":
            cmds = [
                ("/help", "Show this help"),
                ("/clear", "Clear conversation"),
                ("/exit", "Exit shadow-code"),
                ("/tokens", "Show context usage"),
                ("/info", "Show session info"),
                ("/cd [path]", "Show or change working directory"),
                ("/compact", "Manually compact conversation"),
                ("/history", "Show last 10 messages"),
                ("/version", "Show version info"),
                ("/save [name]", "Save session"),
                ("/load [id]", "Load session"),
                ("/list", "List saved sessions"),
                ("/skills", "List available skills"),
            ]
            # Add skills
            for skill_name, skill_desc in list_skills():
                cmds.append((f"/{skill_name}", skill_desc))
            # Keyboard shortcuts
            keys = [
                ("", ""),  # separator
                ("Ctrl+C", "Stop current generation"),
                ("Ctrl+D", "Exit"),
                ("Ctrl+X", "Exit"),
                ("Ctrl+L", "Clear screen"),
                ("Ctrl+U", "Clear input line"),
                ("Alt+Enter", "New line (multiline input)"),
                ("Up/Down", "Command history"),
                ("Ctrl+R", "Search history"),
            ]
            cmds.extend(keys)
            if _RICH:
                console.print(ui.render_help(cmds))
            else:
                for cmd, desc in cmds:
                    print(f"  {cmd:20} {desc}")
            continue

        if user_input == "/skills":
            print("  Available skills:")
            for skill_name, skill_desc in list_skills():
                print(f"    /{skill_name:15} {skill_desc}")
            continue

        if user_input.startswith("/save"):
            if db:
                name = user_input[5:].strip() or f"Session #{session_id}"
                db.rename_session(session_id, name)
                print(f"  Session saved as '{name}'")
            else:
                print("  [DB not available]")
            continue

        if user_input.startswith("/load"):
            if db:
                arg = user_input[5:].strip()
                if arg:
                    try:
                        sid = int(arg)
                        s = db.get_session(sid)
                        if s:
                            conv.clear()
                            first_message = True
                            for m in s["messages"]:
                                if m["role"] == "user":
                                    conv.add_user(m["content"])
                                    first_message = False
                                elif m["role"] == "assistant":
                                    conv.add_assistant(m["content"])
                            session_id = sid
                            print(f"  Loaded session #{sid} ({len(s['messages'])} messages)")
                        else:
                            print(f"  Session #{sid} not found")
                    except ValueError:
                        print("  Usage: /load <id>")
                else:
                    print("  Usage: /load <id>")
            else:
                print("  [DB not available]")
            continue

        if user_input == "/list":
            if db:
                sessions = db.list_sessions()
                if sessions:
                    for s in sessions:
                        name = s.get("name", "") or f"Session #{s['id']}"
                        msgs = s.get("message_count", 0)
                        print(f"  #{s['id']:4}  {name:30} ({msgs} msgs)")
                else:
                    print("  No saved sessions")
            else:
                print("  [DB not available]")
            continue

        # Check if it's a skill command (e.g., /commit, /simplify, /review file.py)
        if user_input.startswith("/"):
            parts = user_input[1:].split(None, 1)
            skill_name = parts[0] if parts else ""
            skill_args = parts[1] if len(parts) > 1 else ""
            skill = get_skill(skill_name)
            if skill:
                desc, prompt_template = skill
                skill_msg = prompt_template
                if skill_args:
                    skill_msg += f"\n\nUser specified: {skill_args}"
                user_input = skill_msg  # falls through to message handling below
                # DO NOT continue -- let it fall through to send the skill prompt to the model
            else:
                print(f"  Unknown command: /{skill_name}. Type /help")
                continue

        # === Inject environment on first message ===
        if first_message:
            shell = os.environ.get("SHELL", "/bin/bash").rsplit("/", 1)[-1]
            env_prefix = (
                f"[Environment: CWD={ctx.cwd}, "
                f"Platform={platform.system()} {platform.release()}, "
                f"Shell={shell}, Date={datetime.now().strftime('%Y-%m-%d')}]\n"
                "[Remember: write COMPLETE, PRODUCTION-READY code. "
                "Never use placeholders, never abbreviate, include all imports "
                "and error handling.]\n\n"
            )
            conv.add_user(env_prefix + user_input)
            first_message = False
        else:
            conv.add_user(user_input)

        # Save to DB
        if db:
            db.add_message(session_id, "user", user_input)

        # === Tool execution loop ===
        turns = 0
        errors = 0

        while turns < MAX_TOOL_TURNS:
            interrupted = False

            # Stream response
            if _RICH and stream_ctrl:
                try:
                    resp, eval_tokens = stream_ctrl.stream_response(
                        conv.get_messages(), SYSTEM_PROMPT
                    )
                except StreamCancelled:
                    print("[Interrupted]")
                    break
                except Exception as e:
                    if _RICH:
                        console.print(ui.render_error(str(e)))
                    else:
                        print(f"[Error: {e}]")
                    break
            else:
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
                print()
                resp = display.get_full_response()

                if interrupted:
                    print("[Interrupted]")
                    break

            if not resp or not resp.strip():
                break

            conv.add_assistant(resp)
            conv.update_tokens(client.last_prompt_tokens)

            # Save assistant response to DB
            if db:
                db.add_message(session_id, "assistant", resp)
                db.update_session_tokens(session_id, conv.total_prompt_tokens)

            # Parse tool calls
            _, calls = parse_tool_calls(resp)
            if not calls:
                break

            # Execute tools
            results = []
            for tc in calls:
                if tc.tool == "__invalid__":
                    r = tool_reg.ToolResult(False, tc.params.get("error", "Invalid"))
                    if _RICH:
                        console.print(ui.render_error(r.output))
                    else:
                        print(f"  [error] {r.output}")
                else:
                    # Build descriptive tool call summary
                    if tc.tool == "bash":
                        desc = tc.params.get("command", "")[:100]
                    elif tc.tool in ("read_file", "write_file", "edit_file"):
                        desc = tc.params.get("file_path", "")
                        if tc.tool == "edit_file":
                            old = tc.params.get("old_string", "")[:40]
                            new = tc.params.get("new_string", "")[:40]
                            desc += f'  "{old}" -> "{new}"'
                        elif tc.tool == "write_file":
                            desc += f"  ({len(tc.params.get('content', ''))} chars)"
                    elif tc.tool == "grep":
                        desc = f'"{tc.params.get("pattern", "")}" in {tc.params.get("path", ".")}'
                    elif tc.tool == "glob":
                        desc = f"{tc.params.get('pattern', '')} in {tc.params.get('path', '.')}"
                    else:
                        desc = str(tc.params)[:80]

                    # Safety check for bash commands
                    if tc.tool == "bash":
                        warning = check_destructive(tc.params.get("command", ""))
                        if warning:
                            if _RICH:
                                console.print(ui.render_error(warning))
                            else:
                                print(f"  {warning}")
                            try:
                                confirm = input("  Proceed? (y/n): ").strip().lower()
                            except (EOFError, KeyboardInterrupt):
                                confirm = "n"
                            if confirm != "y":
                                r = tool_reg.ToolResult(False, "Command cancelled by user")
                                results.append(tool_reg.format_result(tc.tool, r))
                                continue

                    if _RICH:
                        console.print(ui.render_tool_call(tc.tool, desc))

                    r = tool_reg.dispatch(tc.tool, tc.params)

                    if _RICH:
                        console.print(ui.render_tool_result(tc.tool, r.output, r.success))
                    else:
                        print(f"  [{tc.tool}] {desc}")
                        # Show enough output for model to see full context
                        max_lines = 80 if tc.tool in ("read_file", "bash", "grep") else 40
                        max_chars = (
                            8000 if tc.tool in ("read_file", "write_file", "edit_file") else 3000
                        )
                        preview = r.output[:max_chars]
                        if len(r.output) > max_chars:
                            preview += f"\n    ... [{len(r.output) - max_chars} more chars]"
                        lines = preview.split("\n")[:max_lines]
                        for line in lines:
                            print(f"    {line}")

                results.append(tool_reg.format_result(tc.tool, r))
                errors = errors + 1 if not r.success else 0

            conv.add_tool_results("\n\n".join(results))
            turns += 1

            if errors >= MAX_CONSECUTIVE_ERRORS:
                print(f"[{errors} consecutive errors]")
                break

        if turns >= MAX_TOOL_TURNS:
            print(f"[Tool limit ({MAX_TOOL_TURNS}) reached]")

        # === Context status (always visible) ===
        conv.update_tokens(client.last_prompt_tokens)
        if conv.total_prompt_tokens > 0:
            _show_context_status(
                conv.total_prompt_tokens,
                CONTEXT_WINDOW,
                client.last_eval_tokens,
                console if _RICH else None,
                ui if _RICH else None,
            )

        # === 3-Tier Context Management ===
        if conv.needs_result_clearing():
            conv.clear_old_tool_results()

        if conv.needs_compaction():
            print("[Compacting conversation...]")
            try:
                from .compaction import compact

                summary = compact(client, conv.get_messages(), SYSTEM_PROMPT)
                conv.apply_compaction_summary(summary)
                print("[Compaction complete]")
            except Exception as e:
                print(f"[Compaction failed: {e}]")

            if conv.needs_emergency_truncate():
                conv.emergency_truncate()
                print("[Emergency truncation applied]")

    # Cleanup
    if db:
        db.close()
    print("Goodbye!")


def _register_optional_tools(ctx):
    """Register Phase 2 tools if available."""
    optional = [
        ("shadow_code.tools.read_file", "ReadFileTool"),
        ("shadow_code.tools.edit_file", "EditFileTool"),
        ("shadow_code.tools.write_file", "WriteFileTool"),
        ("shadow_code.tools.glob_tool", "GlobTool"),
        ("shadow_code.tools.grep_tool", "GrepTool"),
        ("shadow_code.tools.list_dir", "ListDirTool"),
    ]
    for mod_path, cls_name in optional:
        try:
            import importlib

            mod = importlib.import_module(mod_path)
            tool_reg.register(getattr(mod, cls_name)(ctx))
        except (ImportError, AttributeError):
            pass


def _show_context_status(used: int, total: int, last_eval: int, console=None, ui=None):
    """Show context usage after every turn. Works in both Rich and plain mode."""
    pct = (used / total * 100) if total else 0
    bar_width = 20
    filled = int(bar_width * pct / 100)
    bar = "=" * filled + "-" * (bar_width - filled)

    if console and ui:
        console.print(ui.render_context_status(used, total))
    else:
        # Soft ANSI colors (Claude Code inspired)
        if pct < 50:
            color = "\033[38;5;71m"  # soft green
        elif pct < 75:
            color = "\033[38;5;179m"  # soft amber
        else:
            color = "\033[38;5;167m"  # soft red
        dim = "\033[2m"
        reset = "\033[0m"
        print(f"  {color}[{bar}] {used // 1000}K/{total // 1000}K{reset} {dim}({pct:.0f}%){reset}")


if __name__ == "__main__":
    main()
