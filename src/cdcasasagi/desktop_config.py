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


class EntryNotFoundError(Exception):
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


def windows_msix_config_candidates() -> list[Path]:
    """Return claude_desktop_config.json paths under the MSIX virtualized
    Packages directory, sorted for determinism. Empty list on non-Windows,
    missing %LOCALAPPDATA%, or no match.
    """
    if platform.system() != "Windows":
        return []
    local = os.environ.get("LOCALAPPDATA", "")
    if not local:
        return []
    packages = Path(local) / "Packages"
    if not packages.is_dir():
        return []
    candidates: list[Path] = []
    for pkg in packages.glob("*Claude*"):
        claude_dir = pkg / "LocalCache" / "Roaming" / "Claude"
        if claude_dir.is_dir():
            candidates.append(claude_dir / "claude_desktop_config.json")
    candidates.sort()
    return candidates


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
        if len(args) < 3 or args[0] != "--transport":
            continue
        result.append((name, args[-1]))
    result.sort(key=lambda x: x[0])
    return result


def build_entry(mcp_proxy_path: Path, transport: str, url: str) -> dict[str, Any]:
    return {
        "command": str(mcp_proxy_path),
        "args": ["--transport", transport, url],
    }


def _replace_preserving_order(
    servers: dict[str, Any],
    name: str,
    entry: dict[str, Any],
    replaces: list[str],
) -> dict[str, Any]:
    """Return a new ``mcpServers`` dict with ``name -> entry``, dropping every
    key in ``replaces``.

    ``name`` takes the earliest original position among ``replaces + [name]``
    that exists in *servers*. If none of those keys are present, ``name`` is
    appended at the end. Preserving the slot keeps the preview diff limited to
    the renamed key instead of showing a delete-and-append of the whole entry.
    """
    drop = set(replaces) | {name}
    out: dict[str, Any] = {}
    inserted = False
    for key, val in servers.items():
        if key in drop:
            if not inserted:
                out[name] = entry
                inserted = True
        else:
            out[key] = val
    if not inserted:
        out[name] = entry
    return out


def merge_entry(
    config: dict[str, Any],
    name: str,
    entry: dict[str, Any],
    force: bool,
    *,
    url: str | None = None,
) -> dict[str, Any]:
    config = json.loads(json.dumps(config))  # deep copy
    servers = config.setdefault("mcpServers", {})

    others: list[str] = []
    if url is not None:
        others = [n for n in find_entry_names_by_url(config, url) if n != name]
        if others and not force:
            raise DuplicateUrlError(
                f'URL already configured as "{others[0]}". Use --force to overwrite'
            )

    if name in servers and not others and not force:
        raise EntryExistsError(f'"{name}" already exists. Use --force to overwrite')

    config["mcpServers"] = _replace_preserving_order(servers, name, entry, others)
    return config


def remove_entries_by_url(
    config: dict[str, Any], url: str
) -> tuple[dict[str, Any], list[str]]:
    """Remove every cdcasasagi-managed entry whose URL matches.

    An entry is considered managed when ``command`` basename is ``mcp-proxy``
    (or ``mcp-proxy.exe``) and ``args`` starts with ``--transport`` followed
    by a transport value and the URL -- the same shape written by ``add``
    and required by ``list_mcp_proxy_entries``. Hand-edited entries that
    happen to end in *url* are left alone. Raises :class:`EntryNotFoundError`
    when nothing matches. Returns ``(updated_config, removed_names)``.
    """
    config = json.loads(json.dumps(config))  # deep copy
    servers = config.setdefault("mcpServers", {})
    names: list[str] = []
    for name, entry in servers.items():
        cmd = entry.get("command", "")
        if Path(cmd).name not in {"mcp-proxy", "mcp-proxy.exe"}:
            continue
        args = entry.get("args", [])
        if len(args) < 3 or args[0] != "--transport":
            continue
        if args[-1] == url:
            names.append(name)
    if not names:
        raise EntryNotFoundError(f"No cdcasasagi-managed entry found for URL: {url}")
    for name in names:
        del servers[name]
    return config, names


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
            url = args[-1] if args else None
            replaces = (
                [n for n in find_entry_names_by_url(config, url) if n != name]
                if url is not None
                else []
            )
            config["mcpServers"] = _replace_preserving_order(
                config["mcpServers"], name, entry, replaces
            )
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
