from pathlib import Path

from cdcasasagi.output import (
    doctor_message,
    format_diff,
    import_preview_message,
    import_write_message,
    list_message,
    preview_message,
    revert_message,
    write_message,
)


def test_format_diff_new_file():
    proposed = {"mcpServers": {"test": {"command": "x", "args": []}}}
    diff = format_diff(None, proposed)
    assert "--- (file does not exist; will be created)" in diff
    assert "+++ proposed" in diff
    assert "-" not in diff.split("\n", 2)[2] or all(
        not line.startswith("-") for line in diff.splitlines()[2:]
    )


def test_format_diff_existing():
    current = {"mcpServers": {}}
    proposed = {"mcpServers": {"test": {"command": "x", "args": []}}}
    diff = format_diff(current, proposed)
    assert '+    "test"' in diff


def test_preview_message_derived_name():
    msg = preview_message("notion", True, Path("/tmp/config.json"), "diff here")
    assert 'Derived name from URL: "notion"' in msg
    assert "Target: /tmp/config.json" in msg
    assert "--write" in msg
    assert "--name" in msg


def test_preview_message_explicit_name():
    msg = preview_message("myname", False, Path("/tmp/config.json"), "diff here")
    assert "Derived name" not in msg


def test_write_message_with_backup():
    msg = write_message("notion", True, Path("/tmp/config.json"), file_existed=True)
    assert "Backup:" in msg
    assert "Wrote:" in msg
    assert "Restart Claude Desktop" in msg


def test_write_message_no_backup():
    msg = write_message("notion", True, Path("/tmp/config.json"), file_existed=False)
    assert "Backup:" not in msg
    assert "Wrote:" in msg


def test_format_diff_custom_labels():
    current = {"mcpServers": {"test": {"command": "x", "args": []}}}
    proposed = {"mcpServers": {}}
    diff = format_diff(current, proposed, from_label="before", to_label="after")
    assert "--- before" in diff
    assert "+++ after" in diff


def test_format_diff_custom_labels_none():
    proposed = {"mcpServers": {"test": {}}}
    diff = format_diff(None, proposed, to_label="after")
    assert "+++ after" in diff
    assert "(file does not exist; will be created)" in diff


def test_revert_message():
    msg = revert_message(Path("/tmp/config.json"), "diff here")
    assert "Reverted: /tmp/config.json" in msg
    assert "Removed:" in msg
    assert "config.json.bak" in msg
    assert "diff here" in msg
    assert "Restart Claude Desktop" in msg


def test_revert_message_empty_diff():
    msg = revert_message(Path("/tmp/config.json"), "")
    assert "Reverted:" in msg
    assert "Restart Claude Desktop" in msg
    # No extra blank line from empty diff
    assert "\n\n\n" not in msg


