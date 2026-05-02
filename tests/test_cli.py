import json
import os
from importlib.metadata import version as pkg_version

import pytest
import typer
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


class TestVersion:
    def test_version(self):
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert result.output.strip() == pkg_version("cdcasasagi")


class TestDoctor:
    def test_all_pass(self, config_env):
        config_file, fake_proxy = config_env
        config_file.write_text('{"mcpServers": {}}')
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0
        assert result.output.count("[PASS]") == 3
        assert "[FAIL]" not in result.output
        assert "All checks passed." in result.output

    def test_mcp_proxy_missing(self, config_env, monkeypatch):
        config_file, _ = config_env
        config_file.write_text('{"mcpServers": {}}')
        # Point sys.executable to a dir without mcp-proxy
        monkeypatch.setattr(
            "cdcasasagi.mcp_proxy.sys.executable", "/nonexistent/bin/python"
        )
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 1
        assert "[FAIL] mcp-proxy:" in result.output
        # Other checks still run
        assert result.output.count("[PASS]") == 2

    def test_config_file_missing(self, config_env):
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 1
        assert "[FAIL] Config file:" in result.output
        assert "[PASS] mcp-proxy:" in result.output

    def test_config_dir_not_writable(self, config_env, monkeypatch):
        config_file, _ = config_env
        config_file.write_text('{"mcpServers": {}}')
        original_access = os.access

        def fake_access(path, mode, **kwargs):
            if mode == os.W_OK:
                return False
            return original_access(path, mode, **kwargs)

        monkeypatch.setattr("os.access", fake_access)
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 1
        assert "[FAIL] Config directory:" in result.output
        assert "not writable" in result.output

    def test_all_checks_run_even_with_failures(self, config_env, monkeypatch):
        # mcp-proxy missing + config file missing
        monkeypatch.setattr(
            "cdcasasagi.mcp_proxy.sys.executable", "/nonexistent/bin/python"
        )
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 1
        # All 3 check lines present
        assert "mcp-proxy:" in result.output
        assert "Config file:" in result.output
        assert "Config directory:" in result.output

    def _setup_windows_doctor(self, monkeypatch, tmp_path, with_msix_candidate=True):
        monkeypatch.delenv("CLAUDE_DESKTOP_CONFIG", raising=False)
        appdata = tmp_path / "appdata"
        local = tmp_path / "local"
        appdata.mkdir()
        local.mkdir()
        appdata_cfg_dir = appdata / "Claude"
        appdata_cfg_dir.mkdir()
        appdata_cfg = appdata_cfg_dir / "claude_desktop_config.json"
        appdata_cfg.write_text('{"mcpServers": {}}')
        monkeypatch.setenv("APPDATA", str(appdata))
        monkeypatch.setenv("LOCALAPPDATA", str(local))
        monkeypatch.setattr("platform.system", lambda: "Windows")

        msix_cfg = None
        if with_msix_candidate:
            claude_dir = (
                local
                / "Packages"
                / "Claude_pzs8sxrjxfjjc"
                / "LocalCache"
                / "Roaming"
                / "Claude"
            )
            claude_dir.mkdir(parents=True)
            msix_cfg = claude_dir / "claude_desktop_config.json"

        fake_proxy = tmp_path / "bin" / "mcp-proxy"
        fake_proxy.parent.mkdir()
        fake_proxy.touch()
        fake_python = tmp_path / "bin" / "python"
        monkeypatch.setattr("cdcasasagi.mcp_proxy.sys.executable", str(fake_python))

        return appdata_cfg, msix_cfg

    def test_msix_warn_when_env_pins_appdata_path(self, monkeypatch, tmp_path):
        """User explicitly set CLAUDE_DESKTOP_CONFIG to %APPDATA%\\... despite
        an MSIX candidate existing — the WARN row should still fire.
        """
        appdata_cfg, msix_cfg = self._setup_windows_doctor(monkeypatch, tmp_path)
        monkeypatch.setenv("CLAUDE_DESKTOP_CONFIG", str(appdata_cfg))
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0
        assert "[WARN] Claude Desktop MSIX path:" in result.output
        assert str(msix_cfg) in result.output
        assert "CLAUDE_DESKTOP_CONFIG=" in result.output

    def test_msix_no_warn_when_env_var_set_to_msix(self, monkeypatch, tmp_path):
        _, msix_cfg = self._setup_windows_doctor(monkeypatch, tmp_path)
        msix_cfg.write_text('{"mcpServers": {}}')
        monkeypatch.setenv("CLAUDE_DESKTOP_CONFIG", str(msix_cfg))
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0
        assert "[WARN]" not in result.output

    def test_msix_auto_selected_no_warn(self, monkeypatch, tmp_path):
        """Single MSIX candidate -> config_path() auto-selects it, no WARN."""
        _, msix_cfg = self._setup_windows_doctor(monkeypatch, tmp_path)
        msix_cfg.write_text('{"mcpServers": {}}')
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0
        assert "[WARN]" not in result.output
        assert str(msix_cfg) in result.output

    def test_msix_no_warn_when_no_candidates(self, monkeypatch, tmp_path):
        self._setup_windows_doctor(monkeypatch, tmp_path, with_msix_candidate=False)
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0
        assert "[WARN]" not in result.output

    def test_doctor_exits_zero_with_only_warnings(self, monkeypatch, tmp_path):
        appdata_cfg, _ = self._setup_windows_doctor(monkeypatch, tmp_path)
        monkeypatch.setenv("CLAUDE_DESKTOP_CONFIG", str(appdata_cfg))
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0
        assert "[FAIL]" not in result.output
        assert "All checks passed (1 warning)." in result.output

    def test_orphan_no_warn_when_file_absent(self, monkeypatch, tmp_path):
        appdata_cfg, msix_cfg = self._setup_windows_doctor(monkeypatch, tmp_path)
        msix_cfg.write_text('{"mcpServers": {}}')
        appdata_cfg.unlink()
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0
        assert "Orphan APPDATA config" not in result.output

    def test_orphan_warn_lists_entries_and_active_path(self, monkeypatch, tmp_path):
        appdata_cfg, msix_cfg = self._setup_windows_doctor(monkeypatch, tmp_path)
        msix_cfg.write_text('{"mcpServers": {}}')
        appdata_cfg.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "notion": {"command": "x", "args": []},
                        "github": {"command": "y", "args": []},
                    }
                }
            )
        )
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0
        assert "[WARN] Orphan APPDATA config:" in result.output
        assert str(appdata_cfg) in result.output
        assert "github, notion" in result.output
        assert str(msix_cfg) in result.output

    def test_orphan_no_warn_when_mcp_servers_empty(self, monkeypatch, tmp_path):
        appdata_cfg, msix_cfg = self._setup_windows_doctor(monkeypatch, tmp_path)
        msix_cfg.write_text('{"mcpServers": {}}')
        appdata_cfg.write_text('{"mcpServers": {}}')
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0
        assert "Orphan APPDATA config" not in result.output

    def test_orphan_no_warn_when_mcp_servers_key_missing(self, monkeypatch, tmp_path):
        appdata_cfg, msix_cfg = self._setup_windows_doctor(monkeypatch, tmp_path)
        msix_cfg.write_text('{"mcpServers": {}}')
        appdata_cfg.write_text("{}")
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0
        assert "Orphan APPDATA config" not in result.output

    def test_orphan_warn_when_unreadable(self, monkeypatch, tmp_path):
        appdata_cfg, msix_cfg = self._setup_windows_doctor(monkeypatch, tmp_path)
        msix_cfg.write_text('{"mcpServers": {}}')
        appdata_cfg.write_text("not json {")
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0
        assert "[WARN] Orphan APPDATA config:" in result.output
        assert "unreadable" in result.output
        assert str(appdata_cfg) in result.output

    def test_orphan_warn_when_read_raises_oserror(self, monkeypatch, tmp_path):
        appdata_cfg, msix_cfg = self._setup_windows_doctor(monkeypatch, tmp_path)
        msix_cfg.write_text('{"mcpServers": {}}')
        appdata_cfg.write_text('{"mcpServers": {}}')

        original_read_text = type(appdata_cfg).read_text

        def fake_read_text(self, *args, **kwargs):
            if self == appdata_cfg:
                raise PermissionError("locked")
            return original_read_text(self, *args, **kwargs)

        monkeypatch.setattr(type(appdata_cfg), "read_text", fake_read_text)
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0
        assert "[WARN] Orphan APPDATA config:" in result.output
        assert "unreadable" in result.output

    def test_orphan_no_warn_when_non_msix_install(self, monkeypatch, tmp_path):
        appdata_cfg, _ = self._setup_windows_doctor(
            monkeypatch, tmp_path, with_msix_candidate=False
        )
        appdata_cfg.write_text(
            json.dumps({"mcpServers": {"notion": {"command": "x", "args": []}}})
        )
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0
        assert "Orphan APPDATA config" not in result.output

    def test_orphan_no_warn_when_env_pins_appdata(self, monkeypatch, tmp_path):
        appdata_cfg, _ = self._setup_windows_doctor(monkeypatch, tmp_path)
        appdata_cfg.write_text(
            json.dumps({"mcpServers": {"notion": {"command": "x", "args": []}}})
        )
        monkeypatch.setenv("CLAUDE_DESKTOP_CONFIG", str(appdata_cfg))
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0
        assert "Orphan APPDATA config" not in result.output


