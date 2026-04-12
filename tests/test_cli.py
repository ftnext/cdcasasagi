import json

import pytest
from typer.testing import CliRunner

from cdcasasagi.cli import app

runner = CliRunner()


@pytest.fixture()
def config_env(tmp_path, monkeypatch):
    config_file = tmp_path / "claude_desktop_config.json"
    monkeypatch.setenv("CLAUDE_DESKTOP_CONFIG", str(config_file))

    fake_proxy = tmp_path / "bin" / "mcp-proxy"
    fake_proxy.parent.mkdir()
    fake_proxy.touch()
    fake_python = tmp_path / "bin" / "python"

    monkeypatch.setattr("cdcasasagi.mcp_proxy.sys.executable", str(fake_python))
    return config_file, fake_proxy


class TestAddPreview:
    def test_preview_derived_name(self, config_env):
        config_file, _ = config_env
        result = runner.invoke(app, ["add", "https://mcp.notion.com/mcp"])
        assert result.exit_code == 0
        assert 'Derived name from URL: "notion"' in result.output
        assert "--- current" in result.output or "(file does not exist" in result.output
        assert "--write" in result.output
        assert not config_file.exists()

    def test_preview_explicit_name(self, config_env):
        config_file, _ = config_env
        result = runner.invoke(
            app, ["add", "https://mcp.notion.com/mcp", "--name", "my-notion"]
        )
        assert result.exit_code == 0
        assert "Derived name" not in result.output
        assert "my-notion" in result.output

    def test_preview_with_existing_config(self, config_env):
        config_file, _ = config_env
        config_file.write_text(json.dumps({"mcpServers": {"old": {"command": "x"}}}))
        result = runner.invoke(app, ["add", "https://mcp.notion.com/mcp"])
        assert result.exit_code == 0
        assert "notion" in result.output


class TestAddWrite:
    def test_write_creates_file(self, config_env):
        config_file, fake_proxy = config_env
        result = runner.invoke(app, ["add", "https://mcp.notion.com/mcp", "--write"])
        assert result.exit_code == 0
        assert config_file.exists()
        data = json.loads(config_file.read_text())
        assert "notion" in data["mcpServers"]
        assert data["mcpServers"]["notion"]["command"] == str(fake_proxy)
        assert "Restart Claude Desktop" in result.output

    def test_write_creates_backup(self, config_env):
        config_file, _ = config_env
        config_file.write_text(json.dumps({"mcpServers": {}}))
        result = runner.invoke(app, ["add", "https://mcp.notion.com/mcp", "--write"])
        assert result.exit_code == 0
        assert config_file.with_suffix(".json.bak").exists()

    def test_write_preserves_existing_entries(self, config_env):
        config_file, _ = config_env
        config_file.write_text(
            json.dumps({"mcpServers": {"old": {"command": "y"}}, "other": "keep"})
        )
        result = runner.invoke(app, ["add", "https://mcp.notion.com/mcp", "--write"])
        assert result.exit_code == 0
        data = json.loads(config_file.read_text())
        assert "old" in data["mcpServers"]
        assert "notion" in data["mcpServers"]
        assert data["other"] == "keep"


class TestAddErrors:
    def test_invalid_url_scheme(self, config_env):
        result = runner.invoke(app, ["add", "ftp://example.com/mcp"])
        assert result.exit_code == 1

    def test_duplicate_without_force(self, config_env):
        config_file, _ = config_env
        config_file.write_text(json.dumps({"mcpServers": {"notion": {"command": "x"}}}))
        result = runner.invoke(app, ["add", "https://mcp.notion.com/mcp"])
        assert result.exit_code == 1
        assert "--force" in result.output

    def test_duplicate_with_force(self, config_env):
        config_file, _ = config_env
        config_file.write_text(
            json.dumps({"mcpServers": {"notion": {"command": "old"}}})
        )
        result = runner.invoke(
            app, ["add", "https://mcp.notion.com/mcp", "--force", "--write"]
        )
        assert result.exit_code == 0
        data = json.loads(config_file.read_text())
        assert data["mcpServers"]["notion"]["command"] != "old"

    def test_invalid_json_config(self, config_env):
        config_file, _ = config_env
        config_file.write_text("not json")
        result = runner.invoke(app, ["add", "https://mcp.notion.com/mcp"])
        assert result.exit_code == 1

    def test_name_derivation_fails(self, config_env):
        result = runner.invoke(app, ["add", "https://localhost/mcp"])
        assert result.exit_code == 1
        assert "--name" in result.output


class TestRevert:
    def test_revert_after_add(self, config_env):
        config_file, _ = config_env
        config_file.write_text(json.dumps({"mcpServers": {}}))
        runner.invoke(app, ["add", "https://mcp.notion.com/mcp", "--write"])
        result = runner.invoke(app, ["revert"])
        assert result.exit_code == 0
        data = json.loads(config_file.read_text())
        assert "notion" not in data["mcpServers"]
        assert not config_file.with_suffix(".json.bak").exists()
        assert "Reverted" in result.output
        assert "Restart Claude Desktop" in result.output

    def test_revert_shows_diff(self, config_env):
        config_file, _ = config_env
        config_file.write_text(json.dumps({"mcpServers": {}}))
        runner.invoke(app, ["add", "https://mcp.notion.com/mcp", "--write"])
        result = runner.invoke(app, ["revert"])
        assert result.exit_code == 0
        assert "--- before" in result.output
        assert "+++ after" in result.output

    def test_revert_no_backup(self, config_env):
        config_file, _ = config_env
        result = runner.invoke(app, ["revert"])
        assert result.exit_code == 1
        assert "Backup not found" in result.output

    def test_revert_corrupted_backup(self, config_env):
        config_file, _ = config_env
        bak = config_file.with_suffix(".json.bak")
        bak.write_text("not json")
        result = runner.invoke(app, ["revert"])
        assert result.exit_code == 1
        assert "corrupted" in result.output

    def test_revert_removes_backup_file(self, config_env):
        config_file, _ = config_env
        original = {"mcpServers": {"old": {"command": "x"}}}
        config_file.write_text(json.dumps({"mcpServers": {"old": {"command": "x"}, "notion": {}}}))
        bak = config_file.with_suffix(".json.bak")
        bak.write_text(json.dumps(original))
        result = runner.invoke(app, ["revert"])
        assert result.exit_code == 0
        assert not bak.exists()
        assert "Removed:" in result.output
