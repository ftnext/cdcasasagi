from pathlib import Path

from cdcasasagi.output import (
    format_diff,
    import_preview_message,
    import_write_message,
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
            ("notion", "add", "https://mcp.notion.com/mcp"),
            ("linear", "add", "https://mcp.linear.app/mcp"),
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
        plan = [("notion", "add", "https://mcp.notion.com/mcp")]
        msg = import_preview_message(
            Path("/tmp/config.json"), "servers.json", 1, plan, force=False
        )
        assert "(1 entry)" in msg

    def test_with_identical(self):
        plan = [
            ("notion", "add", "https://mcp.notion.com/mcp"),
            ("linear", "identical", "https://mcp.linear.app/mcp"),
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
            ("notion", "add", "https://mcp.notion.com/mcp"),
            ("existing", "conflict", "https://example.com/mcp"),
        ]
        msg = import_preview_message(
            Path("/tmp/config.json"), "servers.json", 2, plan, force=False
        )
        assert "  ! existing" in msg
        assert "(name conflict, use --force to overwrite)" in msg
        assert "1 conflict" in msg
        assert "Error:" in msg
        assert "--write" not in msg

    def test_conflict_with_force(self):
        plan = [
            ("notion", "add", "https://mcp.notion.com/mcp"),
            ("existing", "conflict", "https://example.com/mcp"),
        ]
        msg = import_preview_message(
            Path("/tmp/config.json"), "servers.json", 2, plan, force=True
        )
        assert "  ~ existing" in msg
        assert "(overwrite)" in msg
        assert "1 to overwrite" in msg
        assert "Error:" not in msg
        assert "--write" in msg

    def test_verbose_diff(self):
        plan = [("notion", "add", "https://mcp.notion.com/mcp")]
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
            ("notion", "add", "https://mcp.notion.com/mcp"),
            ("linear", "add", "https://mcp.linear.app/mcp"),
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
        plan = [("notion", "add", "https://mcp.notion.com/mcp")]
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
            ("notion", "add", "https://mcp.notion.com/mcp"),
            ("existing", "conflict", "https://example.com/mcp"),
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

    def test_with_identical(self):
        plan = [
            ("notion", "add", "https://mcp.notion.com/mcp"),
            ("linear", "identical", "https://mcp.linear.app/mcp"),
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
        plan = [("notion", "add", "https://mcp.notion.com/mcp")]
        msg = import_write_message(
            Path("/tmp/config.json"),
            "servers.json",
            plan,
            force=False,
            file_existed=False,
        )
        assert "1 entry" in msg