class TestImportPreviewMessage:
    def test_basic_adds(self):
        plan = [
            ("notion", "add", "https://mcp.notion.com/mcp", []),
            ("linear", "add", "https://mcp.linear.app/mcp", []),
        ]
        msg = import_preview_message(
            Path("/tmp/config.json"), "servers.json", 2, plan, force=False
        )
        assert "Target: /tmp/config.json" in msg
        assert "Source: servers.json (2 entries)" in msg
        assert "Plan:" in msg
        assert "  + notion" in msg
        assert "  + linear" in msg
        assert "2 to add" in msg
        assert "--write" in msg

    def test_singular_entry(self):
        plan = [("notion", "add", "https://mcp.notion.com/mcp", [])]
        msg = import_preview_message(
            Path("/tmp/config.json"), "servers.json", 1, plan, force=False
        )
        assert "(1 entry)" in msg

    def test_with_identical(self):
        plan = [
            ("notion", "add", "https://mcp.notion.com/mcp", []),
            ("linear", "identical", "https://mcp.linear.app/mcp", []),
        ]
        msg = import_preview_message(
            Path("/tmp/config.json"), "servers.json", 2, plan, force=False
        )
        assert "  = linear" in msg
        assert "(identical, skipped)" in msg
        assert "1 to add" in msg
        assert "1 identical" in msg

    def test_conflict_without_force(self):
        plan = [
            ("notion", "add", "https://mcp.notion.com/mcp", []),
            ("existing", "conflict", "https://example.com/mcp", []),
        ]
        msg = import_preview_message(
            Path("/tmp/config.json"), "servers.json", 2, plan, force=False
        )
        assert "  ! existing" in msg
        assert "(name conflict, use --force to overwrite)" in msg
        assert "1 conflict" in msg
        assert "Error:" in msg
        assert "--write" not in msg

    def test_url_alias_conflict_without_force(self):
        plan = [
            ("my-notion", "conflict", "https://mcp.notion.com/mcp", ["notion"]),
        ]
        msg = import_preview_message(
            Path("/tmp/config.json"), "servers.json", 1, plan, force=False
        )
        assert "  ! my-notion" in msg
        assert 'URL already under "notion"' in msg
        assert "--force" in msg
        assert "Error:" in msg

    def test_same_name_conflict_also_drops_aliased_url_without_force(self):
        """Same-name conflict whose URL is already used by another entry also
        warns about the aliased entry that would be removed."""
        plan = [
            ("notion", "conflict", "https://mcp.notion.com/mcp", ["other"]),
        ]
        msg = import_preview_message(
            Path("/tmp/config.json"), "servers.json", 1, plan, force=False
        )
        assert "  ! notion" in msg
        assert 'URL already under "other"' in msg

    def test_conflict_with_force(self):
        plan = [
            ("notion", "add", "https://mcp.notion.com/mcp", []),
            ("existing", "conflict", "https://example.com/mcp", []),
        ]
        msg = import_preview_message(
            Path("/tmp/config.json"), "servers.json", 2, plan, force=True
        )
        assert "  ~ existing" in msg
        assert "(overwrite)" in msg
        assert "1 to overwrite" in msg
        assert "Error:" not in msg
        assert "--write" in msg

    def test_url_alias_conflict_with_force(self):
        plan = [
            ("my-notion", "conflict", "https://mcp.notion.com/mcp", ["notion"]),
        ]
        msg = import_preview_message(
            Path("/tmp/config.json"), "servers.json", 1, plan, force=True
        )
        assert "  ~ my-notion" in msg
        assert 'replaces "notion"' in msg

    def test_same_name_conflict_with_force_lists_all_removed_aliases(self):
        plan = [
            ("notion", "conflict", "https://mcp.notion.com/mcp", ["alt1", "alt2"]),
        ]
        msg = import_preview_message(
            Path("/tmp/config.json"), "servers.json", 1, plan, force=True
        )
        assert "  ~ notion" in msg
        assert 'replaces "alt1", "alt2"' in msg

    def test_verbose_diff(self):
        plan = [("notion", "add", "https://mcp.notion.com/mcp", [])]
        msg = import_preview_message(
            Path("/tmp/config.json"),
            "servers.json",
            1,
            plan,
            force=False,
            verbose_diff="--- current\n+++ proposed\n@@ stuff @@",
        )
        assert "--- current" in msg
        assert "+++ proposed" in msg


class TestImportWriteMessage:
    def test_basic_adds(self):
        plan = [
            ("notion", "add", "https://mcp.notion.com/mcp", []),
            ("linear", "add", "https://mcp.linear.app/mcp", []),
        ]
        msg = import_write_message(
            Path("/tmp/config.json"),
            "servers.json",
            plan,
            force=False,
            file_existed=False,
        )
        assert "Target: /tmp/config.json" in msg
        assert "Source: servers.json" in msg
        assert "Applied:" in msg
        assert "  + notion" in msg
        assert "  + linear" in msg
        assert "Wrote:" in msg
        assert "Restart Claude Desktop" in msg
        assert "Added 2" in msg
        assert "Backup:" not in msg

    def test_with_backup(self):
        plan = [("notion", "add", "https://mcp.notion.com/mcp", [])]
        msg = import_write_message(
            Path("/tmp/config.json"),
            "servers.json",
            plan,
            force=False,
            file_existed=True,
        )
        assert "Backup:" in msg

    def test_with_overwrites(self):
        plan = [
            ("notion", "add", "https://mcp.notion.com/mcp", []),
            ("existing", "conflict", "https://example.com/mcp", []),
        ]
        msg = import_write_message(
            Path("/tmp/config.json"),
            "servers.json",
            plan,
            force=True,
            file_existed=True,
        )
        assert "  + notion" in msg
        assert "  ~ existing" in msg
        assert "Added 1" in msg
        assert "overwrote 1" in msg

    def test_with_url_alias_overwrite(self):
        plan = [
            ("my-notion", "conflict", "https://mcp.notion.com/mcp", ["notion"]),
        ]
        msg = import_write_message(
            Path("/tmp/config.json"),
            "servers.json",
            plan,
            force=True,
            file_existed=True,
        )
        assert "  ~ my-notion" in msg
        assert 'replaced "notion"' in msg

    def test_same_name_conflict_reports_removed_alias(self):
        plan = [
            ("notion", "conflict", "https://mcp.notion.com/mcp", ["other"]),
        ]
        msg = import_write_message(
            Path("/tmp/config.json"),
            "servers.json",
            plan,
            force=True,
            file_existed=True,
        )
        assert "  ~ notion" in msg
        assert 'replaced "other"' in msg

    def test_with_identical(self):
        plan = [
            ("notion", "add", "https://mcp.notion.com/mcp", []),
            ("linear", "identical", "https://mcp.linear.app/mcp", []),
        ]
        msg = import_write_message(
            Path("/tmp/config.json"),
            "servers.json",
            plan,
            force=False,
            file_existed=True,
        )
        assert "  = linear (unchanged)" in msg

    def test_single_entry_word(self):
        plan = [("notion", "add", "https://mcp.notion.com/mcp", [])]
        msg = import_write_message(
            Path("/tmp/config.json"),
            "servers.json",
            plan,
            force=False,
            file_existed=False,
        )
        assert "1 entry" in msg


