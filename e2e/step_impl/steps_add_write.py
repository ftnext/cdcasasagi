from __future__ import annotations

import json
import os
from pathlib import Path

from getgauge.python import data_store, step

from cdcasasagi.desktop_config import backup_path, config_path


def _parse_names(names: str) -> set[str]:
    return {n.strip() for n in names.split(",") if n.strip()}


def _load_json(path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@step(
    [
        "<names> entry is written to the config file",
        "<names> entries are written to the config file",
    ]
)
def assert_config_has_entries(names):
    path = config_path()
    config = _load_json(path)
    actual = set(config.get("mcpServers", {}).keys())
    expected = _parse_names(names)
    assert actual == expected, f"expected entries {expected}, got {actual}"
    data_store.scenario["last_written_config"] = path.read_bytes()


@step("The backup file is created")
def assert_backup_exists():
    bak = backup_path(config_path())
    assert bak.exists(), f"backup file not found: {bak}"


@step(
    [
        "<names> entry is written to the backup file",
        "<names> entries are written to the backup file",
    ]
)
def assert_backup_has_entries(names):
    bak = backup_path(config_path())
    assert bak.exists(), f"backup file not found: {bak}"
    config = _load_json(bak)
    actual = set(config.get("mcpServers", {}).keys())
    expected = _parse_names(names)
    assert actual == expected, f"expected backup entries {expected}, got {actual}"


@step("The last command fails")
def assert_last_command_failed():
    result = data_store.scenario["last_result"]
    assert result.returncode != 0, (
        f"expected non-zero exit, got {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


@step("The config file is unchanged since the last write")
def assert_config_unchanged_since_last_write():
    snapshot = data_store.scenario["last_written_config"]
    current = config_path().read_bytes()
    assert current == snapshot, (
        f"config changed since last write.\nexpected:\n{snapshot!r}\nactual:\n{current!r}"
    )


@step("The URL of <name> in the config file is <url>")
def assert_entry_url(name, url):
    config = _load_json(config_path())
    entry = config.get("mcpServers", {}).get(name)
    assert entry is not None, f'entry "{name}" not found in config'
    args = entry.get("args", [])
    assert args and args[-1] == url, (
        f'expected URL {url!r} at end of args for "{name}", got args={args!r}'
    )


@step(
    "The <name> entry's command is an absolute path using the platform's native separator"
)
def assert_command_native_separator(name):
    config = _load_json(config_path())
    entry = config.get("mcpServers", {}).get(name)
    assert entry is not None, f'entry "{name}" not found in config'
    command = entry.get("command", "")
    assert Path(command).is_absolute(), f"command is not absolute: {command!r}"
    expected_basename = "mcp-proxy.exe" if os.name == "nt" else "mcp-proxy"
    assert Path(command).name == expected_basename, (
        f"expected command basename {expected_basename!r}, got {Path(command).name!r}"
    )
    foreign_sep = "/" if os.sep == "\\" else "\\"
    assert foreign_sep not in command, (
        f"command contains foreign separator {foreign_sep!r} "
        f"(native is {os.sep!r}): {command!r}"
    )
    assert os.sep in command, (
        f"command does not contain native separator {os.sep!r}: {command!r}"
    )


@step(
    "The --windows-forward-slashes outcome matches the platform for the <name> entry"
)
def assert_windows_forward_slashes_outcome(name):
    """Single step asserting platform-correct behavior of --windows-forward-slashes.

    On Windows: the entry's command is an absolute mcp-proxy.exe path written
    with `/` and no `\\`. On macOS/Linux: the command failed with the
    "only valid on Windows" error and no config file was written.
    """
    result = data_store.scenario["last_result"]
    if os.name == "nt":
        assert result.returncode == 0, (
            f"expected success on Windows, got exit {result.returncode}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        config = _load_json(config_path())
        entry = config.get("mcpServers", {}).get(name)
        assert entry is not None, f'entry "{name}" not found in config'
        command = entry.get("command", "")
        assert "/" in command, f"expected '/' in command on Windows, got {command!r}"
        assert "\\" not in command, (
            f"expected no '\\\\' in command on Windows, got {command!r}"
        )
        assert command.endswith("mcp-proxy.exe"), (
            f"expected command basename mcp-proxy.exe, got {command!r}"
        )
    else:
        assert result.returncode != 0, (
            f"expected non-zero exit on POSIX, got {result.returncode}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        combined = (result.stdout or "") + (result.stderr or "")
        assert "only valid on Windows" in combined, (
            f"expected 'only valid on Windows' in output, got:\n{combined}"
        )
        config = _load_json(config_path())
        assert config.get("mcpServers", {}) == {}, (
            f"expected no entries written on POSIX, got {config.get('mcpServers')!r}"
        )
