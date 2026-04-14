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

    def test_revert_with_corrupted_config(self, config_env):
        config_file, _ = config_env
        config_file.write_text("not json")
        bak = config_file.with_suffix(".json.bak")
        bak.write_text(json.dumps({"mcpServers": {}}))
        result = runner.invoke(app, ["revert"])
        assert result.exit_code == 0
        data = json.loads(config_file.read_text())
        assert data == {"mcpServers": {}}
        assert not bak.exists()

    def test_revert_removes_backup_file(self, config_env):
        config_file, _ = config_env
        original = {"mcpServers": {"old": {"command": "x"}}}
        config_file.write_text(
            json.dumps({"mcpServers": {"old": {"command": "x"}, "notion": {}}})
        )
        bak = config_file.with_suffix(".json.bak")
        bak.write_text(json.dumps(original))
        result = runner.invoke(app, ["revert"])
        assert result.exit_code == 0
        assert not bak.exists()
        assert "Removed:" in result.output


class TestImportPreview:
    def test_preview_basic(self, config_env, tmp_path):
        config_file, _ = config_env
        input_file = tmp_path / "servers.jsonl"
        input_file.write_text(
            '{"url": "https://mcp.notion.com/mcp"}\n'
            '{"url": "https://mcp.linear.app/mcp"}\n'
        )
        result = runner.invoke(app, ["import", str(input_file)])
        assert result.exit_code == 0
        assert "Plan:" in result.output
        assert "notion" in result.output
        assert "linear" in result.output
        assert "--write" in result.output
        assert not config_file.exists()

    def test_preview_explicit_names(self, config_env, tmp_path):
        config_file, _ = config_env
        input_file = tmp_path / "servers.jsonl"
        input_file.write_text(
            '{"url": "https://mcp.notion.com/mcp", "name": "my-notion"}\n'
        )
        result = runner.invoke(app, ["import", str(input_file)])
        assert result.exit_code == 0
        assert "my-notion" in result.output

    def test_preview_per_entry_transport(self, config_env, tmp_path):
        config_file, fake_proxy = config_env
        input_file = tmp_path / "servers.jsonl"
        input_file.write_text(
            '{"url": "https://mcp.notion.com/mcp", "transport": "sse"}\n'
        )
        result = runner.invoke(app, ["import", str(input_file), "--write"])
        assert result.exit_code == 0
        data = json.loads(config_file.read_text())
        assert data["mcpServers"]["notion"]["args"][1] == "sse"

    def test_preview_verbose(self, config_env, tmp_path):
        config_file, _ = config_env
        input_file = tmp_path / "servers.jsonl"
        input_file.write_text('{"url": "https://mcp.notion.com/mcp"}\n')
        result = runner.invoke(app, ["import", str(input_file), "--verbose"])
        assert result.exit_code == 0
        assert "proposed" in result.output

    def test_preview_from_stdin(self, config_env):
        config_file, _ = config_env
        stdin_data = '{"url": "https://mcp.notion.com/mcp"}\n'
        result = runner.invoke(app, ["import", "-"], input=stdin_data)
        assert result.exit_code == 0
        assert "notion" in result.output
        assert "stdin" in result.output

    def test_blank_lines_ignored(self, config_env, tmp_path):
        config_file, _ = config_env
        input_file = tmp_path / "servers.jsonl"
        input_file.write_text(
            "\n"
            '{"url": "https://mcp.notion.com/mcp"}\n'
            "\n"
            '{"url": "https://mcp.linear.app/mcp"}\n'
            "\n"
        )
        result = runner.invoke(app, ["import", str(input_file)])
        assert result.exit_code == 0
        assert "notion" in result.output
        assert "linear" in result.output


