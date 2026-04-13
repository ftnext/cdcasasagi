from pathlib import Path

from cdcasasagi.output import format_diff, preview_message, revert_message, write_message


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
