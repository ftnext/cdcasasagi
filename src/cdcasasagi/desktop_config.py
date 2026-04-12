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


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"mcpServers": {}}
    try:
        text = path.read_text(encoding="utf-8")
        return json.loads(text)
    except (json.JSONDecodeError, ValueError) as e:
        raise ConfigError(
            f"設定ファイルの JSON パースに失敗しました: {path}\n"
            f"ファイルを確認してください: {e}"
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
        raise EntryExistsError(f'既に "{name}" が存在します。--force で上書きできます')

    config["mcpServers"][name] = entry
    return config


def serialize_config(config: dict[str, Any]) -> str:
    return json.dumps(config, indent=2, ensure_ascii=False) + "\n"


def write_config(path: Path, config: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        backup = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, backup)

    content = serialize_config(config)
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
