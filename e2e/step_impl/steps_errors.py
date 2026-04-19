from __future__ import annotations

import shlex
import subprocess
import sys

from getgauge.python import data_store, step


@step("Run cdcasasagi <args> with the following raw lines piped to stdin <table>")
def run_cdcasasagi_with_raw_lines(args, table):
    lines = table.get_column_values_with_name("line")
    stdin_input = "\n".join(lines) + "\n"
    cmd = [sys.executable, "-m", "cdcasasagi"] + shlex.split(args)
    result = subprocess.run(cmd, input=stdin_input, capture_output=True, text=True)
    data_store.scenario["last_result"] = result


@step("stderr contains <text>")
def assert_stderr_contains(text):
    result = data_store.scenario["last_result"]
    assert text in result.stderr, (
        f"stderr does not contain {text!r}\nstderr:\n{result.stderr}"
    )
