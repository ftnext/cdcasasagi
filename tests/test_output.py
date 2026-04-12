from pathlib import Path

from cdcasasagi.output import format_diff, preview_message, write_message


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
