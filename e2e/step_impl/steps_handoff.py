from __future__ import annotations

import json
import shlex
import subprocess
import sys
from pathlib import Path

from getgauge.python import data_store, step

from cdcasasagi.desktop_config import config_path

_JSONL_KEYS = ("url", "name", "transport")


def _row_to_entry(headers: list[str], row: list[str]) -> dict[str, str]:
    entry: dict[str, str] = {}
    for header, value in zip(headers, row):
        if header in _JSONL_KEYS and value:
            entry[header] = value
    return entry


@step("Run cdcasasagi <args> with the following JSONL piped to stdin <table>")
def run_cdcasasagi_with_jsonl(args, table):
    lines = [json.dumps(_row_to_entry(table.headers, row)) for row in table.rows]
    stdin_input = "\n".join(lines) + "\n"
    cmd = [sys.executable, "-m", "cdcasasagi"] + shlex.split(args)
    result = subprocess.run(cmd, input=stdin_input, capture_output=True, text=True)
    data_store.scenario["last_result"] = result


@step("No staging file <path> is created")
def assert_staging_file_not_created(path):
    staged = Path(path)
    assert not staged.exists(), f"unexpected staging file: {staged.resolve()}"


@step("The config file has no MCP server entries")
def assert_config_has_no_entries():
    config = json.loads(config_path().read_text(encoding="utf-8"))
    servers = config.get("mcpServers", {})
    assert servers == {}, f"expected no mcpServers entries, got {servers}"
