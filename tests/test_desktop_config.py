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


def _entry(url: str, command: str = "x") -> dict:
    return {"command": command, "args": ["--transport", "streamablehttp", url]}


class TestPlanImport:
    def test_all_new(self):
        config = {"mcpServers": {}}
        a_entry = _entry("https://a.example/mcp")
        b_entry = _entry("https://b.example/mcp")
        entries = [
            ("a", "https://a.example/mcp", a_entry),
            ("b", "https://b.example/mcp", b_entry),
        ]
        plan = plan_import(config, entries)
        assert plan == [
            ("a", "add", a_entry),
            ("b", "add", b_entry),
        ]

    def test_identical(self):
        a_entry = _entry("https://a.example/mcp")
        config = {"mcpServers": {"a": a_entry}}
        entries = [("a", "https://a.example/mcp", a_entry)]
        plan = plan_import(config, entries)
        assert plan == [("a", "identical", a_entry)]

    def test_conflict_same_name(self):
        old = _entry("https://a.example/mcp", command="old")
        new = _entry("https://a.example/mcp", command="new")
        config = {"mcpServers": {"a": old}}
        entries = [("a", "https://a.example/mcp", new)]
        plan = plan_import(config, entries)
        assert plan == [("a", "conflict", new)]

    def test_conflict_url_under_different_name(self):
        """Same URL, new name → conflict (not add)."""
        url = "https://mcp.notion.com/mcp"
        existing = _entry(url)
        incoming = _entry(url, command="different")
        config = {"mcpServers": {"notion": existing}}
        entries = [("my-notion", url, incoming)]
        plan = plan_import(config, entries)
        assert plan == [("my-notion", "conflict", incoming)]

    def test_mixed(self):
        existing = _entry("https://existing.example/mcp")
        incoming_new = _entry("https://new.example/mcp")
        config = {"mcpServers": {"existing": existing}}
        entries = [
            ("existing", "https://existing.example/mcp", existing),  # identical
            ("new", "https://new.example/mcp", incoming_new),  # add
        ]
        plan = plan_import(config, entries)
        assert plan[0][1] == "identical"
        assert plan[1][1] == "add"

    def test_empty_mcpservers(self):
        e = _entry("https://a.example/mcp")
        config = {"other": "value"}
        entries = [("a", "https://a.example/mcp", e)]
        plan = plan_import(config, entries)
        assert plan == [("a", "add", e)]


class TestApplyImport:
    def test_adds_new_entries(self):
        config = {"mcpServers": {}}
        a = _entry("https://a.example/mcp")
        b = _entry("https://b.example/mcp")
        plan = [("a", "add", a), ("b", "add", b)]
        result = apply_import(config, plan, force=False)
        assert "a" in result["mcpServers"]
        assert "b" in result["mcpServers"]

    def test_skips_identical(self):
        a = _entry("https://a.example/mcp")
        config = {"mcpServers": {"a": a}}
        plan = [("a", "identical", a)]
        result = apply_import(config, plan, force=False)
        assert result["mcpServers"]["a"] == a

    def test_skips_conflict_without_force(self):
        old = _entry("https://a.example/mcp", command="old")
        new = _entry("https://a.example/mcp", command="new")
        config = {"mcpServers": {"a": old}}
        plan = [("a", "conflict", new)]
        result = apply_import(config, plan, force=False)
        assert result["mcpServers"]["a"] == old

    def test_overwrites_conflict_with_force(self):
        old = _entry("https://a.example/mcp", command="old")
        new = _entry("https://a.example/mcp", command="new")
        config = {"mcpServers": {"a": old}}
        plan = [("a", "conflict", new)]
        result = apply_import(config, plan, force=True)
        assert result["mcpServers"]["a"] == new

    def test_url_alias_conflict_force_removes_existing_alias(self):
        """`--force` removes the aliased entry and writes under the new name."""
        url = "https://mcp.notion.com/mcp"
        existing = _entry(url)
        incoming = _entry(url, command="new")
        config = {"mcpServers": {"notion": existing}}
        plan = [("my-notion", "conflict", incoming)]
        result = apply_import(config, plan, force=True)
        assert "my-notion" in result["mcpServers"]
        assert "notion" not in result["mcpServers"]
        assert result["mcpServers"]["my-notion"] == incoming

    def test_url_alias_conflict_without_force_does_not_remove(self):
        url = "https://mcp.notion.com/mcp"
        existing = _entry(url)
        incoming = _entry(url, command="new")
        config = {"mcpServers": {"notion": existing}}
        plan = [("my-notion", "conflict", incoming)]
        result = apply_import(config, plan, force=False)
        assert "notion" in result["mcpServers"]
        assert "my-notion" not in result["mcpServers"]

    def test_preserves_other_keys(self):
        e = _entry("https://new.example/mcp")
        config = {"mcpServers": {"old": {"command": "y"}}, "other": "keep"}
        plan = [("new", "add", e)]
        result = apply_import(config, plan, force=False)
        assert result["other"] == "keep"
        assert "old" in result["mcpServers"]

    def test_does_not_mutate_original(self):
        e = _entry("https://a.example/mcp")
        config = {"mcpServers": {}}
        plan = [("a", "add", e)]
        apply_import(config, plan, force=False)
        assert "a" not in config["mcpServers"]

    def test_creates_mcpservers_if_missing(self):
        e = _entry("https://a.example/mcp")
        config = {"other": "value"}
        plan = [("a", "add", e)]
        result = apply_import(config, plan, force=False)
        assert "a" in result["mcpServers"]
