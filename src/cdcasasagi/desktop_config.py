from __future__ import annotations

import json
import os
import platform
import shutil
import tempfile
from pathlib import Path
from typing import Any


class ConfigError(Exception):
    pass


class EntryExistsError(Exception):
    pass


class BackupNotFoundError(Exception):
    pass


class BackupError(Exception):
    pass


def config_path() -> Path:
    env = os.environ.get("CLAUDE_DESKTOP_CONFIG")
    if env:
        return Path(env)
    if platform.system() == "Windows":
        appdata = os.environ.get("APPDATA", "")
        return Path(appdata) / "Claude" / "claude_desktop_config.json"
    return (
        Path.home()
        / "Library"
        / "Application Support"
        / "Claude"
        / "claude_desktop_config.json"
    )


def backup_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".bak")


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"mcpServers": {}}
    try:
        text = path.read_text(encoding="utf-8")
        return json.loads(text)
    except (json.JSONDecodeError, ValueError) as e:
        raise ConfigError(
            f"Failed to parse JSON config file: {path}\nPlease check the file: {e}"
        ) from e


def load_backup(path: Path) -> dict[str, Any]:
    bak = backup_path(path)
    if not bak.exists():
        raise BackupNotFoundError(f"Backup not found: {bak}")
    try:
        text = bak.read_text(encoding="utf-8")
        return json.loads(text)
    except (json.JSONDecodeError, ValueError) as e:
        raise BackupError(
            f"Backup file is corrupted: {bak}\nPlease check the file: {e}"
        ) from e
    except OSError as e:
        raise BackupError(
            f"Cannot read backup file: {bak}\nPlease check the file: {e}"
        ) from e


def build_entry(mcp_proxy_path: Path, transport: str, url: str) -> dict[str, Any]:
    return {
        "command": str(mcp_proxy_path),
        "args": ["--transport", transport, url],
    }


def merge_entry(
    config: dict[str, Any],
    name: str,
    entry: dict[str, Any],
    force: bool,
) -> dict[str, Any]:
    config = json.loads(json.dumps(config))  # deep copy
    if "mcpServers" not in config:
        config["mcpServers"] = {}

    if name in config["mcpServers"] and not force:
        raise EntryExistsError(f'"{name}" already exists. Use --force to overwrite')

    config["mcpServers"][name] = entry
    return config


def plan_import(
    config: dict[str, Any],
    entries: list[tuple[str, dict[str, Any]]],
) -> list[tuple[str, str, dict[str, Any]]]:
    """Classify import entries against current config.

    Returns list of ``(name, action, entry)`` where *action* is one of
    ``'add'``, ``'identical'``, or ``'conflict'``.
    """
    servers = config.get("mcpServers", {})
    if not isinstance(servers, dict):
        servers = {}
    plan: list[tuple[str, str, dict[str, Any]]] = []
    for name, entry in entries:
        if name not in servers:
            plan.append((name, "add", entry))
        elif servers[name] == entry:
            plan.append((name, "identical", entry))
        else:
            plan.append((name, "conflict", entry))
    return plan


def apply_import(
    config: dict[str, Any],
    plan: list[tuple[str, str, dict[str, Any]]],
    force: bool,
) -> dict[str, Any]:
    """Apply an import plan – adds new entries and overwrites conflicts when *force*."""
    config = json.loads(json.dumps(config))  # deep copy
    if not isinstance(config.get("mcpServers"), dict):
        config["mcpServers"] = {}
    for name, action, entry in plan:
        if action == "add" or (action == "conflict" and force):
            config["mcpServers"][name] = entry
    return config


def serialize_config(config: dict[str, Any]) -> str:
    return json.dumps(config, indent=2, ensure_ascii=False) + "\n"


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    dir_ = path.parent
    fd, tmp = tempfile.mkstemp(dir=dir_, suffix=".tmp")
    fd_closed = False
    try:
        os.write(fd, content.encode("utf-8"))
        os.close(fd)
        fd_closed = True
        os.replace(tmp, path)
    except BaseException:
        if not fd_closed:
            os.close(fd)
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def write_config(path: Path, config: dict[str, Any]) -> None:
    if path.exists():
        shutil.copy2(path, backup_path(path))
    _atomic_write(path, serialize_config(config))


def revert_config(path: Path, config: dict[str, Any]) -> None:
    _atomic_write(path, serialize_config(config))
    backup_path(path).unlink()
