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


class DuplicateUrlError(Exception):
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


def find_entry_names_by_url(config: dict[str, Any], url: str) -> list[str]:
    """Return names of all entries whose args end with *url*."""
    names: list[str] = []
    for name, entry in config.get("mcpServers", {}).items():
        args = entry.get("args", [])
        if args and args[-1] == url:
            names.append(name)
    return names


def list_mcp_proxy_entries(config: dict[str, Any]) -> list[tuple[str, str]]:
    """Return ``(name, url)`` for every entry whose command basename is mcp-proxy.

    Entries with unexpected ``args`` shape are skipped.
    """
    result: list[tuple[str, str]] = []
    for name, entry in config.get("mcpServers", {}).items():
        cmd = entry.get("command", "")
        if Path(cmd).name not in {"mcp-proxy", "mcp-proxy.exe"}:
            continue
        args = entry.get("args", [])
        if not isinstance(args, list) or len(args) < 3 or args[0] != "--transport":
            continue
        result.append((name, args[-1]))
    result.sort(key=lambda x: x[0])
    return result


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
    *,
    url: str | None = None,
) -> dict[str, Any]:
    config = json.loads(json.dumps(config))  # deep copy
    if "mcpServers" not in config:
        config["mcpServers"] = {}

    if url is not None:
        others = [n for n in find_entry_names_by_url(config, url) if n != name]
        if others:
            if not force:
                raise DuplicateUrlError(
                    f'URL already configured as "{others[0]}". Use --force to overwrite'
                )
            for n in others:
                del config["mcpServers"][n]

    if name in config["mcpServers"] and not force:
        raise EntryExistsError(f'"{name}" already exists. Use --force to overwrite')

    config["mcpServers"][name] = entry
    return config


def plan_import(
    config: dict[str, Any],
    entries: list[tuple[str, str, dict[str, Any]]],
) -> list[tuple[str, str, dict[str, Any]]]:
    """Classify import entries against current config.

    *entries* is a list of ``(name, url, entry)``. Returns a list of
    ``(name, action, entry)`` where *action* is one of ``'add'``,
    ``'identical'``, or ``'conflict'``. A URL that already exists in the
    config under a different name counts as a conflict.
    """
    servers = config.get("mcpServers", {})
    plan: list[tuple[str, str, dict[str, Any]]] = []
    for name, url, entry in entries:
        if name in servers:
            if servers[name] == entry:
                plan.append((name, "identical", entry))
            else:
                plan.append((name, "conflict", entry))
        elif find_entry_names_by_url(config, url):
            plan.append((name, "conflict", entry))
        else:
            plan.append((name, "add", entry))
    return plan


def apply_import(
    config: dict[str, Any],
    plan: list[tuple[str, str, dict[str, Any]]],
    force: bool,
) -> dict[str, Any]:
    """Apply an import plan – adds new entries and overwrites conflicts when *force*.

    On a URL alias conflict (new name, existing URL under another name),
    ``--force`` removes the aliased entry before writing the new one.
    """
    config = json.loads(json.dumps(config))  # deep copy
    if "mcpServers" not in config:
        config["mcpServers"] = {}
    for name, action, entry in plan:
        if action == "add":
            config["mcpServers"][name] = entry
        elif action == "conflict" and force:
            args = entry.get("args", [])
            if args:
                url = args[-1]
                for other in find_entry_names_by_url(config, url):
                    if other != name:
                        del config["mcpServers"][other]
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