class TestAmbiguousMsixConfig:
    """`config_path()` raises AmbiguousConfigError when multiple MSIX packages
    each have a config file. Verify each command surfaces the error message
    and the doctor still runs the mcp-proxy check.
    """

    def _setup(self, monkeypatch, tmp_path):
        monkeypatch.delenv("CLAUDE_DESKTOP_CONFIG", raising=False)
        appdata = tmp_path / "appdata"
        local = tmp_path / "local"
        appdata.mkdir()
        local.mkdir()
        monkeypatch.setenv("APPDATA", str(appdata))
        monkeypatch.setenv("LOCALAPPDATA", str(local))
        monkeypatch.setattr("platform.system", lambda: "Windows")
        monkeypatch.setattr(
            "cdcasasagi.desktop_config.platform.system", lambda: "Windows"
        )
        cfgs = []
        for pkg in ("Anthropic.ClaudeDesktop_h6f0761", "Claude_pzs8sxrjxfjjc"):
            d = local / "Packages" / pkg / "LocalCache" / "Roaming" / "Claude"
            d.mkdir(parents=True)
            cfg = d / "claude_desktop_config.json"
            cfg.write_text('{"mcpServers": {}}')
            cfgs.append(cfg)
        fake_proxy = tmp_path / "bin" / "mcp-proxy"
        fake_proxy.parent.mkdir()
        fake_proxy.touch()
        fake_python = tmp_path / "bin" / "python"
        monkeypatch.setattr("cdcasasagi.mcp_proxy.sys.executable", str(fake_python))
        return cfgs

    def test_doctor_reports_fail_and_continues(self, monkeypatch, tmp_path):
        cfgs = self._setup(monkeypatch, tmp_path)
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 1
        assert "[FAIL] Config file:" in result.output
        for cfg in cfgs:
            assert str(cfg) in result.output
        assert "CLAUDE_DESKTOP_CONFIG" in result.output
        # mcp-proxy check still ran
        assert "[PASS] mcp-proxy:" in result.output

    def test_add_exits_with_env_var_hint(self, monkeypatch, tmp_path):
        cfgs = self._setup(monkeypatch, tmp_path)
        result = runner.invoke(app, ["add", "https://mcp.notion.com/mcp"])
        assert result.exit_code == 1
        assert "CLAUDE_DESKTOP_CONFIG" in result.output
        for cfg in cfgs:
            assert str(cfg) in result.output

    def test_import_exits_with_env_var_hint(self, monkeypatch, tmp_path):
        cfgs = self._setup(monkeypatch, tmp_path)
        input_file = tmp_path / "servers.jsonl"
        input_file.write_text('{"url": "https://mcp.notion.com/mcp"}\n')
        result = runner.invoke(app, ["import", str(input_file)])
        assert result.exit_code == 1
        assert "CLAUDE_DESKTOP_CONFIG" in result.output
        for cfg in cfgs:
            assert str(cfg) in result.output


