# cdcasasagi
鵲 - Bridge Claude Desktop to Streamable HTTP MCP servers via mcp-proxy

> [!IMPORTANT]
> As of now, Claude Desktop officially supports [custom connectors](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp) for remote MCP servers.
> I recommend considering that option first.
> While [mcp-proxy](https://github.com/sparfenyuk/mcp-proxy) is a great and easy-to-use tool, the scenarios where it is still necessary are likely limited now that official support exists.
> Additionally, custom connectors work not only with Claude Desktop but also with the web version of Claude, once configured.

## Install

```
uv tool install cdcasasagi
```

## Usage

The `add` and `import` commands default to **preview mode** (no files are modified). Pass `--write` to apply changes.
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

### delete

Remove an entry from the Claude Desktop config by name:

```
cdcasasagi delete notion
```

This shows a unified diff of the proposed removal. Pass `--write` to apply:

```
cdcasasagi delete notion --write
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

### revert

Restore the config from the `.bak` backup created by the last `--write`:

```
cdcasasagi revert
```

### version

```
cdcasasagi version
```
