from __future__ import annotations

import json
import shlex
import subprocess
import sys

from getgauge.python import data_store, step

from cdcasasagi.desktop_config import config_path


@step("Pipe JSONL to cdcasasagi <args> <table>")
def pipe_jsonl_to_cdcasasagi(args, table):
    urls = table.get_column_values_with_name("url")
    stdin_text = "".join(json.dumps({"url": url}) + "\n" for url in urls)
    cmd = [sys.executable, "-m", "cdcasasagi"] + shlex.split(args)
    result = subprocess.run(cmd, capture_output=True, text=True, input=stdin_text)
    data_store.scenario["last_result"] = result


@step("The transport of <name> in the config file is <transport>")
def assert_entry_transport(name, transport):
    config = json.loads(config_path().read_text(encoding="utf-8"))
    entry = config.get("mcpServers", {}).get(name)
    assert entry is not None, f'entry "{name}" not found in config'
    args = entry.get("args", [])
    assert len(args) >= 2 and args[0] == "--transport" and args[1] == transport, (
        f'expected transport {transport!r} for "{name}", got args={args!r}'
    )
