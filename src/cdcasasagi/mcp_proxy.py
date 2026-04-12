from __future__ import annotations

import os
import sys
from pathlib import Path


class McpProxyNotFoundError(Exception):
    pass


def resolve_path() -> Path:
    bin_dir = Path(sys.executable).parent
    name = "mcp-proxy.exe" if os.name == "nt" else "mcp-proxy"
    candidate = bin_dir / name
    if candidate.exists() and candidate.is_file():
        return candidate
    raise McpProxyNotFoundError(
        "mcp-proxy が見つかりません。"
        "このツールは uv tool install cdcasasagi 経由でインストールしてください。"
        "uvx での一時実行では設定ファイルに書き込んだパスが永続化されません。"
    )
