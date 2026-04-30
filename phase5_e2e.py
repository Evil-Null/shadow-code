"""Phase 5 e2e validation: 5 realistic dev tasks against shadow-qwen.

Verifies that the model produces sensible FIRST tool calls for representative
agentic tasks. Does NOT run a full multi-turn agent loop (out of scope for
validation harness — the goal is to confirm intent + tool-format reliability
on real prompts, not to test shadow-code's loop which already works).
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import requests

from shadow_code.parser import parse_tool_calls
from shadow_code.prompt import SYSTEM_PROMPT

MODEL = "shadow-qwen:latest"
OLLAMA_URL = "http://localhost:11434/api/chat"

# Each case: (description, user_prompt, expected_first_tool_set, expected_param_substr)
CASES = [
    (
        "Read a real config file",
        "Read shadow_code/config.py and tell me the model name.",
        {"read_file"},
        "config.py",
    ),
    (
        "Find a symbol",
        "Search this repo for the parse_tool_calls function definition.",
        {"grep", "grep_tool"},
        "parse_tool_calls",
    ),
    (
        "List a directory",
        "Show me what files are in the shadow_code/tools directory.",
        {"list_dir", "glob", "glob_tool"},
        "shadow_code/tools",
    ),
    (
        "Use a skill — language rules",
        "I'm about to write a Python module. Get the language rules first.",
        {"get_language_rules"},
        "py",
    ),
    (
        "Bash command",
        "Run `git status` and tell me what's changed.",
        {"bash"},
        "git status",
    ),
]


def run_case(prompt: str) -> tuple[str, float]:
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "options": {"temperature": 0.2, "num_ctx": 32768, "num_predict": 1024},
    }
    t0 = time.time()
    r = requests.post(OLLAMA_URL, json=body, timeout=300)
    r.raise_for_status()
    elapsed = time.time() - t0
    return r.json()["message"]["content"], elapsed


def main():
    results = []
    for idx, (desc, prompt, expected_tools, expected_substr) in enumerate(CASES, 1):
        print(f"[{idx}] {desc}")
        try:
            resp, lat = run_case(prompt)
        except Exception as e:
            results.append(
                {"idx": idx, "desc": desc, "ok": False, "reason": f"request failed: {e}", "lat": 0}
            )
            print(f"  FAIL — request: {e}")
            continue

        calls = parse_tool_calls(resp)
        # parse_tool_calls returns (clean_text, list[ToolCall])
        if isinstance(calls, tuple):
            _, calls = calls
        if not calls:
            results.append(
                {"idx": idx, "desc": desc, "ok": False, "reason": "no tool call",
                 "resp": resp[:300], "lat": lat}
            )
            print(f"  FAIL — no tool call ({lat:.1f}s)")
            continue

        first = calls[0]
        tool_name = first.tool
        params_str = json.dumps(first.params)

        tool_ok = tool_name in expected_tools
        substr_ok = expected_substr.lower() in params_str.lower()

        if tool_ok and substr_ok:
            results.append(
                {"idx": idx, "desc": desc, "ok": True, "tool": tool_name,
                 "params": first.params, "lat": lat}
            )
            print(f"  PASS — {tool_name} ({lat:.1f}s)")
        else:
            reason = []
            if not tool_ok:
                reason.append(f"got tool={tool_name!r}, want one of {expected_tools}")
            if not substr_ok:
                reason.append(f"params {params_str!r} missing {expected_substr!r}")
            results.append(
                {"idx": idx, "desc": desc, "ok": False, "reason": "; ".join(reason),
                 "tool": tool_name, "params": first.params, "lat": lat}
            )
            print(f"  FAIL — {'; '.join(reason)} ({lat:.1f}s)")

    Path("phase5_e2e_report.json").write_text(json.dumps(results, indent=2, ensure_ascii=False))
    ok = sum(1 for r in results if r["ok"])
    avg = sum(r["lat"] for r in results) / len(results)
    print(f"\n=== {ok}/{len(results)} passed ({ok/len(results)*100:.0f}%), avg {avg:.1f}s ===")


if __name__ == "__main__":
    main()
