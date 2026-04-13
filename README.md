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

Preview what will be written to `claude_desktop_config.json`:

```
cdcasasagi add https://developers.openai.com/mcp --name openai-developer-docs
```

This shows a unified diff of the proposed change. No files are modified.

Apply the change:

```
cdcasasagi add https://developers.openai.com/mcp --name openai-developer-docs --write
```

This writes the following entry to your Claude Desktop config:

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

The `--name` flag is optional. If omitted, a name is automatically derived from the URL hostname (e.g. `developers` for the URL above).

### Options

| Option | Description |
|---|---|
| `--name` | Key name for the `mcpServers` entry. Auto-derived from URL if omitted. |
| `--transport` | Transport type passed to mcp-proxy. Default: `streamablehttp`. |
| `--force` | Overwrite an existing entry with the same name. |
| `--write` | Actually write to the config file. Without this flag, only a preview is shown. |
