import os
import shlex
import signal
import subprocess  # nosec B404 - subprocess is required for shell tool functionality

from ..config import BASH_DEFAULT_TIMEOUT, BASH_MAX_TIMEOUT, INTERACTIVE_CMDS
from .base import BaseTool, ToolResult


class BashTool(BaseTool):
    name = "bash"

    def __init__(self, ctx):  # ctx: ToolContext
        self.ctx = ctx

    def validate(self, params: dict) -> str | None:
        if "command" not in params:
            return "Missing required: command"
        cmd = params["command"].strip()
        if not cmd:
            return "Command cannot be empty"
        first = cmd.split()[0].split("/")[-1]
        if first in INTERACTIVE_CMDS:
            return f"Interactive command '{first}' not supported"
        return None

    def execute(self, params: dict) -> ToolResult:
        command = params["command"]
        timeout = min(params.get("timeout", BASH_DEFAULT_TIMEOUT), BASH_MAX_TIMEOUT)
        try:
            proc = subprocess.Popen(  # noqa: S602  # nosec B602 - shell=True is intentional for a coding assistant shell tool
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True,
                cwd=self.ctx.cwd,
                preexec_fn=os.setsid,
            )
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            proc.wait()
            return ToolResult(False, f"Timed out after {timeout}s")
        except Exception as e:
            return ToolResult(False, f"Error: {e}")

        # CWD tracking: detect cd/pushd commands only (SAFE -- never re-executes command)
        if proc.returncode == 0:
            try:
                tokens = shlex.split(command)
            except ValueError:
                tokens = command.split()
            if tokens and tokens[0] in ("cd", "pushd"):
                target = tokens[1] if len(tokens) > 1 else os.path.expanduser("~")
                new = os.path.normpath(os.path.join(self.ctx.cwd, os.path.expanduser(target)))
                if os.path.isdir(new):
                    self.ctx.cwd = new

        parts = []
        if stdout.strip():
            parts.append(stdout.rstrip())
        if stderr.strip():
            parts.append(f"STDERR: {stderr.rstrip()}")
        if proc.returncode != 0:
            parts.append(f"(exit code: {proc.returncode})")
        return ToolResult(proc.returncode == 0, "\n".join(parts) or "(no output)")
