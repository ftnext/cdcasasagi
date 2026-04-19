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
    headers = set(table.headers)
    names = table.get_column_values_with_name("name") if "name" in headers else None

    lines: list[str] = []
    for i, url in enumerate(urls):
        obj: dict[str, str] = {"url": url}
        if names is not None and names[i]:
            obj["name"] = names[i]
        lines.append(json.dumps(obj))
    stdin_text = "\n".join(lines) + "\n"

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


@step("<name> entry does not exist in the config file")
def assert_entry_missing(name):
    config = json.loads(config_path().read_text(encoding="utf-8"))
    assert name not in config.get("mcpServers", {}), (
        f'entry "{name}" unexpectedly present in config'
    )
