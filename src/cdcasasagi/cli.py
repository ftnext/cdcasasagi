from __future__ import annotations

import json
import os
import sys
from importlib.metadata import version as _pkg_version
from pathlib import Path
from urllib.parse import urlparse

import typer

from . import desktop_config, mcp_proxy, output, server_name

_VALID_ENTRY_KEYS = frozenset({"url", "name", "transport"})

app = typer.Typer(pretty_exceptions_enable=False)


@app.callback()
def _callback() -> None:
    pass


@app.command()
def version() -> None:
    typer.echo(_pkg_version("cdcasasagi"))


@app.command()
def doctor() -> None:
    import platform as _platform

    results: list[tuple[str, str, str]] = []

    try:
        proxy_path = mcp_proxy.resolve_path()
        results.append(("mcp-proxy", "pass", str(proxy_path)))
    except mcp_proxy.McpProxyNotFoundError:
        results.append(("mcp-proxy", "fail", "not found"))

    try:
        cfg_path = desktop_config.config_path()
    except desktop_config.AmbiguousConfigError as e:
        results.append(("Config file", "fail", str(e)))
    else:
        if cfg_path.is_file():
            results.append(("Config file", "pass", str(cfg_path)))
        else:
            results.append(("Config file", "fail", f"not found: {cfg_path}"))

        cfg_dir = cfg_path.parent
        if os.access(cfg_dir, os.W_OK):
            results.append(("Config directory", "pass", str(cfg_dir)))
        else:
            results.append(("Config directory", "fail", f"not writable: {cfg_dir}"))

        if _platform.system() == "Windows":
            msix_row = _msix_doctor_row(cfg_path)
            if msix_row is not None:
                results.append(msix_row)
            orphan_row = _orphan_appdata_doctor_row(cfg_path)
            if orphan_row is not None:
                results.append(orphan_row)

    typer.echo(output.doctor_message(results))
    if any(status == "fail" for _, status, _ in results):
        raise typer.Exit(code=1)


def _msix_doctor_row(cfg_path: Path) -> tuple[str, str, str] | None:
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        try:
            cfg_path.resolve().relative_to((Path(local) / "Packages").resolve())
            return None
        except ValueError:
            pass
    candidates = desktop_config.windows_msix_config_candidates()
    if not candidates:
        return None
    detail = desktop_config.format_msix_guidance(
        "Claude Desktop on MSIX reads config from a virtualized path.",
        candidates,
    )
    return ("Claude Desktop MSIX path", "warn", detail)


def _orphan_appdata_doctor_row(cfg_path: Path) -> tuple[str, str, str] | None:
    local = os.environ.get("LOCALAPPDATA", "")
    if not local:
        return None
    try:
        cfg_path.resolve().relative_to((Path(local) / "Packages").resolve())
    except ValueError:
        return None

    appdata_path = desktop_config.appdata_config_path()
    if appdata_path is None or not appdata_path.is_file():
        return None

    try:
        config = desktop_config.load_config(appdata_path)
    except (desktop_config.ConfigError, OSError):
        detail = (
            f"Orphan config at {appdata_path} is present but unreadable.\n"
            f"Active config: {cfg_path}\n"
            "Claude Desktop reads only the active config. Inspect the orphan "
            "file manually, then delete it once you have migrated any entries."
        )
        return ("Orphan APPDATA config", "warn", detail)

    servers = config.get("mcpServers")
    if not isinstance(servers, dict) or not servers:
        return None

    names = ", ".join(sorted(servers.keys()))
    detail = (
        f"Orphan config at {appdata_path} has mcpServers entries: {names}\n"
        f"Active config: {cfg_path} (Claude Desktop reads only this file).\n"
        "Re-add the entries against the active config "
        "(`cdcasasagi add ...` or `cdcasasagi import ...`), "
        "then delete the orphan file."
    )
    return ("Orphan APPDATA config", "warn", detail)


