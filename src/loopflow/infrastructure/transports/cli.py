"""Generic CLI transport — spawn a subprocess, stream stdout, capture exit code."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from typing import Callable


class CliTransport:
    """Generic subprocess-based communication with a CLI tool.

    Spawns a command, streams stdout/stderr line-by-line through
    optional callbacks, and returns the exit code.
    """

    def __init__(self, backend_name: str | None = None,
                 idle_timeout: float | None = None) -> None:
        self._proc: subprocess.Popen | None = None
        self._backend_name = backend_name
        self._timeout: float | None = None
        self._stderr_lines: list[str] = []
        # Idle watchdog (last-resort backstop): a subprocess that produces no
        # output for this long is treated as a hung model call (ghost process)
        # and killed. Resets on any stdout/stderr line. Default 2h — long
        # builds/downloads stay silent for 30-60min, while observed API hangs
        # were 6.5-10.5h. Configurable via LOOPFLOW_AGENT_IDLE_TIMEOUT
        # (seconds). This is a backstop only: Claude Code >= 2.1.196 ships its
        # own streaming idle watchdog (CLAUDE_STREAM_IDLE_TIMEOUT_MS, default
        # 90s, on by default for all providers), which handles mid-stream API
        # stalls first; this layer only guards the pathological cases where the
        # CLI process itself goes silent with no live child doing real work.
        self._idle_timeout = (
            idle_timeout if idle_timeout is not None
            else float(os.environ.get("LOOPFLOW_AGENT_IDLE_TIMEOUT", "7200")))
        self._last_activity = time.monotonic()

    @property
    def stderr_text(self) -> str:
        """Stderr output from the most recent run, for error diagnostics."""
        return "\n".join(self._stderr_lines)

    def run(
        self,
        args: list[str],
        *,
        on_stdout: Callable[[str], None] | None = None,
        on_stderr: Callable[[str], None] | None = None,
        timeout: float | None = None,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
    ) -> int:
        """Run a command and return its exit code.

        Args:
            args: Command and arguments to execute.
            on_stdout: Called for each stdout line (newline stripped).
            on_stderr: Called for each stderr line (newline stripped).
            timeout: Maximum time in seconds. Default 300s (5 min).
            env: Additional environment variables to merge into the
                subprocess environment.
            cwd: Working directory for the subprocess.

        Returns:
            The process exit code.
        """
        try:
            import os
            proc_env = os.environ.copy()
            if env:
                proc_env.update(env)
            self._proc = subprocess.Popen(
                args,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=proc_env,
                cwd=cwd,
            )
        except FileNotFoundError:
            install_guide = ""
            if self._backend_name:
                from loopflow.infrastructure.backends.diagnostics import format_install_guide
                install_guide = "\n" + format_install_guide(self._backend_name)
            raise RuntimeError(
                f"Command not found: {args[0]}\n"
                f"Please install '{args[0]}' or use a different backend with --backend <name>."
                f"{install_guide}"
            ) from None

        assert self._proc.stdout is not None
        assert self._proc.stderr is not None

        errors: list[Exception] = []
        self._stderr_lines.clear()

        def _read(stream, callback, write_fn, flush_fn):
            try:
                for line in iter(stream.readline, ""):
                    self._last_activity = time.monotonic()
                    line = line.rstrip("\n")
                    if callback:
                        callback(line)
                    else:
                        write_fn(line + "\n")
                        flush_fn()
            except Exception as e:
                errors.append(e)

        def _read_stderr(line: str) -> None:
            self._stderr_lines.append(line)
            if on_stderr:
                on_stderr(line)
            else:
                sys.stderr.write(line + "\n")
                sys.stderr.flush()

        t_stdout = threading.Thread(
            target=_read,
            args=(self._proc.stdout, on_stdout, sys.stdout.write, sys.stdout.flush),
            daemon=True,
        )
        t_stderr = threading.Thread(
            target=_read,
            args=(self._proc.stderr, _read_stderr, sys.stderr.write, sys.stderr.flush),
            daemon=True,
        )
        t_stdout.start()
        t_stderr.start()

        effective_timeout = timeout if timeout is not None else self._timeout
        self._last_activity = time.monotonic()
        wall_start = time.monotonic()
        while True:
            t_stdout.join(timeout=10)
            if not t_stdout.is_alive():
                break
            elapsed = time.monotonic() - wall_start
            idle = time.monotonic() - self._last_activity
            if effective_timeout is not None and elapsed > effective_timeout:
                self._proc.kill()
                self._proc.wait()
                raise TimeoutError(
                    f"Command timed out: {args[0]}\n"
                    f"Exceeded hard wall-clock timeout {effective_timeout:.0f}s."
                )
            if idle > self._idle_timeout:
                # A silent CLI that still has live children is almost always
                # waiting on a long command (e.g. a shell running mip or
                # docker pull that emits nothing for 30-60min) — keep waiting.
                # Only a silent CLI with no children is a hung model call.
                if self._has_live_children():
                    continue
                self._proc.kill()
                self._proc.wait()
                raise TimeoutError(
                    f"Command timed out: {args[0]}\n"
                    f"No output for {idle:.0f}s and no live child processes — "
                    f"killed as a possible hung model call (idle timeout "
                    f"{self._idle_timeout:.0f}s). Check the API connection.\n"
                    f"Tip: LOOPFLOW_AGENT_IDLE_TIMEOUT controls the idle threshold."
                )
        t_stderr.join(timeout=30)
        exit_code = self._proc.wait()

        if errors:
            raise errors[0]

        return exit_code

    @staticmethod
    def _has_live_children(pid: int | None = None) -> bool:
        """True if the tracked process has any live child processes.

        Used to distinguish "silently waiting on a long shell command"
        (children alive) from "hung model call" (no children). Falls back to
        False on any platform issue so the watchdog still fires.
        """
        if pid is None:
            return False
        try:
            # pgrep -P works on both Linux (procps) and macOS (10.8+).
            out = subprocess.run(
                ["pgrep", "-P", str(pid)],
                capture_output=True, text=True, timeout=3,
            )
            children = [p for p in out.stdout.split() if p.strip()]
            if not children:
                return False
            # Ignore zombies: they are dead but not yet reaped.
            alive = subprocess.run(
                ["ps", "-o", "pid=", "-o", "stat=", "-p", ",".join(children)],
                capture_output=True, text=True, timeout=3,
            )
            for line in alive.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 2 and "Z" not in parts[1]:
                    return True
            return False
        except (OSError, subprocess.TimeoutExpired):
            return False

    def close(self) -> None:
        """Terminate the process if still running."""
        if self._proc is not None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    self._proc.kill()
                except OSError:
                    pass
            self._proc = None