class TestImportWrite:
    def test_write_creates_file(self, config_env, tmp_path):
        config_file, fake_proxy = config_env
        input_file = tmp_path / "servers.jsonl"
        input_file.write_text(
            '{"url": "https://mcp.notion.com/mcp"}\n'
            '{"url": "https://developers.openai.com/mcp"}\n'
        )
        result = runner.invoke(app, ["import", str(input_file), "--write"])
        assert result.exit_code == 0
        assert config_file.exists()
        data = json.loads(config_file.read_text())
        assert "notion" in data["mcpServers"]
        assert "developers" in data["mcpServers"]
        assert "Restart Claude Desktop" in result.output

    def test_write_creates_backup(self, config_env, tmp_path):
        config_file, _ = config_env
        config_file.write_text(json.dumps({"mcpServers": {}}))
        input_file = tmp_path / "servers.jsonl"
        input_file.write_text('{"url": "https://mcp.notion.com/mcp"}\n')
        result = runner.invoke(app, ["import", str(input_file), "--write"])
        assert result.exit_code == 0
        assert config_file.with_suffix(".json.bak").exists()

    def test_write_preserves_existing(self, config_env, tmp_path):
        config_file, _ = config_env
        config_file.write_text(
            json.dumps({"mcpServers": {"old": {"command": "y"}}, "other": "keep"})
        )
        input_file = tmp_path / "servers.jsonl"
        input_file.write_text('{"url": "https://mcp.notion.com/mcp"}\n')
        result = runner.invoke(app, ["import", str(input_file), "--write"])
        assert result.exit_code == 0
        data = json.loads(config_file.read_text())
        assert "old" in data["mcpServers"]
        assert "notion" in data["mcpServers"]
        assert data["other"] == "keep"

    def test_write_all_identical_no_write(self, config_env, tmp_path):
        config_file, fake_proxy = config_env
        entry = {
            "command": str(fake_proxy),
            "args": ["--transport", "streamablehttp", "https://mcp.notion.com/mcp"],
        }
        config_file.write_text(json.dumps({"mcpServers": {"notion": entry}}))
        input_file = tmp_path / "servers.jsonl"
        input_file.write_text('{"url": "https://mcp.notion.com/mcp"}\n')
        result = runner.invoke(app, ["import", str(input_file), "--write"])
        assert result.exit_code == 0
        assert "No changes needed" in result.output


class TestImportConflicts:
    def test_conflict_without_force_aborts(self, config_env, tmp_path):
        config_file, _ = config_env
        config_file.write_text(
            json.dumps({"mcpServers": {"notion": {"command": "old"}}})
        )
        input_file = tmp_path / "servers.jsonl"
        input_file.write_text('{"url": "https://mcp.notion.com/mcp"}\n')
        result = runner.invoke(app, ["import", str(input_file)])
        assert result.exit_code == 1
        assert "name conflict" in result.output
        assert "--force" in result.output

    def test_conflict_with_force_overwrites(self, config_env, tmp_path):
        config_file, fake_proxy = config_env
        config_file.write_text(
            json.dumps({"mcpServers": {"notion": {"command": "old"}}})
        )
        input_file = tmp_path / "servers.jsonl"
        input_file.write_text('{"url": "https://mcp.notion.com/mcp"}\n')
        result = runner.invoke(app, ["import", str(input_file), "--force", "--write"])
        assert result.exit_code == 0
        data = json.loads(config_file.read_text())
        assert data["mcpServers"]["notion"]["command"] == str(fake_proxy)

    def test_identical_never_conflicts(self, config_env, tmp_path):
        config_file, fake_proxy = config_env
        entry = {
            "command": str(fake_proxy),
            "args": ["--transport", "streamablehttp", "https://mcp.notion.com/mcp"],
        }
        config_file.write_text(json.dumps({"mcpServers": {"notion": entry}}))
        input_file = tmp_path / "servers.jsonl"
        input_file.write_text('{"url": "https://mcp.notion.com/mcp"}\n')
        result = runner.invoke(app, ["import", str(input_file)])
        assert result.exit_code == 0
        assert "identical" in result.output