class TestList:
    def test_lists_entries_alphabetically(self, config_env):
        config_file, fake_proxy = config_env
        config_file.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "notion": {
                            "command": str(fake_proxy),
                            "args": [
                                "--transport",
                                "streamablehttp",
                                "https://mcp.notion.com/mcp",
                            ],
                        },
                        "developers": {
                            "command": str(fake_proxy),
                            "args": [
                                "--transport",
                                "streamablehttp",
                                "https://developers.openai.com/mcp",
                            ],
                        },
                    }
                }
            )
        )
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "developers" in result.output
        assert "notion" in result.output
        assert "https://mcp.notion.com/mcp" in result.output
        assert "https://developers.openai.com/mcp" in result.output
        # alphabetical: developers before notion
        assert result.output.index("developers") < result.output.index("notion")
        assert f"Target: {config_file}" in result.output

    def test_empty_servers(self, config_env):
        config_file, _ = config_env
        config_file.write_text('{"mcpServers": {}}')
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "No mcp-proxy MCP servers configured." in result.output
        assert f"Target: {config_file}" in result.output

    def test_no_config_file(self, config_env):
        config_file, _ = config_env
        assert not config_file.exists()
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "No mcp-proxy MCP servers configured." in result.output

    def test_filters_non_mcp_proxy_entries(self, config_env):
        config_file, fake_proxy = config_env
        config_file.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "notion": {
                            "command": str(fake_proxy),
                            "args": [
                                "--transport",
                                "streamablehttp",
                                "https://mcp.notion.com/mcp",
                            ],
                        },
                        "other": {
                            "command": "/usr/bin/some-other-tool",
                            "args": ["--whatever"],
                        },
                    }
                }
            )
        )
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "notion" in result.output
        assert "https://mcp.notion.com/mcp" in result.output
        assert "other" not in result.output
        assert "some-other-tool" not in result.output

    def test_skips_malformed_args(self, config_env):
        config_file, fake_proxy = config_env
        config_file.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "broken": {
                            "command": str(fake_proxy),
                            "args": [],
                        },
                        "wrong-flag": {
                            "command": str(fake_proxy),
                            "args": ["--other", "x", "https://example.com/mcp"],
                        },
                        "ok": {
                            "command": str(fake_proxy),
                            "args": [
                                "--transport",
                                "streamablehttp",
                                "https://example.com/mcp",
                            ],
                        },
                    }
                }
            )
        )
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "ok" in result.output
        assert "https://example.com/mcp" in result.output
        assert "broken" not in result.output
        assert "wrong-flag" not in result.output

    def test_corrupt_config(self, config_env):
        config_file, _ = config_env
        config_file.write_text("not json at all")
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 1
        assert "Failed to parse JSON config file" in result.output


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

    def test_duplicate_url_different_name(self, config_env):
        config_file, fake_proxy = config_env
        entry = {
            "command": str(fake_proxy),
            "args": [
                "--transport",
                "streamablehttp",
                "https://mcp.notion.com/mcp",
            ],
        }
        config_file.write_text(json.dumps({"mcpServers": {"notion": entry}}))
        result = runner.invoke(
            app, ["add", "https://mcp.notion.com/mcp", "--name", "my-notion"]
        )
        assert result.exit_code == 1
        assert "already configured" in result.output
        assert '"notion"' in result.output
        assert "--force" in result.output

    def test_duplicate_url_with_force(self, config_env):
        config_file, fake_proxy = config_env
        entry = {
            "command": str(fake_proxy),
            "args": [
                "--transport",
                "streamablehttp",
                "https://mcp.notion.com/mcp",
            ],
        }
        config_file.write_text(json.dumps({"mcpServers": {"notion": entry}}))
        result = runner.invoke(
            app,
            [
                "add",
                "https://mcp.notion.com/mcp",
                "--name",
                "my-notion",
                "--force",
                "--write",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(config_file.read_text())
        assert "my-notion" in data["mcpServers"]
        assert "notion" not in data["mcpServers"]

    def test_force_rename_preview_diff_is_minimal(self, config_env):
        """A rename via --force must only touch the renamed key in the diff,
        not reorder the other entries into the added/removed block.
        """
        config_file, fake_proxy = config_env
        url_a = "https://mcp.notion.com/mcp"
        url_b = "https://developers.openai.com/mcp"
        notion = {
            "command": str(fake_proxy),
            "args": ["--transport", "streamablehttp", url_a],
        }
        openai = {
            "command": str(fake_proxy),
            "args": ["--transport", "streamablehttp", url_b],
        }
        config_file.write_text(
            json.dumps({"mcpServers": {"notion": notion, "openai": openai}})
        )
        result = runner.invoke(app, ["add", url_a, "--name", "my-notion", "--force"])
        assert result.exit_code == 0
        assert '-    "notion":' in result.output
        assert '+    "my-notion":' in result.output
        # The untouched entry must not appear as an add/remove in the diff.
        for line in result.output.splitlines():
            if line.startswith(("+", "-")) and not line.startswith(("+++", "---")):
                assert '"openai"' not in line, line

    def test_duplicate_url_force_removes_all(self, config_env):
        config_file, fake_proxy = config_env
        url = "https://mcp.notion.com/mcp"
        entry = {
            "command": str(fake_proxy),
            "args": ["--transport", "streamablehttp", url],
        }
        config_file.write_text(
            json.dumps(
                {"mcpServers": {"notion-a": entry, "notion-b": entry, "other": {}}}
            )
        )
        result = runner.invoke(
            app, ["add", url, "--name", "notion", "--force", "--write"]
        )
        assert result.exit_code == 0
        data = json.loads(config_file.read_text())
        assert "notion" in data["mcpServers"]
        assert "notion-a" not in data["mcpServers"]
        assert "notion-b" not in data["mcpServers"]
        assert "other" in data["mcpServers"]

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


class TestDelete:
    @staticmethod
    def _managed(command, url):
        return {
            "command": str(command),
            "args": ["--transport", "streamablehttp", url],
        }

    def test_preview_shows_diff(self, config_env):
        config_file, fake_proxy = config_env
        url = "https://mcp.notion.com/mcp"
        config_file.write_text(
            json.dumps({"mcpServers": {"notion": self._managed(fake_proxy, url)}})
        )
        before = config_file.read_text()
        result = runner.invoke(app, ["delete", url])
        assert result.exit_code == 0
        assert f"Target: {config_file}" in result.output
        assert "--- current" in result.output
        assert "+++ proposed" in result.output
        assert '-    "notion"' in result.output
        assert f'Will remove "notion" ({url}).' in result.output
        assert "--write" in result.output
        assert config_file.read_text() == before

    def test_write_removes_entry(self, config_env):
        config_file, fake_proxy = config_env
        notion_url = "https://mcp.notion.com/mcp"
        linear_url = "https://mcp.linear.app/mcp"
        config_file.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "notion": self._managed(fake_proxy, notion_url),
                        "linear": self._managed(fake_proxy, linear_url),
                    },
                    "other": "keep",
                }
            )
        )
        result = runner.invoke(app, ["delete", notion_url, "--write"])
        assert result.exit_code == 0
        data = json.loads(config_file.read_text())
        assert "notion" not in data["mcpServers"]
        assert "linear" in data["mcpServers"]
        assert data["other"] == "keep"
        assert config_file.with_suffix(".json.bak").exists()
        assert f'Removed "notion" ({notion_url}).' in result.output
        assert "Restart Claude Desktop" in result.output

    def test_url_not_found(self, config_env):
        config_file, fake_proxy = config_env
        config_file.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "notion": self._managed(
                            fake_proxy, "https://mcp.notion.com/mcp"
                        )
                    }
                }
            )
        )
        before = config_file.read_text()
        result = runner.invoke(app, ["delete", "https://missing.example.com/mcp"])
        assert result.exit_code == 1
        assert "No cdcasasagi-managed entry found" in result.output
        assert "https://missing.example.com/mcp" in result.output
        assert config_file.read_text() == before

    def test_no_config_file(self, config_env):
        config_file, _ = config_env
        assert not config_file.exists()
        result = runner.invoke(app, ["delete", "https://mcp.notion.com/mcp"])
        assert result.exit_code == 1
        assert "No cdcasasagi-managed entry found" in result.output

    def test_corrupt_config(self, config_env):
        config_file, _ = config_env
        config_file.write_text("not json at all")
        result = runner.invoke(app, ["delete", "https://mcp.notion.com/mcp"])
        assert result.exit_code == 1
        assert "Failed to parse JSON config file" in result.output

    def test_ignores_non_managed_entry_with_matching_url(self, config_env):
        config_file, _ = config_env
        url = "https://mcp.notion.com/mcp"
        config_file.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "custom": {
                            "command": "/usr/bin/some-other-tool",
                            "args": ["--transport", "streamablehttp", url],
                        }
                    }
                }
            )
        )
        before = config_file.read_text()
        result = runner.invoke(app, ["delete", url, "--write"])
        assert result.exit_code == 1
        assert "No cdcasasagi-managed entry found" in result.output
        assert config_file.read_text() == before

    def test_delete_then_revert_restores(self, config_env):
        config_file, fake_proxy = config_env
        notion_url = "https://mcp.notion.com/mcp"
        linear_url = "https://mcp.linear.app/mcp"
        original = {
            "mcpServers": {
                "notion": self._managed(fake_proxy, notion_url),
                "linear": self._managed(fake_proxy, linear_url),
            }
        }
        config_file.write_text(json.dumps(original))
        result = runner.invoke(app, ["delete", notion_url, "--write"])
        assert result.exit_code == 0
        result = runner.invoke(app, ["revert"])
        assert result.exit_code == 0
        data = json.loads(config_file.read_text())
        assert "notion" in data["mcpServers"]
        assert "linear" in data["mcpServers"]


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

    def test_write_from_stdin(self, config_env):
        config_file, _ = config_env
        stdin_data = '{"url": "https://mcp.notion.com/mcp"}\n'
        result = runner.invoke(app, ["import", "-", "--write"], input=stdin_data)
        assert result.exit_code == 0
        assert config_file.exists()
        data = json.loads(config_file.read_text())
        assert "notion" in data["mcpServers"]

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

    def test_url_alias_conflict_without_force_aborts(self, config_env, tmp_path):
        """Same URL under a different name is a conflict; no --force → fail, no write."""
        config_file, fake_proxy = config_env
        entry = {
            "command": str(fake_proxy),
            "args": ["--transport", "streamablehttp", "https://mcp.notion.com/mcp"],
        }
        original = {"mcpServers": {"notion": entry}}
        config_file.write_text(json.dumps(original))
        input_file = tmp_path / "servers.jsonl"
        input_file.write_text(
            '{"url": "https://mcp.notion.com/mcp", "name": "my-notion"}\n'
        )
        result = runner.invoke(app, ["import", str(input_file), "--write"])
        assert result.exit_code == 1
        assert "my-notion" in result.output
        assert '"notion"' in result.output
        assert "--force" in result.output
        assert json.loads(config_file.read_text()) == original

    def test_url_alias_conflict_with_force_replaces(self, config_env, tmp_path):
        """`--force` removes the existing alias and writes under the new name."""
        config_file, fake_proxy = config_env
        entry = {
            "command": str(fake_proxy),
            "args": ["--transport", "streamablehttp", "https://mcp.notion.com/mcp"],
        }
        config_file.write_text(json.dumps({"mcpServers": {"notion": entry}}))
        input_file = tmp_path / "servers.jsonl"
        input_file.write_text(
            '{"url": "https://mcp.notion.com/mcp", "name": "my-notion"}\n'
        )
        result = runner.invoke(app, ["import", str(input_file), "--force", "--write"])
        assert result.exit_code == 0
        data = json.loads(config_file.read_text())
        assert "my-notion" in data["mcpServers"]
        assert "notion" not in data["mcpServers"]

    def test_same_name_conflict_reports_url_alias_removal(self, config_env, tmp_path):
        """Same-name conflict whose URL is held by another entry: the plan output
        must mention the aliased entry that --force will delete."""
        config_file, fake_proxy = config_env
        notion_url = "https://mcp.notion.com/mcp"
        other_url = "https://other.example.com/mcp"
        config_file.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "notion": {
                            "command": str(fake_proxy),
                            "args": ["--transport", "streamablehttp", notion_url],
                        },
                        "other": {
                            "command": str(fake_proxy),
                            "args": ["--transport", "streamablehttp", other_url],
                        },
                    }
                }
            )
        )
        # Re-target "notion" to the URL currently held by "other".
        input_file = tmp_path / "servers.jsonl"
        input_file.write_text(f'{{"url": "{other_url}", "name": "notion"}}\n')

        # Preview: warns that "other" would be removed alongside the notion overwrite.
        result = runner.invoke(app, ["import", str(input_file)])
        assert result.exit_code == 1
        assert '"other"' in result.output

        # --force --write: plan announces the removal and config actually loses "other".
        result = runner.invoke(app, ["import", str(input_file), "--force", "--write"])
        assert result.exit_code == 0
        assert 'replaced "other"' in result.output
        data = json.loads(config_file.read_text())
        assert "other" not in data["mcpServers"]
        assert data["mcpServers"]["notion"]["args"][-1] == other_url

    def test_replaces_reflects_serial_apply(self, config_env, tmp_path):
        """Row N's `replaces` is computed against the state after rows 0..N-1 apply.

        Starting from ``{a:url1, b:url2}`` and importing ``a->url2, c->url1``:
        row 1 overwrites ``a`` and removes ``b`` (replaces=["b"]). Row 2 then
        adds ``c`` — by this point ``a`` already holds ``url2``, so ``c`` does
        not actually remove anything and must not claim to replace ``a``.
        """
        config_file, fake_proxy = config_env
        url1 = "https://one.example.com/mcp"
        url2 = "https://two.example.com/mcp"
        config_file.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "a": {
                            "command": str(fake_proxy),
                            "args": ["--transport", "streamablehttp", url1],
                        },
                        "b": {
                            "command": str(fake_proxy),
                            "args": ["--transport", "streamablehttp", url2],
                        },
                    }
                }
            )
        )
        input_file = tmp_path / "servers.jsonl"
        input_file.write_text(
            f'{{"url": "{url2}", "name": "a"}}\n{{"url": "{url1}", "name": "c"}}\n'
        )

        # --force preview: "a" replaces "b"; "c" must not claim to replace "a".
        result = runner.invoke(app, ["import", str(input_file), "--force"])
        assert result.exit_code == 0
        assert 'replaces "b"' in result.output
        assert 'replaces "a"' not in result.output

        # --force --write: post-apply, "a" holds url2, "c" holds url1, "b" gone.
        result = runner.invoke(app, ["import", str(input_file), "--force", "--write"])
        assert result.exit_code == 0
        assert 'replaced "a"' not in result.output
        data = json.loads(config_file.read_text())
        assert data["mcpServers"]["a"]["args"][-1] == url2
        assert data["mcpServers"]["c"]["args"][-1] == url1
        assert "b" not in data["mcpServers"]

    def test_url_alias_conflict_all_or_nothing(self, config_env, tmp_path):
        """Mixed input: URL alias conflict + new URL — without --force nothing is written."""
        config_file, fake_proxy = config_env
        entry = {
            "command": str(fake_proxy),
            "args": ["--transport", "streamablehttp", "https://mcp.notion.com/mcp"],
        }
        original = {"mcpServers": {"notion": entry}}
        config_file.write_text(json.dumps(original))
        input_file = tmp_path / "servers.jsonl"
        input_file.write_text(
            '{"url": "https://mcp.notion.com/mcp", "name": "my-notion"}\n'
            '{"url": "https://developers.openai.com/mcp"}\n'
        )
        result = runner.invoke(app, ["import", str(input_file), "--write"])
        assert result.exit_code == 1
        assert json.loads(config_file.read_text()) == original

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


