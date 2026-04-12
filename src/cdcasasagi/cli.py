from __future__ import annotations

from urllib.parse import urlparse

import typer

from . import desktop_config, mcp_proxy, output, server_name

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