class TestDoctorMessage:
    def test_all_pass(self):
        results = [
            ("mcp-proxy", "pass", "/usr/local/bin/mcp-proxy"),
            ("Config file", "pass", "/tmp/config.json"),
            ("Config directory", "pass", "/tmp"),
        ]
        msg = doctor_message(results)
        assert msg.count("[PASS]") == 3
        assert "[FAIL]" not in msg
        assert "All checks passed." in msg

    def test_one_failure(self):
        results = [
            ("mcp-proxy", "pass", "/usr/local/bin/mcp-proxy"),
            ("Config file", "fail", "not found: /tmp/config.json"),
            ("Config directory", "pass", "/tmp"),
        ]
        msg = doctor_message(results)
        assert msg.count("[PASS]") == 2
        assert msg.count("[FAIL]") == 1
        assert "1 check failed." in msg

    def test_multiple_failures(self):
        results = [
            ("mcp-proxy", "fail", "not found"),
            ("Config file", "fail", "not found: /tmp/config.json"),
            ("Config directory", "fail", "not writable: /tmp"),
        ]
        msg = doctor_message(results)
        assert msg.count("[FAIL]") == 3
        assert "3 checks failed." in msg

    def test_detail_shown(self):
        results = [
            ("mcp-proxy", "pass", "/path/to/mcp-proxy"),
        ]
        msg = doctor_message(results)
        assert "/path/to/mcp-proxy" in msg

    def test_ascii_only(self):
        results = [
            ("mcp-proxy", "pass", "/usr/local/bin/mcp-proxy"),
            ("Config file", "fail", "not found: /tmp/config.json"),
            ("Config directory", "pass", "/tmp"),
        ]
        msg = doctor_message(results)
        assert msg.isascii()

    def test_warn_renders_warn_tag(self):
        results = [
            ("mcp-proxy", "pass", "/usr/local/bin/mcp-proxy"),
            ("Claude Desktop MSIX path", "warn", "see candidates"),
        ]
        msg = doctor_message(results)
        assert "[WARN] Claude Desktop MSIX path:" in msg

    def test_warn_counted_separately_from_failures(self):
        results = [
            ("mcp-proxy", "pass", "/usr/local/bin/mcp-proxy"),
            ("Config file", "pass", "/tmp/config.json"),
            ("Config directory", "pass", "/tmp"),
            ("Claude Desktop MSIX path", "warn", "see candidates"),
        ]
        msg = doctor_message(results)
        assert "[FAIL]" not in msg
        assert "All checks passed (1 warning)." in msg

    def test_multiple_warnings(self):
        results = [
            ("a", "warn", "x"),
            ("b", "warn", "y"),
        ]
        msg = doctor_message(results)
        assert "All checks passed (2 warnings)." in msg


class TestListMessage:
    def test_empty(self):
        msg = list_message(Path("/tmp/config.json"), [])
        assert "No mcp-proxy MCP servers configured." in msg
        assert "Target: /tmp/config.json" in msg

    def test_formats_entries(self):
        servers = [
            ("notion", "https://mcp.notion.com/mcp"),
            ("openai-developer-docs", "https://developers.openai.com/mcp"),
        ]
        msg = list_message(Path("/tmp/config.json"), servers)
        assert "Target: /tmp/config.json" in msg
        assert "notion" in msg
        assert "https://mcp.notion.com/mcp" in msg
        assert "openai-developer-docs" in msg
        assert "https://developers.openai.com/mcp" in msg

    def test_aligns_names(self):
        servers = [
            ("a", "https://a.example/mcp"),
            ("longer-name", "https://b.example/mcp"),
        ]
        msg = list_message(Path("/tmp/config.json"), servers)
        # Both URLs should appear at the same column thanks to ljust padding.
        lines = [line for line in msg.splitlines() if " : " in line]
        assert len(lines) == 2
        url_columns = {line.index(" : ") for line in lines}
        assert len(url_columns) == 1

    def test_uses_colon_separator(self):
        servers = [("notion", "https://mcp.notion.com/mcp")]
        msg = list_message(Path("/tmp/config.json"), servers)
        assert "notion : https://mcp.notion.com/mcp" in msg

    def test_ascii_only(self):
        servers = [("notion", "https://mcp.notion.com/mcp")]
        msg = list_message(Path("/tmp/config.json"), servers)
        assert msg.isascii()
        empty = list_message(Path("/tmp/config.json"), [])
        assert empty.isascii()
