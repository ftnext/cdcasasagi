from __future__ import annotations

import shlex
import subprocess

from getgauge.python import data_store, step

from cdcasasagi.desktop_config import config_path

_INITIAL_CONFIG = "{}"


@step("MCPサーバ設定なしでClaude Desktopが使われている")
def given_claude_desktop_without_mcp_servers():
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_INITIAL_CONFIG, encoding="utf-8")
    data_store.scenario["initial_config"] = _INITIAL_CONFIG


@step("cdcasasagiで<args>を実行する")
def run_cdcasasagi(args):
    cmd = ["cdcasasagi"] + shlex.split(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    data_store.scenario["last_result"] = result


@step("プレビューが表示される")
def assert_preview_shown():
    result = data_store.scenario["last_result"]
    assert result.returncode == 0, (
        f"exit code {result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "This is a preview" in result.stdout, (
        f"preview marker not found in stdout:\n{result.stdout}"
    )


@step("設定ファイルは変更されていない")
def assert_config_unchanged():
    initial = data_store.scenario["initial_config"]
    current = config_path().read_text(encoding="utf-8")
    assert current == initial, (
        f"config file changed.\nexpected:\n{initial!r}\nactual:\n{current!r}"
    )
