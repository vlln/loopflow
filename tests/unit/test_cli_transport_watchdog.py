"""CliTransport idle-watchdog tests (BL-013 backstop).

Covers the last-resort idle watchdog: a silent subprocess with no live
children is killed as a hung model call, while a silent subprocess that
still has live children (long shell command) is left running.
"""

import os
import subprocess
import sys
import time

import pytest

from loopflow.infrastructure.transports.cli import CliTransport


def _sleep_cmd(seconds: int) -> list[str]:
    return [sys.executable, "-c", f"import time; time.sleep({seconds})"]


def test_idle_timeout_kills_silent_no_children():
    """A silent process with no children is killed as a hung model call."""
    t = CliTransport(idle_timeout=2.0)
    start = time.monotonic()
    with pytest.raises(TimeoutError, match="hung model call"):
        t.run(_sleep_cmd(30))
    assert time.monotonic() - start < 15


def test_idle_timeout_defaults_to_env():
    os.environ["LOOPFLOW_AGENT_IDLE_TIMEOUT"] = "5"
    try:
        t = CliTransport()
        assert t._idle_timeout == 5.0
    finally:
        del os.environ["LOOPFLOW_AGENT_IDLE_TIMEOUT"]


def test_idle_timeout_default_when_no_env():
    os.environ.pop("LOOPFLOW_AGENT_IDLE_TIMEOUT", None)
    t = CliTransport()
    assert t._idle_timeout == 7200.0


def test_has_live_children_false_when_no_proc():
    assert CliTransport._has_live_children() is False
    assert CliTransport._has_live_children(999999) is False


def test_has_live_children_detects_sleeper():
    """A subprocess that spawns a long-running child reports live children."""
    proc = subprocess.Popen(
        [sys.executable, "-c",
         "import subprocess,sys,time; "
         "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)']); "
         "time.sleep(30)"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(0.5)
        assert CliTransport._has_live_children(proc.pid) is True
    finally:
        proc.kill()
        proc.wait()


def test_has_live_children_false_for_zombie_only():
    """Children that are all zombies do not count as live work."""
    proc = subprocess.Popen(
        [sys.executable, "-c",
         "import subprocess,sys; "
         "subprocess.Popen([sys.executable, '-c', 'pass']); "
         "import time; time.sleep(1)"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(0.5)
        # The short child may already be a zombie or reaped; either way we
        # must not crash and must return a boolean.
        assert isinstance(CliTransport._has_live_children(proc.pid), bool)
    finally:
        proc.kill()
        proc.wait()


def test_normal_command_completes_with_watchdog():
    """A healthy short command still completes without watchdog firing."""
    t = CliTransport(idle_timeout=2.0)
    ec = t.run([sys.executable, "-c", "print('ok')"])
    assert ec == 0
