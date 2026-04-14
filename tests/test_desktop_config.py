import json
from pathlib import Path

import pytest

from cdcasasagi.desktop_config import (
    BackupError,
    BackupNotFoundError,
    ConfigError,
    EntryExistsError,
    apply_import,
    backup_path,
    build_entry,
    config_path,
    load_backup,
    load_config,
    merge_entry,
    plan_import,
    revert_config,
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


class TestBackupPath:
    def test_basic(self):
        assert backup_path(Path("/tmp/config.json")) == Path("/tmp/config.json.bak")

    def test_preserves_directory(self):
        p = Path("/home/user/.config/claude_desktop_config.json")
        assert backup_path(p).parent == p.parent


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


class TestLoadBackup:
    def test_backup_not_found(self, tmp_path):
        p = tmp_path / "config.json"
        with pytest.raises(BackupNotFoundError):
            load_backup(p)

    def test_valid_backup(self, tmp_path):
        p = tmp_path / "config.json"
        bak = tmp_path / "config.json.bak"
        bak.write_text('{"mcpServers": {}}')
        assert load_backup(p) == {"mcpServers": {}}

    def test_corrupted_backup(self, tmp_path):
        p = tmp_path / "config.json"
        bak = tmp_path / "config.json.bak"
        bak.write_text("not json")
        with pytest.raises(BackupError):
            load_backup(p)

    def test_unreadable_backup(self, tmp_path):
        p = tmp_path / "config.json"
        bak = tmp_path / "config.json.bak"
        bak.mkdir()  # directory, not a file
        with pytest.raises(BackupError, match="Cannot read"):
            load_backup(p)


class TestRevertConfig:
    def test_reverts_content(self, tmp_path):
        p = tmp_path / "config.json"
        p.write_text(json.dumps({"mcpServers": {"new": {}}}))
        bak = tmp_path / "config.json.bak"
        bak.write_text(json.dumps({"mcpServers": {}}))
        revert_config(p, {"mcpServers": {}})
        assert json.loads(p.read_text()) == {"mcpServers": {}}

    def test_deletes_backup(self, tmp_path):
        p = tmp_path / "config.json"
        p.write_text(json.dumps({"mcpServers": {"new": {}}}))
        bak = tmp_path / "config.json.bak"
        bak.write_text(json.dumps({"mcpServers": {}}))
        revert_config(p, {"mcpServers": {}})
        assert not bak.exists()

    def test_creates_file_if_not_exists(self, tmp_path):
        p = tmp_path / "config.json"
        bak = tmp_path / "config.json.bak"
        bak.write_text(json.dumps({"mcpServers": {}}))
        revert_config(p, {"mcpServers": {}})
        assert p.exists()
        assert not bak.exists()

    def test_trailing_newline(self, tmp_path):
        p = tmp_path / "config.json"
        bak = tmp_path / "config.json.bak"
        bak.write_text(json.dumps({"mcpServers": {}}))
        revert_config(p, {"mcpServers": {}})
        assert p.read_text().endswith("\n")


class TestPlanImport:
    def test_all_new(self):
        config = {"mcpServers": {}}
        entries = [("a", {"command": "x"}), ("b", {"command": "y"})]
        plan = plan_import(config, entries)
        assert plan == [
            ("a", "add", {"command": "x"}),
            ("b", "add", {"command": "y"}),
        ]

    def test_identical(self):
        config = {"mcpServers": {"a": {"command": "x"}}}
        entries = [("a", {"command": "x"})]
        plan = plan_import(config, entries)
        assert plan == [("a", "identical", {"command": "x"})]

    def test_conflict(self):
        config = {"mcpServers": {"a": {"command": "old"}}}
        entries = [("a", {"command": "new"})]
        plan = plan_import(config, entries)
        assert plan == [("a", "conflict", {"command": "new"})]

    def test_mixed(self):
        config = {"mcpServers": {"existing": {"command": "x"}}}
        entries = [
            ("existing", {"command": "x"}),  # identical
            ("new", {"command": "y"}),  # add
        ]
        plan = plan_import(config, entries)
        assert plan[0][1] == "identical"
        assert plan[1][1] == "add"

    def test_empty_mcpservers(self):
        config = {"other": "value"}
        entries = [("a", {"command": "x"})]
        plan = plan_import(config, entries)
        assert plan == [("a", "add", {"command": "x"})]

    def test_mcpservers_is_null(self):
        config = {"mcpServers": None}
        entries = [("a", {"command": "x"})]
        plan = plan_import(config, entries)
        assert plan == [("a", "add", {"command": "x"})]

    def test_mcpservers_is_list(self):
        config = {"mcpServers": []}
        entries = [("a", {"command": "x"})]
        plan = plan_import(config, entries)
        assert plan == [("a", "add", {"command": "x"})]


class TestApplyImport:
    def test_adds_new_entries(self):
        config = {"mcpServers": {}}
        plan = [("a", "add", {"command": "x"}), ("b", "add", {"command": "y"})]
        result = apply_import(config, plan, force=False)
        assert "a" in result["mcpServers"]
        assert "b" in result["mcpServers"]

    def test_skips_identical(self):
        config = {"mcpServers": {"a": {"command": "x"}}}
        plan = [("a", "identical", {"command": "x"})]
        result = apply_import(config, plan, force=False)
        assert result["mcpServers"]["a"] == {"command": "x"}

    def test_skips_conflict_without_force(self):
        config = {"mcpServers": {"a": {"command": "old"}}}
        plan = [("a", "conflict", {"command": "new"})]
        result = apply_import(config, plan, force=False)
        assert result["mcpServers"]["a"] == {"command": "old"}

    def test_overwrites_conflict_with_force(self):
        config = {"mcpServers": {"a": {"command": "old"}}}
        plan = [("a", "conflict", {"command": "new"})]
        result = apply_import(config, plan, force=True)
        assert result["mcpServers"]["a"] == {"command": "new"}

    def test_preserves_other_keys(self):
        config = {"mcpServers": {"old": {"command": "y"}}, "other": "keep"}
        plan = [("new", "add", {"command": "x"})]
        result = apply_import(config, plan, force=False)
        assert result["other"] == "keep"
        assert "old" in result["mcpServers"]

    def test_does_not_mutate_original(self):
        config = {"mcpServers": {}}
        plan = [("a", "add", {"command": "x"})]
        apply_import(config, plan, force=False)
        assert "a" not in config["mcpServers"]

    def test_creates_mcpservers_if_missing(self):
        config = {"other": "value"}
        plan = [("a", "add", {"command": "x"})]
        result = apply_import(config, plan, force=False)
        assert "a" in result["mcpServers"]

    def test_mcpservers_is_null(self):
        config = {"mcpServers": None}
        plan = [("a", "add", {"command": "x"})]
        result = apply_import(config, plan, force=False)
        assert result["mcpServers"]["a"] == {"command": "x"}

    def test_mcpservers_is_list(self):
        config = {"mcpServers": []}
        plan = [("a", "add", {"command": "x"})]
        result = apply_import(config, plan, force=False)
        assert result["mcpServers"]["a"] == {"command": "x"}
