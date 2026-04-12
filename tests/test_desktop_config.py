import json
from pathlib import Path

import pytest

from cdcasasagi.desktop_config import (
    ConfigError,
    EntryExistsError,
    build_entry,
    config_path,
    load_config,
    merge_entry,
    write_config,
)


class TestConfigPath:
    def test_env_override(self, monkeypatch, tmp_path):
        p = tmp_path / "custom.json"
        monkeypatch.setenv("CLAUDE_DESKTOP_CONFIG", str(p))
        assert config_path() == p

    def test_macos_default(self, monkeypatch):
        monkeypatch.delenv("CLAUDE_DESKTOP_CONFIG", raising=False)
        monkeypatch.setattr(
            "cdcasasagi.desktop_config.platform.system", lambda: "Darwin"
        )
        result = config_path()
        assert "Claude" in str(result)
        assert result.name == "claude_desktop_config.json"

    def test_windows_default(self, monkeypatch):
        monkeypatch.delenv("CLAUDE_DESKTOP_CONFIG", raising=False)
        monkeypatch.setattr(
            "cdcasasagi.desktop_config.platform.system", lambda: "Windows"
        )
        monkeypatch.setenv("APPDATA", "/fake/appdata")
        result = config_path()
        assert result == Path("/fake/appdata/Claude/claude_desktop_config.json")


class TestLoadConfig:
    def test_file_not_exists(self, tmp_path):
        p = tmp_path / "nonexistent.json"
        result = load_config(p)
        assert result == {"mcpServers": {}}

    def test_valid_json(self, tmp_path):
        p = tmp_path / "config.json"
        data = {"mcpServers": {"test": {}}, "other": "value"}
        p.write_text(json.dumps(data))
        assert load_config(p) == data

    def test_invalid_json(self, tmp_path):
        p = tmp_path / "config.json"
        p.write_text("not json")
        with pytest.raises(ConfigError):
            load_config(p)


class TestBuildEntry:
    def test_basic(self):
        entry = build_entry(
            Path("/usr/bin/mcp-proxy"), "streamablehttp", "https://mcp.notion.com/mcp"
        )
        assert entry == {
            "command": "/usr/bin/mcp-proxy",
            "args": ["--transport", "streamablehttp", "https://mcp.notion.com/mcp"],
        }


class TestMergeEntry:
    def test_add_to_empty(self):
        config = {"mcpServers": {}}
        entry = {"command": "x", "args": []}
        result = merge_entry(config, "notion", entry, force=False)
        assert "notion" in result["mcpServers"]

    def test_preserves_existing(self):
        config = {"mcpServers": {"old": {"command": "y"}}, "other": "keep"}
        entry = {"command": "x", "args": []}
        result = merge_entry(config, "new", entry, force=False)
        assert "old" in result["mcpServers"]
        assert "new" in result["mcpServers"]
        assert result["other"] == "keep"

    def test_duplicate_without_force(self):
        config = {"mcpServers": {"notion": {"command": "old"}}}
        entry = {"command": "new", "args": []}
        with pytest.raises(EntryExistsError):
            merge_entry(config, "notion", entry, force=False)

    def test_duplicate_with_force(self):
        config = {"mcpServers": {"notion": {"command": "old"}}}
        entry = {"command": "new", "args": []}
        result = merge_entry(config, "notion", entry, force=True)
        assert result["mcpServers"]["notion"]["command"] == "new"

    def test_creates_mcpservers_if_missing(self):
        config = {"other": "value"}
        entry = {"command": "x", "args": []}
        result = merge_entry(config, "notion", entry, force=False)
        assert "notion" in result["mcpServers"]

    def test_does_not_mutate_original(self):
        config = {"mcpServers": {}}
        entry = {"command": "x", "args": []}
        merge_entry(config, "notion", entry, force=False)
        assert "notion" not in config["mcpServers"]


class TestWriteConfig:
    def test_creates_file(self, tmp_path):
        p = tmp_path / "config.json"
        data = {"mcpServers": {"test": {}}}
        write_config(p, data)
        assert p.exists()
        assert json.loads(p.read_text()) == data

    def test_creates_backup(self, tmp_path):
        p = tmp_path / "config.json"
        p.write_text('{"old": true}')
        write_config(p, {"mcpServers": {}})
        backup = tmp_path / "config.json.bak"
        assert backup.exists()
        assert json.loads(backup.read_text()) == {"old": True}

    def test_no_backup_if_file_not_exists(self, tmp_path):
        p = tmp_path / "config.json"
        write_config(p, {"mcpServers": {}})
        backup = tmp_path / "config.json.bak"
        assert not backup.exists()

    def test_trailing_newline(self, tmp_path):
        p = tmp_path / "config.json"
        write_config(p, {"mcpServers": {}})
        assert p.read_text().endswith("\n")
