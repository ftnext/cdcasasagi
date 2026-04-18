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

Stdin is also supported:

```
cat servers.jsonl | cdcasasagi import -
```

### validate-import

Validate a JSONL file without importing:

```
cdcasasagi validate-import servers.jsonl
```

Paste JSONL from stdin instead of preparing a file. When reading from stdin, the validated content is also saved to `./mcp-servers.jsonl` so you can hand it to `import`:

```
cdcasasagi validate-import -
# Paste JSONL, then press Ctrl+D (Ctrl+Z on Windows)

cdcasasagi import ./mcp-servers.jsonl --write
```

Use `--output` (`-o`) to save to a different path. An existing file at the target path is overwritten without prompting.

### revert

Restore the config from the `.bak` backup created by the last `--write`:

```
cdcasasagi revert
```

### version

```
cdcasasagi version
```
