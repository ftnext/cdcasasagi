from __future__ import annotations

import shlex
import subprocess
import sys

from getgauge.python import data_store, step


@step("Run cdcasasagi <args> with stdin <stdin>")
def run_cdcasasagi_with_stdin(args, stdin):
    cmd = [sys.executable, "-m", "cdcasasagi"] + shlex.split(args)
    result = subprocess.run(cmd, input=stdin, capture_output=True, text=True)
    data_store.scenario["last_result"] = result


@step("stderr contains <text>")
def assert_stderr_contains(text):
    result = data_store.scenario["last_result"]
    assert text in result.stderr, (
        f"stderr does not contain {text!r}\nstderr:\n{result.stderr}"
    )
