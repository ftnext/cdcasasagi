from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any

from . import desktop_config


def format_diff(
    current_config: dict[str, Any] | None,
    proposed_config: dict[str, Any],
    *,
    from_label: str = "current",
    to_label: str = "proposed",
) -> str:
    if current_config is None:
        current_lines: list[str] = []
        header = f"--- (file does not exist; will be created)\n+++ {to_label}\n"
    else:
        current_text = desktop_config.serialize_config(current_config)
        current_lines = current_text.splitlines(keepends=True)
        header = ""

    proposed_text = desktop_config.serialize_config(proposed_config)
    proposed_lines = proposed_text.splitlines(keepends=True)

    diff = difflib.unified_diff(
        current_lines,
        proposed_lines,
        fromfile=from_label,
        tofile=to_label,
    )
    if header:
        diff_lines = list(diff)
        # Drop the default --- / +++ lines from unified_diff
        content = "".join(
            line
            for line in diff_lines
            if not line.startswith("--- ") and not line.startswith("+++ ")
        )
        return header + content
    return "".join(diff)


def preview_message(
    name: str,
    name_was_derived: bool,
    config_path: Path,
    diff_text: str,
) -> str:
    lines: list[str] = []
    if name_was_derived:
        lines.append(f'Derived name from URL: "{name}"')
    lines.append(f"Target: {config_path}")
    lines.append("")
    lines.append(diff_text.rstrip())
    lines.append("")
    lines.append("This is a preview. Re-run with --write to apply.")
    lines.append("To use a different name: --name <your-name>")
    return "\n".join(lines)


def revert_message(
    config_path: Path,
    diff_text: str,
) -> str:
    lines: list[str] = []
    lines.append(f"Reverted: {config_path}")
    backup = config_path.with_suffix(config_path.suffix + ".bak")
    lines.append(f"Removed:  {backup}")
    if diff_text.strip():
        lines.append("")
        lines.append(diff_text.rstrip())
    lines.append("")
    lines.append("Reverted to backup. Restart Claude Desktop to take effect.")
    return "\n".join(lines)


def write_message(
    name: str,
    name_was_derived: bool,
    config_path: Path,
    file_existed: bool,
) -> str:
    lines: list[str] = []
    if name_was_derived:
        lines.append(f'Derived name from URL: "{name}"')
    if file_existed:
        backup = config_path.with_suffix(config_path.suffix + ".bak")
        lines.append(f"Backup: {backup}")
    lines.append(f"Wrote:  {config_path}")
    lines.append("")
    lines.append(f'Added "{name}". Restart Claude Desktop to take effect.')
    return "\n".join(lines)