@app.command(name="list")
def list_cmd() -> None:
    """List cdcasasagi-managed MCP servers as 'name : url'."""
    try:
        cfg_path = desktop_config.config_path()
        config = desktop_config.load_config(cfg_path)
    except desktop_config.ConfigError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1)

    servers = desktop_config.list_mcp_proxy_entries(config)
    typer.echo(output.list_message(cfg_path, servers))


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

    try:
        cfg_path = desktop_config.config_path()
        current_config = desktop_config.load_config(cfg_path)
    except desktop_config.ConfigError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1)

    entry = desktop_config.build_entry(proxy_path, transport, url)

    try:
        merged = desktop_config.merge_entry(current_config, name, entry, force, url=url)
    except (desktop_config.EntryExistsError, desktop_config.DuplicateUrlError) as e:
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
def delete(
    url: str = typer.Argument(..., help="URL of the mcpServers entry to remove"),
    write: bool = typer.Option(False, help="Actually write to the file"),
) -> None:
    try:
        cfg_path = desktop_config.config_path()
        current_config = desktop_config.load_config(cfg_path)
    except desktop_config.ConfigError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1)

    try:
        updated, removed = desktop_config.remove_entries_by_url(current_config, url)
    except desktop_config.EntryNotFoundError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1)

    if not write:
        diff_text = output.format_diff(current_config, updated)
        typer.echo(output.delete_preview_message(url, removed, cfg_path, diff_text))
    else:
        desktop_config.write_config(cfg_path, updated)
        typer.echo(output.delete_write_message(url, removed, cfg_path))


@app.command()
def revert() -> None:
    try:
        cfg_path = desktop_config.config_path()
    except desktop_config.ConfigError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1)

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


def _read_stdin_jsonl() -> str:
    """Read JSONL from stdin.

    When stdin is a TTY (interactive paste), stop at the first blank line so
    a single extra Enter after paste finishes input. Otherwise (piped), read
    to EOF as usual.
    """
    if not sys.stdin.isatty():
        return sys.stdin.read()

    fg = None if os.environ.get("NO_COLOR") else typer.colors.CYAN
    typer.secho(
        "Paste JSONL, then press Enter on a blank line to finish "
        "(or Ctrl+D on macOS / Ctrl+Z on Windows):",
        err=True,
        fg=fg,
    )
    lines: list[str] = []
    for line in sys.stdin:
        if line.strip() == "":
            break
        lines.append(line)
    return "".join(lines)


def _parse_import_file(file_path: str) -> tuple[list, str, str]:
    """Read and parse import JSONL.  Returns ``(data, source_label, raw_text)``."""
    if file_path == "-":
        try:
            text = _read_stdin_jsonl()
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

    data = _parse_jsonl(text, source_label)

    if len(data) == 0:
        typer.echo("Input contains no entries", err=True)
        raise typer.Exit(code=1)

    return data, source_label, text


def _parse_jsonl(text: str, source_label: str) -> list:
    """Parse JSON Lines: one JSON value per non-blank line."""
    entries = []
    errors: list[str] = []
    has_content = False
    for i, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        has_content = True
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError as e:
            errors.append(f"line {i}: {e}")

    if not has_content:
        return []

    if errors:
        typer.echo(
            f"Failed to parse JSON Lines from {source_label}:\n" + "\n".join(errors),
            err=True,
        )
        raise typer.Exit(code=1)

    return entries


def _validate_import_schema(raw_entries: list) -> list[str]:
    """Validate JSON schema of each entry.  Returns list of error strings."""
    errors: list[str] = []
    for i, entry in enumerate(raw_entries):
        if not isinstance(entry, dict):
            errors.append(f"entry[{i}]: must be an object")
            continue
        unknown = set(entry.keys()) - _VALID_ENTRY_KEYS
        if unknown:
            errors.append(f"entry[{i}]: unknown keys: {', '.join(sorted(unknown))}")
        if "url" not in entry:
            errors.append(f'entry[{i}]: missing required key "url"')
        elif not isinstance(entry["url"], str):
            errors.append(f'entry[{i}]: "url" must be a string')
        if "name" in entry and not isinstance(entry["name"], str):
            errors.append(f'entry[{i}]: "name" must be a string')
        if "transport" in entry and not isinstance(entry["transport"], str):
            errors.append(f'entry[{i}]: "transport" must be a string')
    return errors


