from __future__ import annotations

import json

from getgauge.python import data_store, step

from cdcasasagi.desktop_config import backup_path, config_path


def _parse_names(names: str) -> set[str]:
    return {n.strip() for n in names.split(",") if n.strip()}


def _load_json(path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@step("設定ファイルに<names>エントリが書き込まれている")
def assert_config_has_entries(names):
    path = config_path()
    config = _load_json(path)
    actual = set(config.get("mcpServers", {}).keys())
    expected = _parse_names(names)
    assert actual == expected, f"expected entries {expected}, got {actual}"
    data_store.scenario["last_written_config"] = path.read_bytes()


@step("バックアップファイルが作成されている")
def assert_backup_exists():
    bak = backup_path(config_path())
    assert bak.exists(), f"backup file not found: {bak}"


@step("バックアップファイルに<names>エントリが書き込まれている")
def assert_backup_has_entries(names):
    bak = backup_path(config_path())
    assert bak.exists(), f"backup file not found: {bak}"
    config = _load_json(bak)
    actual = set(config.get("mcpServers", {}).keys())
    expected = _parse_names(names)
    assert actual == expected, f"expected backup entries {expected}, got {actual}"


@step("直前のコマンドは失敗する")
def assert_last_command_failed():
    result = data_store.scenario["last_result"]
    assert result.returncode != 0, (
        f"expected non-zero exit, got {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


@step("設定ファイルは直前の書き込みから変更されていない")
def assert_config_unchanged_since_last_write():
    snapshot = data_store.scenario["last_written_config"]
    current = config_path().read_bytes()
    assert current == snapshot, (
        f"config changed since last write.\nexpected:\n{snapshot!r}\nactual:\n{current!r}"
    )


@step("設定ファイル内<name>のURLは<url>である")
def assert_entry_url(name, url):
    config = _load_json(config_path())
    entry = config.get("mcpServers", {}).get(name)
    assert entry is not None, f'entry "{name}" not found in config'
    args = entry.get("args", [])
    assert args and args[-1] == url, (
        f'expected URL {url!r} at end of args for "{name}", got args={args!r}'
    )