# ------------------------------------------------------------------
# validate command
# ------------------------------------------------------------------


@pytest.fixture()
def validate_env(tmp_path, monkeypatch):
    """Minimal env for validate — no mcp-proxy, no config file."""
    monkeypatch.setenv("CLAUDE_DESKTOP_CONFIG", str(tmp_path / "nonexistent.json"))
    monkeypatch.chdir(tmp_path)


class TestValidate:
    def test_single_entry(self, validate_env, tmp_path):
        f = tmp_path / "servers.jsonl"
        f.write_text('{"url": "https://mcp.notion.com/mcp"}\n')
        result = runner.invoke(app, ["validate-import", str(f)])
        assert result.exit_code == 0
        assert "Valid:" in result.output
        assert "1 entry" in result.output
        assert "mcp.notion.com" in result.output

    def test_multiple_entries(self, validate_env, tmp_path):
        f = tmp_path / "servers.jsonl"
        f.write_text(
            '{"url": "https://mcp.notion.com/mcp"}\n'
            '{"url": "https://mcp.linear.app/mcp"}\n'
        )
        result = runner.invoke(app, ["validate-import", str(f)])
        assert result.exit_code == 0
        assert "2 entries" in result.output
        assert "notion" in result.output
        assert "linear" in result.output

    def test_explicit_name(self, validate_env, tmp_path):
        f = tmp_path / "servers.jsonl"
        f.write_text('{"url": "https://mcp.notion.com/mcp", "name": "my-notion"}\n')
        result = runner.invoke(app, ["validate-import", str(f)])
        assert result.exit_code == 0
        assert "my-notion" in result.output

    def test_explicit_transport(self, validate_env, tmp_path):
        f = tmp_path / "servers.jsonl"
        f.write_text(
            '{"url": "https://example.com/mcp", "name": "test", "transport": "sse"}\n'
        )
        result = runner.invoke(app, ["validate-import", str(f)])
        assert result.exit_code == 0

    def test_blank_lines_skipped(self, validate_env, tmp_path):
        f = tmp_path / "servers.jsonl"
        f.write_text('\n{"url": "https://mcp.notion.com/mcp"}\n\n')
        result = runner.invoke(app, ["validate-import", str(f)])
        assert result.exit_code == 0
        assert "1 entry" in result.output

    def test_does_not_require_mcp_proxy(self, tmp_path, monkeypatch):
        """validate works even when mcp-proxy is not installed."""
        monkeypatch.setenv("CLAUDE_DESKTOP_CONFIG", str(tmp_path / "no.json"))
        # Point sys.executable somewhere with no mcp-proxy
        monkeypatch.setattr(
            "cdcasasagi.mcp_proxy.sys.executable", str(tmp_path / "nope" / "python")
        )
        f = tmp_path / "servers.jsonl"
        f.write_text('{"url": "https://mcp.notion.com/mcp"}\n')
        result = runner.invoke(app, ["validate-import", str(f)])
        assert result.exit_code == 0

    def test_does_not_require_config_file(self, validate_env, tmp_path):
        """validate works even when config file does not exist."""
        f = tmp_path / "servers.jsonl"
        f.write_text('{"url": "https://mcp.notion.com/mcp"}\n')
        result = runner.invoke(app, ["validate-import", str(f)])
        assert result.exit_code == 0

    def test_stdin_validates_without_writing_file(self, validate_env, tmp_path):
        jsonl = '{"url": "https://mcp.notion.com/mcp"}\n'
        result = runner.invoke(app, ["validate-import", "-"], input=jsonl)
        assert result.exit_code == 0
        assert "Valid:" in result.output
        assert "stdin" in result.output
        assert "Saved:" not in result.output
        assert not (tmp_path / "mcp-servers.jsonl").exists()

    def test_stdin_does_not_touch_existing_file(self, validate_env, tmp_path):
        existing = tmp_path / "mcp-servers.jsonl"
        existing.write_text("old content\n", encoding="utf-8")
        jsonl = '{"url": "https://mcp.notion.com/mcp"}\n'
        result = runner.invoke(app, ["validate-import", "-"], input=jsonl)
        assert result.exit_code == 0
        assert existing.read_text(encoding="utf-8") == "old content\n"

    def test_file_input_does_not_save(self, validate_env, tmp_path):
        f = tmp_path / "servers.jsonl"
        f.write_text('{"url": "https://mcp.notion.com/mcp"}\n')
        result = runner.invoke(app, ["validate-import", str(f)])
        assert result.exit_code == 0
        assert not (tmp_path / "mcp-servers.jsonl").exists()
        assert "Saved:" not in result.output

    def test_tty_stdin_blank_line_terminates(self, monkeypatch):
        """TTY stdin stops reading at the first blank line."""
        import io

        from cdcasasagi.cli import _read_stdin_jsonl

        class FakeStdin(io.StringIO):
            def isatty(self):
                return True

        text = (
            '{"url": "https://mcp.notion.com/mcp"}\n'
            '{"url": "https://mcp.linear.app/mcp"}\n'
            "\n"
            # Anything after the blank line must be ignored.
            '{"url": "https://ignored.example.com/mcp"}\n'
        )
        monkeypatch.setattr("cdcasasagi.cli.sys.stdin", FakeStdin(text))
        assert _read_stdin_jsonl() == (
            '{"url": "https://mcp.notion.com/mcp"}\n'
            '{"url": "https://mcp.linear.app/mcp"}\n'
        )

    def test_piped_stdin_reads_to_eof(self, monkeypatch):
        """Non-TTY stdin reads all the way to EOF (blank lines don't stop it)."""
        import io

        from cdcasasagi.cli import _read_stdin_jsonl

        class FakeStdin(io.StringIO):
            def isatty(self):
                return False

        text = (
            '{"url": "https://a.example.com/mcp"}\n'
            "\n"
            '{"url": "https://b.example.com/mcp"}\n'
        )
        monkeypatch.setattr("cdcasasagi.cli.sys.stdin", FakeStdin(text))
        assert _read_stdin_jsonl() == text

    def test_no_color_env_strips_ansi_from_prompt(self, monkeypatch, capsys):
        """NO_COLOR=<non-empty> must suppress ANSI escape codes in the prompt."""
        import io

        from cdcasasagi.cli import _read_stdin_jsonl

        class FakeStdin(io.StringIO):
            def isatty(self):
                return True

        monkeypatch.setenv("NO_COLOR", "1")
        monkeypatch.setattr("cdcasasagi.cli.sys.stdin", FakeStdin(""))
        _read_stdin_jsonl()
        captured = capsys.readouterr()
        assert "\x1b[" not in captured.err
        assert "Paste JSONL" in captured.err

    def test_no_color_empty_string_keeps_color_path(self, monkeypatch):
        """NO_COLOR="" (empty) is treated as unset per the no-color.org spec."""
        import io

        from cdcasasagi.cli import _read_stdin_jsonl

        class FakeStdin(io.StringIO):
            def isatty(self):
                return True

        captured_fg: list = []
        original_secho = typer.secho

        def fake_secho(*args, **kwargs):
            captured_fg.append(kwargs.get("fg"))
            return original_secho(*args, **kwargs)

        monkeypatch.setenv("NO_COLOR", "")
        monkeypatch.setattr("cdcasasagi.cli.typer.secho", fake_secho)
        monkeypatch.setattr("cdcasasagi.cli.sys.stdin", FakeStdin(""))
        _read_stdin_jsonl()
        assert captured_fg == [typer.colors.CYAN]


