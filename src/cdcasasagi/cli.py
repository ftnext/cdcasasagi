from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlparse

import typer

from . import desktop_config, mcp_proxy, output, server_name

_VALID_ENTRY_KEYS = frozenset({"url", "name", "transport"})

app = typer.Typer(pretty_exceptions_enable=False)


@app.callback()
def _callback() -> None:
    pass


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        typer.echo("Please specify a valid HTTP(S) URL", err=True)
        raise typer.Exit(code=1)
    if not parsed.hostname:
        typer.echo("Invalid URL format", err=True)
        raise typer.Exit(code=1)


@app.command()
def add(
    url: str = typer.Argument(..., help="URL of the MCP server"),
    name: str | None = typer.Option(None, help="Key name for mcpServers"),
    transport: str = typer.Option(
        "streamablehttp", help="Transport type passed to mcp-proxy"
    ),
    force: bool = typer.Option(False, help="Overwrite existing entry"),
    write: bool = typer.Option(False, help="Actually write to the file"),
) -> None:
    _validate_url(url)

    name_was_derived = name is None
    if name is None:
        try:
            name = server_name.derive_server_name(url)
        except server_name.NameDerivationError as e:
            typer.echo(str(e), err=True)
            raise typer.Exit(code=1)

    try:
        proxy_path = mcp_proxy.resolve_path()
    except mcp_proxy.McpProxyNotFoundError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1)

    cfg_path = desktop_config.config_path()

    try:
        current_config = desktop_config.load_config(cfg_path)
    except desktop_config.ConfigError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1)

    entry = desktop_config.build_entry(proxy_path, transport, url)

    try:
        merged = desktop_config.merge_entry(current_config, name, entry, force)
    except desktop_config.EntryExistsError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1)

    file_existed = cfg_path.exists()

    if not write:
        original = None if not file_existed else current_config
        diff_text = output.format_diff(original, merged)
        msg = output.preview_message(name, name_was_derived, cfg_path, diff_text)
        typer.echo(msg)
    else:
        desktop_config.write_config(cfg_path, merged)
        msg = output.write_message(name, name_was_derived, cfg_path, file_existed)
        typer.echo(msg)


@app.command()
def revert() -> None:
    cfg_path = desktop_config.config_path()

    try:
        backup_config = desktop_config.load_backup(cfg_path)
    except desktop_config.BackupNotFoundError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1)
    except desktop_config.BackupError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1)

    try:
        current_config = desktop_config.load_config(cfg_path)
        before = current_config if cfg_path.exists() else None
    except (desktop_config.ConfigError, OSError):
        before = None

    diff_text = output.format_diff(
        before, backup_config, from_label="before", to_label="after"
    )
    desktop_config.revert_config(cfg_path, backup_config)
    msg = output.revert_message(cfg_path, diff_text)
    typer.echo(msg)


# ------------------------------------------------------------------
# import command helpers
# ------------------------------------------------------------------


def _parse_import_file(file_path: str) -> tuple[list, str]:
    """Read and parse import JSON.  Returns ``(data, source_label)``."""
    if file_path == "-":
        try:
            text = sys.stdin.read()
        except UnicodeDecodeError as e:
            typer.echo(f"Cannot read stdin: {e}", err=True)
            raise typer.Exit(code=1)
        source_label = "stdin"
    else:
        path = Path(file_path)
        if not path.exists():
            typer.echo(f"File not found: {file_path}", err=True)
            raise typer.Exit(code=1)
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            typer.echo(f"Cannot read file: {file_path}\n{e}", err=True)
            raise typer.Exit(code=1)
        source_label = file_path

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        typer.echo(f"Failed to parse JSON from {source_label}: {e}", err=True)
        raise typer.Exit(code=1)

    if not isinstance(data, list):
        typer.echo("Input must be a JSON array of entries", err=True)
        raise typer.Exit(code=1)

    if len(data) == 0:
        typer.echo("Input contains no entries", err=True)
        raise typer.Exit(code=1)

    return data, source_label


def _validate_import_schema(raw_entries: list) -> list[str]:
    """Validate JSON schema of each entry.  Returns list of error strings."""
    errors: list[str] = []
    for i, entry in enumerate(raw_entries):
        if not isinstance(entry, dict):
            errors.append(f"entry[{i}]: must be an object")
            continue
        unknown = set(entry.keys()) - _VALID_ENTRY_KEYS
        if unknown:
            errors.append(
                f"entry[{i}]: unknown keys: {', '.join(sorted(unknown))}"
            )
        if "url" not in entry:
            errors.append(f'entry[{i}]: missing required key "url"')
        elif not isinstance(entry["url"], str):
            errors.append(f'entry[{i}]: "url" must be a string')
        if "name" in entry and not isinstance(entry["name"], str):
            errors.append(f'entry[{i}]: "name" must be a string')
        if "transport" in entry and not isinstance(entry["transport"], str):
            errors.append(f'entry[{i}]: "transport" must be a string')
    return errors