def _collect_entry_errors(
    raw_entries: list[dict],
) -> tuple[list[str], list[tuple[str, str, str]]]:
    """Validate URLs, derive names, check duplicates.  No entry building.

    Returns ``(errors, validated)`` where *validated* contains
    ``(name, url, transport)`` tuples for entries that passed individual
    validation.
    """
    errors: list[str] = []
    validated: list[tuple[str, str, str]] = []

    for i, raw in enumerate(raw_entries):
        url = raw["url"]
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            errors.append(f"entry[{i}]: Please specify a valid HTTP(S) URL: {url}")
            continue
        if not parsed.hostname:
            errors.append(f"entry[{i}]: Invalid URL format: {url}")
            continue

        name = raw.get("name")
        if name is None:
            try:
                name = server_name.derive_server_name(url)
            except server_name.NameDerivationError as e:
                errors.append(f'entry[{i}]: {e}. Set "name" explicitly for this entry')
                continue

        transport = raw.get("transport", "streamablehttp")
        validated.append((name, url, transport))

    # Duplicate checks within the input
    names_seen: dict[str, int] = {}
    urls_seen: dict[str, int] = {}

    for i, (name, url, _) in enumerate(validated):
        if name in names_seen:
            errors.append(
                f'Duplicate name "{name}" in entry[{names_seen[name]}] and entry[{i}]'
            )
        else:
            names_seen[name] = i
        if url in urls_seen:
            errors.append(
                f'Duplicate url "{url}" in entry[{urls_seen[url]}] and entry[{i}]'
            )
        else:
            urls_seen[url] = i

    return errors, validated


def _resolve_import_entries(
    raw_entries: list[dict],
    proxy_path: Path,
) -> list[tuple[str, str, dict]]:
    """Validate URLs, derive names, build config entries.

    Returns list of ``(name, url, entry_dict)``.
    """
    errors, validated = _collect_entry_errors(raw_entries)
    if errors:
        typer.echo("\n".join(errors), err=True)
        raise typer.Exit(code=1)

    return [
        (name, url, desktop_config.build_entry(proxy_path, transport, url))
        for name, url, transport in validated
    ]


# ------------------------------------------------------------------
# validate-import command
# ------------------------------------------------------------------


@app.command(name="validate-import")
def validate_import(
    file: str = typer.Argument(..., help="Path to JSONL file (use - for stdin)"),
) -> None:
    """Validate a JSONL import file. Does not write any files."""
    raw_entries, source_label, _ = _parse_import_file(file)

    schema_errors = _validate_import_schema(raw_entries)

    if not schema_errors:
        entry_errors, validated = _collect_entry_errors(raw_entries)
    else:
        entry_errors = []
        validated = []

    all_errors = schema_errors + entry_errors

    if all_errors:
        typer.echo(
            output.validate_error_message(source_label, len(raw_entries), all_errors),
            err=True,
        )
        raise typer.Exit(code=1)

    typer.echo(output.validate_ok_message(source_label, len(raw_entries), validated))


# ------------------------------------------------------------------
# import command
# ------------------------------------------------------------------


@app.command(name="import")
def import_cmd(
    file: str = typer.Argument(..., help="Path to JSONL file (use - for stdin)"),
    force: bool = typer.Option(False, help="Overwrite existing entries on conflict"),
    write: bool = typer.Option(False, help="Actually write to the file"),
    verbose: bool = typer.Option(False, help="Show full diff in preview"),
) -> None:
    # Phase 1: Validation
    raw_entries, source_label, _ = _parse_import_file(file)

    try:
        proxy_path = mcp_proxy.resolve_path()
    except mcp_proxy.McpProxyNotFoundError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1)

    schema_errors = _validate_import_schema(raw_entries)
    if schema_errors:
        typer.echo("\n".join(schema_errors), err=True)
        raise typer.Exit(code=1)

    resolved = _resolve_import_entries(raw_entries, proxy_path)

    try:
        cfg_path = desktop_config.config_path()
        current_config = desktop_config.load_config(cfg_path)
    except desktop_config.ConfigError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1)

    # Phase 2: Planning
    plan = desktop_config.plan_import(current_config, resolved)

    # Build plan_for_output by simulating apply_import row by row so `replaces`
    # reflects the state each row will actually see (earlier rows may have
    # already deleted or rewritten entries this row would otherwise claim).
    working = json.loads(json.dumps(current_config))
    if "mcpServers" not in working:
        working["mcpServers"] = {}

    plan_for_output: list[tuple[str, str, str, list[str]]] = []
    for (name, action, entry), (_n, url, _e) in zip(plan, resolved):
        replaces: list[str] = []
        if action == "conflict":
            replaces = [
                n
                for n in desktop_config.find_entry_names_by_url(working, url)
                if n != name
            ]
        plan_for_output.append((name, action, url, replaces))

        if action == "add" or (action == "conflict" and force):
            for r in replaces:
                del working["mcpServers"][r]
            working["mcpServers"][name] = entry

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
        action == "add" or (action == "conflict" and force) for _, action, _ in plan
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