class TestValidateErrors:
    def test_invalid_jsonl(self, validate_env, tmp_path):
        f = tmp_path / "servers.jsonl"
        f.write_text("not json")
        result = runner.invoke(app, ["validate-import", str(f)])
        assert result.exit_code == 1
        assert "Failed to parse JSON Lines" in result.output

    def test_empty_file(self, validate_env, tmp_path):
        f = tmp_path / "servers.jsonl"
        f.write_text("")
        result = runner.invoke(app, ["validate-import", str(f)])
        assert result.exit_code == 1
        assert "no entries" in result.output

    def test_blank_lines_only(self, validate_env, tmp_path):
        f = tmp_path / "servers.jsonl"
        f.write_text("\n\n\n")
        result = runner.invoke(app, ["validate-import", str(f)])
        assert result.exit_code == 1
        assert "no entries" in result.output

    def test_missing_url(self, validate_env, tmp_path):
        f = tmp_path / "servers.jsonl"
        f.write_text('{"name": "test"}\n')
        result = runner.invoke(app, ["validate-import", str(f)])
        assert result.exit_code == 1
        assert "Invalid:" in result.output
        assert 'entry[0]: missing required key "url"' in result.output

    def test_unknown_keys(self, validate_env, tmp_path):
        f = tmp_path / "servers.jsonl"
        f.write_text('{"url": "https://mcp.notion.com/mcp", "typo": "bad"}\n')
        result = runner.invoke(app, ["validate-import", str(f)])
        assert result.exit_code == 1
        assert "unknown keys" in result.output
        assert "typo" in result.output

    def test_entry_not_object(self, validate_env, tmp_path):
        f = tmp_path / "servers.jsonl"
        f.write_text('"https://mcp.notion.com/mcp"\n')
        result = runner.invoke(app, ["validate-import", str(f)])
        assert result.exit_code == 1
        assert "entry[0]: must be an object" in result.output

    def test_url_not_string(self, validate_env, tmp_path):
        f = tmp_path / "servers.jsonl"
        f.write_text('{"url": 123}\n')
        result = runner.invoke(app, ["validate-import", str(f)])
        assert result.exit_code == 1
        assert '"url" must be a string' in result.output

    def test_name_not_string(self, validate_env, tmp_path):
        f = tmp_path / "servers.jsonl"
        f.write_text('{"url": "https://mcp.notion.com/mcp", "name": 123}\n')
        result = runner.invoke(app, ["validate-import", str(f)])
        assert result.exit_code == 1
        assert '"name" must be a string' in result.output

    def test_multiple_schema_errors(self, validate_env, tmp_path):
        f = tmp_path / "servers.jsonl"
        f.write_text('{"name": "test"}\n{"url": "https://example.com", "bad": "key"}\n')
        result = runner.invoke(app, ["validate-import", str(f)])
        assert result.exit_code == 1
        assert "entry[0]" in result.output
        assert "entry[1]" in result.output

    def test_invalid_url_scheme(self, validate_env, tmp_path):
        f = tmp_path / "servers.jsonl"
        f.write_text('{"url": "ftp://example.com/mcp"}\n')
        result = runner.invoke(app, ["validate-import", str(f)])
        assert result.exit_code == 1
        assert "HTTP(S) URL" in result.output

    def test_name_derivation_failure(self, validate_env, tmp_path):
        f = tmp_path / "servers.jsonl"
        f.write_text('{"url": "https://localhost/mcp"}\n')
        result = runner.invoke(app, ["validate-import", str(f)])
        assert result.exit_code == 1
        assert '"name"' in result.output

    def test_duplicate_names(self, validate_env, tmp_path):
        f = tmp_path / "servers.jsonl"
        f.write_text(
            '{"url": "https://mcp.notion.com/mcp", "name": "test"}\n'
            '{"url": "https://mcp.linear.app/mcp", "name": "test"}\n'
        )
        result = runner.invoke(app, ["validate-import", str(f)])
        assert result.exit_code == 1
        assert 'Duplicate name "test"' in result.output

    def test_duplicate_urls(self, validate_env, tmp_path):
        f = tmp_path / "servers.jsonl"
        f.write_text(
            '{"url": "https://mcp.notion.com/mcp", "name": "a"}\n'
            '{"url": "https://mcp.notion.com/mcp", "name": "b"}\n'
        )
        result = runner.invoke(app, ["validate-import", str(f)])
        assert result.exit_code == 1
        assert "Duplicate url" in result.output

    def test_file_not_found(self, validate_env, tmp_path):
        result = runner.invoke(
            app, ["validate-import", str(tmp_path / "nonexistent.jsonl")]
        )
        assert result.exit_code == 1
        assert "File not found" in result.output

    def test_non_utf8_file(self, validate_env, tmp_path):
        f = tmp_path / "servers.jsonl"
        f.write_bytes(b"\xff\xfe invalid utf-8")
        result = runner.invoke(app, ["validate-import", str(f)])
        assert result.exit_code == 1
        assert "Cannot read file" in result.output

    def test_error_output_format(self, validate_env, tmp_path):
        f = tmp_path / "servers.jsonl"
        f.write_text('{"name": "test"}\n{"url": "ftp://bad.com"}\n')
        result = runner.invoke(app, ["validate-import", str(f)])
        assert result.exit_code == 1
        assert "Invalid:" in result.output
        assert "2 entries" in result.output

    def test_stdin_validation_error_does_not_save(self, validate_env, tmp_path):
        # Schema error: missing required url key.
        result = runner.invoke(
            app, ["validate-import", "-"], input='{"name": "test"}\n'
        )
        assert result.exit_code == 1
        assert not (tmp_path / "mcp-servers.jsonl").exists()