class TestImportValidationErrors:
    def test_invalid_jsonl(self, config_env, tmp_path):
        input_file = tmp_path / "servers.jsonl"
        input_file.write_text("not json")
        result = runner.invoke(app, ["import", str(input_file)])
        assert result.exit_code == 1
        assert "Failed to parse JSON Lines" in result.output

    def test_invalid_jsonl_line(self, config_env, tmp_path):
        input_file = tmp_path / "servers.jsonl"
        input_file.write_text('{"url": "https://mcp.notion.com/mcp"}\nnot json\n')
        result = runner.invoke(app, ["import", str(input_file)])
        assert result.exit_code == 1
        assert "Failed to parse JSON Lines" in result.output
        assert "line 2" in result.output

    def test_invalid_line_after_blank_reports_correct_line_number(
        self, config_env, tmp_path
    ):
        input_file = tmp_path / "servers.jsonl"
        input_file.write_text('{"url": "https://mcp.notion.com/mcp"}\n\nnot json\n')
        result = runner.invoke(app, ["import", str(input_file)])
        assert result.exit_code == 1
        assert "line 3" in result.output

    def test_empty_input(self, config_env, tmp_path):
        input_file = tmp_path / "servers.jsonl"
        input_file.write_text("")
        result = runner.invoke(app, ["import", str(input_file)])
        assert result.exit_code == 1
        assert "no entries" in result.output

    def test_blank_lines_only(self, config_env, tmp_path):
        input_file = tmp_path / "servers.jsonl"
        input_file.write_text("\n\n\n")
        result = runner.invoke(app, ["import", str(input_file)])
        assert result.exit_code == 1
        assert "no entries" in result.output

    def test_missing_url(self, config_env, tmp_path):
        input_file = tmp_path / "servers.jsonl"
        input_file.write_text('{"name": "test"}\n')
        result = runner.invoke(app, ["import", str(input_file)])
        assert result.exit_code == 1
        assert 'entry[0]: missing required key "url"' in result.output

    def test_unknown_keys(self, config_env, tmp_path):
        input_file = tmp_path / "servers.jsonl"
        input_file.write_text('{"url": "https://mcp.notion.com/mcp", "typo": "bad"}\n')
        result = runner.invoke(app, ["import", str(input_file)])
        assert result.exit_code == 1
        assert "unknown keys" in result.output
        assert "typo" in result.output

    def test_multiple_schema_errors(self, config_env, tmp_path):
        input_file = tmp_path / "servers.jsonl"
        input_file.write_text(
            '{"name": "test"}\n{"url": "https://example.com", "bad": "key"}\n'
        )
        result = runner.invoke(app, ["import", str(input_file)])
        assert result.exit_code == 1
        assert "entry[0]" in result.output
        assert "entry[1]" in result.output

    def test_duplicate_names(self, config_env, tmp_path):
        input_file = tmp_path / "servers.jsonl"
        input_file.write_text(
            '{"url": "https://mcp.notion.com/mcp", "name": "test"}\n'
            '{"url": "https://mcp.linear.app/mcp", "name": "test"}\n'
        )
        result = runner.invoke(app, ["import", str(input_file)])
        assert result.exit_code == 1
        assert 'Duplicate name "test"' in result.output

    def test_duplicate_urls(self, config_env, tmp_path):
        input_file = tmp_path / "servers.jsonl"
        input_file.write_text(
            '{"url": "https://mcp.notion.com/mcp", "name": "a"}\n'
            '{"url": "https://mcp.notion.com/mcp", "name": "b"}\n'
        )
        result = runner.invoke(app, ["import", str(input_file)])
        assert result.exit_code == 1
        assert "Duplicate url" in result.output

    def test_invalid_url_scheme(self, config_env, tmp_path):
        input_file = tmp_path / "servers.jsonl"
        input_file.write_text('{"url": "ftp://example.com/mcp"}\n')
        result = runner.invoke(app, ["import", str(input_file)])
        assert result.exit_code == 1
        assert "HTTP(S) URL" in result.output

    def test_name_derivation_failure(self, config_env, tmp_path):
        input_file = tmp_path / "servers.jsonl"
        input_file.write_text('{"url": "https://localhost/mcp"}\n')
        result = runner.invoke(app, ["import", str(input_file)])
        assert result.exit_code == 1
        assert '"name"' in result.output

    def test_file_not_found(self, config_env, tmp_path):
        result = runner.invoke(app, ["import", str(tmp_path / "nonexistent.jsonl")])
        assert result.exit_code == 1
        assert "File not found" in result.output

    def test_invalid_config_json(self, config_env, tmp_path):
        config_file, _ = config_env
        config_file.write_text("not json")
        input_file = tmp_path / "servers.jsonl"
        input_file.write_text('{"url": "https://mcp.notion.com/mcp"}\n')
        result = runner.invoke(app, ["import", str(input_file)])
        assert result.exit_code == 1
        assert "Failed to parse JSON config" in result.output

    def test_entry_not_object(self, config_env, tmp_path):
        input_file = tmp_path / "servers.jsonl"
        input_file.write_text('"https://mcp.notion.com/mcp"\n')
        result = runner.invoke(app, ["import", str(input_file)])
        assert result.exit_code == 1
        assert "entry[0]: must be an object" in result.output

    def test_non_utf8_file(self, config_env, tmp_path):
        input_file = tmp_path / "servers.jsonl"
        input_file.write_bytes(b"\xff\xfe invalid utf-8")
        result = runner.invoke(app, ["import", str(input_file)])
        assert result.exit_code == 1
        assert "Cannot read file" in result.output
