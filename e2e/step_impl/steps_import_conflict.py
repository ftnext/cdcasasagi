from __future__ import annotations

import json
import shlex
import subprocess
import sys

from getgauge.python import data_store, step


@step("Pipe JSONL to cdcasasagi <args> <table>")
def pipe_jsonl_to_cdcasasagi(args, table):
    urls = table.get_column_values_with_name("url")
    stdin_text = "".join(json.dumps({"url": url}) + "\n" for url in urls)
    cmd = [sys.executable, "-m", "cdcasasagi"] + shlex.split(args)
    result = subprocess.run(cmd, capture_output=True, text=True, input=stdin_text)
    data_store.scenario["last_result"] = result
