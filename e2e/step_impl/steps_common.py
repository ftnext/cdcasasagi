from __future__ import annotations

import os
import shlex
import subprocess
import sys

from getgauge.python import data_store, step

from cdcasasagi.desktop_config import config_path

_INITIAL_CONFIG = "{}"


def _guard_against_overwriting_real_config():
    """Refuse to run when we might clobber the developer's real Claude Desktop config.

    In GitHub Actions the default config path is safe to use (the runner has no
    pre-existing config). Locally, developers must opt in by setting
    ``CLAUDE_DESKTOP_CONFIG`` (typically via ``e2e/env/default/local.properties``).
    """
    if os.environ.get("CLAUDE_DESKTOP_CONFIG"):
        return
    if os.environ.get("GITHUB_ACTIONS") == "true":
        return
    raise RuntimeError(
        "Refusing to run: CLAUDE_DESKTOP_CONFIG is not set and this does not "
        "look like a GitHub Actions run. Set CLAUDE_DESKTOP_CONFIG to a "
        "throwaway path (e.g. via e2e/env/default/local.properties) to avoid "
        "overwriting your real Claude Desktop config."
    )


@step("MCPサーバ設定なしでClaude Desktopが使われている")
def given_claude_desktop_without_mcp_servers():
    _guard_against_overwriting_real_config()
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_INITIAL_CONFIG, encoding="utf-8")
    data_store.scenario["initial_config"] = _INITIAL_CONFIG


@step("cdcasasagiで<args>を実行する")
def run_cdcasasagi(args):
    # Invoke the CLI via the same interpreter that imported cdcasasagi above,
    # so the E2E always exercises the code in this checkout (not whatever
    # `cdcasasagi` happens to be first on PATH).
    cmd = [sys.executable, "-m", "cdcasasagi"] + shlex.split(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    data_store.scenario["last_result"] = result


@step("設定ファイルは変更されていない")
def assert_config_unchanged():
    initial = data_store.scenario["initial_config"]
    current = config_path().read_text(encoding="utf-8")
    assert current == initial, (
        f"config file changed.\nexpected:\n{initial!r}\nactual:\n{current!r}"
    )
