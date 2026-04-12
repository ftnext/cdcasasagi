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
        "mcp-proxy not found. "
        "Please install this tool via 'uv tool install cdcasasagi'. "
        "Temporary execution with uvx will not persist the path written to the config file."
    )
