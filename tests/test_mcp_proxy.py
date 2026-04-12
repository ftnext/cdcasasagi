from unittest.mock import patch

import pytest

from cdcasasagi.mcp_proxy import McpProxyNotFoundError, resolve_path


def test_resolve_path_found(tmp_path):
    fake_bin = tmp_path / "mcp-proxy"
    fake_bin.touch()
    fake_executable = tmp_path / "python"

    with patch("cdcasasagi.mcp_proxy.sys") as mock_sys:
        mock_sys.executable = str(fake_executable)
        result = resolve_path()

    assert result == fake_bin


def test_resolve_path_not_found(tmp_path):
    fake_executable = tmp_path / "python"

    with patch("cdcasasagi.mcp_proxy.sys") as mock_sys:
        mock_sys.executable = str(fake_executable)
        with pytest.raises(McpProxyNotFoundError):
            resolve_path()


def test_resolve_path_windows(tmp_path):
    fake_bin = tmp_path / "mcp-proxy.exe"
    fake_bin.touch()
    fake_executable = tmp_path / "python.exe"

    with (
        patch("cdcasasagi.mcp_proxy.sys") as mock_sys,
        patch("cdcasasagi.mcp_proxy.os") as mock_os,
    ):
        mock_sys.executable = str(fake_executable)
        mock_os.name = "nt"
        mock_os.path = __import__("os").path
        result = resolve_path()

    assert result == fake_bin
