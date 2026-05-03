# cdcasasagi
鵲 - Bridge Claude Desktop to Streamable HTTP MCP servers via mcp-proxy

> [!IMPORTANT]
> As of now, Claude Desktop officially supports [custom connectors](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp) for remote MCP servers.
> I recommend considering that option first.
> While [mcp-proxy](https://github.com/sparfenyuk/mcp-proxy) is a great and easy-to-use tool, the scenarios where it is still necessary are likely limited now that official support exists.
> Additionally, custom connectors work not only with Claude Desktop but also with the web version of Claude, once configured.

> [!NOTE]
> Windows users: see [Windows notes](#windows-notes) for MSIX-specific config path behavior.

## Install

```
uv tool install cdcasasagi
```

## Usage

Commands at a glance:

- **Mutating (preview by default, `--write` to apply):** `add`, `import`, `delete`
- **Read-only:** `list`, `validate-import`, `doctor`
- **Recovery:** `revert` (restores from the `.bak` left by the last `--write`)
- **Misc:** `version`

The `add`, `import`, and `delete` commands default to **preview mode** (no files are modified). Pass `--write` to apply changes.  
For full option details, run `cdcasasagi <command> --help`.

### add

Add a single MCP server entry:

```
cdcasasagi add https://developers.openai.com/mcp
```

This shows a unified diff of the proposed change. Pass `--write` to apply:

```
cdcasasagi add https://developers.openai.com/mcp --write
```

A server name is automatically derived from the URL hostname (e.g. `developers` for the URL above). Use `--name` to specify a custom name:

```
cdcasasagi add https://developers.openai.com/mcp --name openai-developer-docs --write
```

The written entry looks like this:

```json
{
  "mcpServers": {
    "openai-developer-docs": {
      "command": "/Users/you/.local/bin/mcp-proxy",
      "args": [
        "--transport",
        "streamablehttp",
        "https://developers.openai.com/mcp"
      ]
    }
  }
}
```

### import

Add multiple entries at once from a JSONL file:

```
cdcasasagi import servers.jsonl
```

Each line is a JSON object with a required `url` key and optional `name` / `transport` keys:

```jsonl
{"url": "https://developers.openai.com/mcp", "name": "openai-developer-docs"}
{"url": "https://example.com/mcp"}
```

Stdin is also supported — pipe a file, or pass `-` and paste the JSONL interactively:

```
cat servers.jsonl | cdcasasagi import -
```

```
cdcasasagi import - --write
# Paste JSONL, then press Enter on a blank line to finish
# (Ctrl+D / Ctrl+Z also works)
```

### delete

Remove an entry from the Claude Desktop config by URL:

```
cdcasasagi delete https://mcp.notion.com/mcp
```

This shows a unified diff of the proposed removal. Pass `--write` to apply:

```
cdcasasagi delete https://mcp.notion.com/mcp --write
```

Only entries added by cdcasasagi (whose `command` is `mcp-proxy`) are removed. Hand-added entries that happen to share a URL are left alone.

### list

Show cdcasasagi-managed MCP servers in the config:

```
cdcasasagi list
```

Output is `name : url`, one entry per line, sorted by name. Only entries whose `command` is `mcp-proxy` (or `mcp-proxy.exe` on Windows) are shown.

### validate-import

Validate a JSONL file's schema without importing. This command never writes any files.

```
cdcasasagi validate-import servers.jsonl
```

Paste JSONL from stdin instead of preparing a file:

```
cdcasasagi validate-import -
# Paste JSONL, then press Enter on a blank line to finish
# (Ctrl+D / Ctrl+Z also works)
```

Once the JSONL validates, feed the same content to `import - --write` to apply it.

### doctor

Check that cdcasasagi can find what it needs to operate:

```
cdcasasagi doctor
```

This reports the resolved `mcp-proxy` binary, the active Claude Desktop config path, and whether the config directory is writable. The command exits with a non-zero status when any check fails, so it can be used in scripts.

On Windows, `doctor` also surfaces two MSIX-specific warnings:

- **Claude Desktop MSIX path** — the active config is **not** under the MSIX virtualized path, but a Claude MSIX install was detected. Claude Desktop on MSIX reads from the virtualized path (`%LOCALAPPDATA%\Packages\...\LocalCache\Roaming\Claude\...`), so edits to the current path may have no effect. Set `CLAUDE_DESKTOP_CONFIG` to the candidate path shown in the warning.
- **Orphan APPDATA config** — the active config is on the MSIX virtualized path, and a leftover `%APPDATA%\Claude\claude_desktop_config.json` is also present. Claude Desktop reads only the active file, so any `mcpServers` entries in the orphan are ignored. Re-add them against the active config, then delete the orphan.

### revert

Restore the config from the `.bak` backup created by the last `--write`:

```
cdcasasagi revert
```

### version

```
cdcasasagi version
```

## Windows notes

cdcasasagi locates Claude Desktop's config in this order:

1. `CLAUDE_DESKTOP_CONFIG` environment variable, if set.
2. The MSIX virtualized path (`%LOCALAPPDATA%\Packages\<Claude package>\LocalCache\Roaming\Claude\claude_desktop_config.json`), if any MSIX install is detected.
3. `%APPDATA%\Claude\claude_desktop_config.json` otherwise.

When multiple MSIX package directories are detected, cdcasasagi first tries to disambiguate by checking which candidates actually contain a `claude_desktop_config.json` — a common stale-install scenario (several package folders but only one real config) is handled automatically. cdcasasagi only refuses to proceed when more than one candidate file exists and the active one cannot be guessed. In that case, confirm the path via **Settings > Developer > Edit Config** in Claude Desktop, then set `CLAUDE_DESKTOP_CONFIG` to that path.

Run `cdcasasagi doctor` to check the resolved config path. On Windows it also surfaces two MSIX-specific situations:

- The active config is on `%APPDATA%` while a Claude MSIX install is detected. Claude Desktop on MSIX reads the virtualized path, so `%APPDATA%` edits may not apply — point `CLAUDE_DESKTOP_CONFIG` at the MSIX path shown.
- An orphan `%APPDATA%\Claude\claude_desktop_config.json` exists alongside the active MSIX config. Claude Desktop ignores the orphan, so any `mcpServers` entries there are dead. Re-add them against the active config and delete the orphan.