def _resolve_import_entries(
    raw_entries: list[dict],
    default_transport: str,
    proxy_path: Path,
) -> list[tuple[str, str, dict]]:
    """Validate URLs, derive names, build config entries.

    Returns list of ``(name, url, entry_dict)``.
    """
    errors: list[str] = []
    resolved: list[tuple[str, str, dict]] = []

    for i, raw in enumerate(raw_entries):
        url = raw["url"]
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            errors.append(
                f"entry[{i}]: Please specify a valid HTTP(S) URL: {url}"
            )
            continue
        if not parsed.hostname:
            errors.append(f"entry[{i}]: Invalid URL format: {url}")
            continue

        name = raw.get("name")
        if name is None:
            try:
                name = server_name.derive_server_name(url)
            except server_name.NameDerivationError as e:
                errors.append(
                    f'entry[{i}]: {e}. Set "name" explicitly for this entry'
                )
                continue

        transport = raw.get("transport", default_transport)
        entry = desktop_config.build_entry(proxy_path, transport, url)
        resolved.append((name, url, entry))

    if errors:
        typer.echo("\n".join(errors), err=True)
        raise typer.Exit(code=1)

    # Duplicate checks within the input
    dup_errors: list[str] = []
    names_seen: dict[str, int] = {}
    urls_seen: dict[str, int] = {}

    for i, (name, url, _) in enumerate(resolved):
        if name in names_seen:
            dup_errors.append(
                f'Duplicate name "{name}" in entry[{names_seen[name]}] and entry[{i}]'
            )
        else:
            names_seen[name] = i
        if url in urls_seen:
            dup_errors.append(
                f'Duplicate url "{url}" in entry[{urls_seen[url]}] and entry[{i}]'
            )
        else:
            urls_seen[url] = i

    if dup_errors:
        typer.echo("\n".join(dup_errors), err=True)
        raise typer.Exit(code=1)

    return resolved


# ------------------------------------------------------------------
# import command
# ------------------------------------------------------------------


@app.command(name="import")
def import_cmd(
    file: str = typer.Argument(..., help="Path to JSON file (use - for stdin)"),
    transport: str = typer.Option(
        "streamablehttp", help="Default transport for entries without one"
    ),
    force: bool = typer.Option(False, help="Overwrite existing entries on conflict"),
    write: bool = typer.Option(False, help="Actually write to the file"),
    verbose: bool = typer.Option(False, help="Show full diff in preview"),
) -> None:
    # Phase 1: Validation
    raw_entries, source_label = _parse_import_file(file)

    try:
        proxy_path = mcp_proxy.resolve_path()
    except mcp_proxy.McpProxyNotFoundError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1)

    schema_errors = _validate_import_schema(raw_entries)
    if schema_errors:
        typer.echo("\n".join(schema_errors), err=True)
        raise typer.Exit(code=1)

    resolved = _resolve_import_entries(raw_entries, transport, proxy_path)

    cfg_path = desktop_config.config_path()
    try:
        current_config = desktop_config.load_config(cfg_path)
    except desktop_config.ConfigError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1)

    # Phase 2: Planning
    entries_for_plan = [(name, entry) for name, _url, entry in resolved]
    plan = desktop_config.plan_import(current_config, entries_for_plan)

    plan_for_output: list[tuple[str, str, str]] = [
        (name, action, url)
        for (name, action, _entry), (_n, url, _e) in zip(plan, resolved)
    ]

    conflicts = [name for name, action, _ in plan if action == "conflict"]
    if conflicts and not force:
        msg = output.import_preview_message(
            cfg_path, source_label, len(raw_entries), plan_for_output, force
        )
        typer.echo(msg)
        raise typer.Exit(code=1)

    # Phase 3: Apply
    merged = desktop_config.apply_import(current_config, plan, force)
    file_existed = cfg_path.exists()

    has_changes = any(
        action == "add" or (action == "conflict" and force)
        for _, action, _ in plan
    )

    if not write:
        verbose_diff = None
        if verbose:
            original = None if not file_existed else current_config
            verbose_diff = output.format_diff(original, merged)
        msg = output.import_preview_message(
            cfg_path,
            source_label,
            len(raw_entries),
            plan_for_output,
            force,
            verbose_diff,
        )
        typer.echo(msg)
    else:
        if has_changes:
            desktop_config.write_config(cfg_path, merged)
            msg = output.import_write_message(
                cfg_path, source_label, plan_for_output, force, file_existed
            )
        else:
            msg = (
                f"Target: {cfg_path}\n"
                f"Source: {source_label}\n\n"
                "All entries are identical to existing configuration. "
                "No changes needed."
            )
        typer.echo(msg)
