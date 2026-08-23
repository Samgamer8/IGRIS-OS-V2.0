import os
import sys

import pytest

from igris_os.security.sandbox import JobObjectSandbox


def test_sandbox_captures_stdout():
    run = JobObjectSandbox().run([sys.executable, "-c", "print('hola')"])
    assert run.returncode == 0
    assert run.stdout.strip() == "hola"


def test_sandbox_times_out():
    run = JobObjectSandbox().run(
        [sys.executable, "-c", "import time; time.sleep(5)"], timeout=1)
    assert run.timed_out


@pytest.mark.skipif(os.name != "nt", reason="Job Objects solo en Windows")
def test_sandbox_limits_memory():
    sandbox = JobObjectSandbox(memory_limit_mb=256)
    code = ("data=[]\n"
            "try:\n"
            "    while True: data.append(bytearray(1024*1024))\n"
            "except MemoryError:\n"
            "    print('CAP')\n")
    run = sandbox.run([sys.executable, "-c", code], timeout=30)
    assert "CAP" in run.stdout


def test_sandbox_returns_nonzero_exit():
    run = JobObjectSandbox().run(
        [sys.executable, "-c", "import sys; sys.exit(3)"])
    assert run.returncode == 3
    assert not run.timed_out


@pytest.mark.skipif(os.name != "nt", reason="Job Objects solo en Windows")
def test_sandbox_reports_was_sandboxed():
    run = JobObjectSandbox().run([sys.executable, "-c", "print('x')"])
    assert run.sandboxed


@pytest.mark.skipif(os.name != "nt", reason="Job Objects solo en Windows")
def test_sandbox_no_carrera_fast_command_still_sandboxed():
    run = JobObjectSandbox().run([sys.executable, "-c", "pass"])
    assert run.returncode == 0
    assert run.sandboxed


def test_sandbox_fallback_timeout(monkeypatch):
    sandbox = JobObjectSandbox()
    sandbox._windows = False
    run = sandbox.run([sys.executable, "-c", "import time; time.sleep(30)"],
                      timeout=1)
    assert run.timed_out
    assert run.returncode != 0

