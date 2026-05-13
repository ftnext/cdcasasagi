from __future__ import annotations

import shlex
import subprocess
import sys

from getgauge.python import data_store, step


@step("stdout has <count> JSONL lines")
def assert_stdout_jsonl_line_count(count):
    result = data_store.scenario["last_result"]
    expected = int(count)
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(lines) == expected, (
        f"expected {expected} JSONL lines on stdout, got {len(lines)}\n"
        f"stdout:\n{result.stdout}"
    )


@step("Pipe the previous stdout to cdcasasagi <args>")
def pipe_previous_stdout_to_cdcasasagi(args):
    previous = data_store.scenario["last_result"]
    cmd = [sys.executable, "-m", "cdcasasagi"] + shlex.split(args)
    result = subprocess.run(
        cmd, capture_output=True, text=True, input=previous.stdout
    )
    data_store.scenario["last_result"] = result
