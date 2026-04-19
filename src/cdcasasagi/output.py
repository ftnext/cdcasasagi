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


def delete_preview_message(name: str, config_path: Path, diff_text: str) -> str:
    lines = [
        f"Target: {config_path}",
        "",
        diff_text.rstrip(),
        "",
        f'Will remove "{name}".',
        "This is a preview. Re-run with --write to apply.",
    ]
    return "\n".join(lines)


def delete_write_message(name: str, config_path: Path) -> str:
    backup = config_path.with_suffix(config_path.suffix + ".bak")
    lines = [
        f"Backup: {backup}",
        f"Wrote:  {config_path}",
        "",
        f'Removed "{name}". Restart Claude Desktop to take effect.',
    ]
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


def _format_replaces(replaces: list[str]) -> str:
    return ", ".join(f'"{n}"' for n in replaces)


def import_preview_message(
    config_path: Path,
    source: str,
    entry_count: int,
    plan: list[tuple[str, str, str, list[str]]],
    force: bool,
    verbose_diff: str | None = None,
) -> str:
    lines: list[str] = []
    lines.append(f"Target: {config_path}")
    entry_word = "entry" if entry_count == 1 else "entries"
    lines.append(f"Source: {source} ({entry_count} {entry_word})")
    lines.append("")
    lines.append("Plan:")

    max_name_len = max((len(n) for n, _, _, _ in plan), default=0)

    counts: dict[str, int] = {"add": 0, "identical": 0, "conflict": 0, "overwrite": 0}

    for name, action, url, replaces in plan:
        padded = name.ljust(max_name_len)
        if action == "add":
            lines.append(f"  + {padded}  {url}")
            counts["add"] += 1
        elif action == "identical":
            lines.append(f"  = {padded}  {url}  (identical, skipped)")
            counts["identical"] += 1
        elif action == "conflict":
            if force:
                if replaces:
                    lines.append(
                        f"  ~ {padded}  {url}  "
                        f"(overwrite, replaces {_format_replaces(replaces)})"
                    )
                else:
                    lines.append(f"  ~ {padded}  {url}  (overwrite)")
                counts["overwrite"] += 1
            else:
                if replaces:
                    label = (
                        "URL already under" if len(replaces) == 1 else "URL shared with"
                    )
                    lines.append(
                        f"  ! {padded}  {url}  "
                        f"({label} {_format_replaces(replaces)}, "
                        "use --force to overwrite)"
                    )
                else:
                    lines.append(
                        f"  ! {padded}  {url}  (name conflict, use --force to overwrite)"
                    )
                counts["conflict"] += 1

    lines.append("")

    summary_parts: list[str] = []
    if counts["add"]:
        summary_parts.append(f"{counts['add']} to add")
    if counts["overwrite"]:
        summary_parts.append(f"{counts['overwrite']} to overwrite")
    if counts["identical"]:
        summary_parts.append(f"{counts['identical']} identical")
    if counts["conflict"]:
        summary_parts.append(f"{counts['conflict']} conflict")
    lines.append(f"Summary: {', '.join(summary_parts)}")

    if verbose_diff:
        lines.append("")
        lines.append(verbose_diff.rstrip())

    if counts["conflict"] > 0:
        conflict_word = "conflict" if counts["conflict"] == 1 else "conflicts"
        lines.append(
            f"Error: {counts['conflict']} {conflict_word} without --force. Aborting."
        )
    else:
        lines.append("This is a preview. Re-run with --write to apply.")

    return "\n".join(lines)


def import_write_message(
    config_path: Path,
    source: str,
    plan: list[tuple[str, str, str, list[str]]],
    force: bool,
    file_existed: bool,
) -> str:
    lines: list[str] = []
    lines.append(f"Target: {config_path}")
    lines.append(f"Source: {source}")
    lines.append("")
    lines.append("Applied:")

    add_count = 0
    overwrite_count = 0

    for name, action, _url, replaces in plan:
        if action == "add":
            lines.append(f"  + {name}")
            add_count += 1
        elif action == "identical":
            lines.append(f"  = {name} (unchanged)")
        elif action == "conflict" and force:
            if replaces:
                lines.append(f"  ~ {name} (replaced {_format_replaces(replaces)})")
            else:
                lines.append(f"  ~ {name}")
            overwrite_count += 1

    lines.append("")

    if file_existed:
        backup = config_path.with_suffix(config_path.suffix + ".bak")
        lines.append(f"Backup: {backup}")
    lines.append(f"Wrote:  {config_path}")
    lines.append("")

    total = add_count + overwrite_count
    entry_word = "entry" if total == 1 else "entries"
    parts: list[str] = []
    if add_count:
        parts.append(f"Added {add_count}")
    if overwrite_count:
        parts.append(f"overwrote {overwrite_count}")
    action_text = " and ".join(parts)
    lines.append(f"{action_text} {entry_word}. Restart Claude Desktop to take effect.")

    return "\n".join(lines)


def validate_ok_message(
    source: str,
    entry_count: int,
    resolved: list[tuple[str, str, str]],
) -> str:
    entry_word = "entry" if entry_count == 1 else "entries"
    lines: list[str] = [f"Valid: {source} ({entry_count} {entry_word})", ""]
    max_name = max((len(n) for n, _, _ in resolved), default=0)
    for name, url, _transport in resolved:
        lines.append(f"  {name.ljust(max_name)}  {url}")
    return "\n".join(lines)


def validate_error_message(
    source: str,
    entry_count: int,
    errors: list[str],
) -> str:
    entry_word = "entry" if entry_count == 1 else "entries"
    error_word = "error" if len(errors) == 1 else "errors"
    lines: list[str] = [
        f"Invalid: {source} ({entry_count} {entry_word}, {len(errors)} {error_word})",
        "",
    ]
    for e in errors:
        lines.append(f"  {e}")
    return "\n".join(lines)


def list_message(config_path: Path, servers: list[tuple[str, str]]) -> str:
    if not servers:
        return f"No mcp-proxy MCP servers configured.\nTarget: {config_path}"
    max_name = max(len(n) for n, _ in servers)
    lines = [f"Target: {config_path}", ""]
    for name, url in servers:
        lines.append(f"  {name.ljust(max_name)} : {url}")
    return "\n".join(lines)


def doctor_message(results: list[tuple[str, bool, str]]) -> str:
    lines: list[str] = []
    for label, passed, detail in results:
        tag = "[PASS]" if passed else "[FAIL]"
        lines.append(f"{tag} {label}: {detail}")
    lines.append("")
    fail_count = sum(1 for _, passed, _ in results if not passed)
    if fail_count == 0:
        lines.append("All checks passed.")
    elif fail_count == 1:
        lines.append("1 check failed. See above for details.")
    else:
        lines.append(f"{fail_count} checks failed. See above for details.")
    return "\n".join(lines)
