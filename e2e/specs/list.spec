# cdcasasagi list

E2E for `cdcasasagi list`, which prints cdcasasagi-managed MCP servers as
`name : url`. These scenarios seed `claude_desktop_config.json` directly
(no `add --write`) so they can cover hand-added entries whose `command` is
not `mcp-proxy` -- a shape `add` would never produce.

## Mixed managed and hand-added entries list only the managed one

* Claude Desktop's config has the following mcpServers entries
   |name  |command  |args                                                 |
   |------|---------|-----------------------------------------------------|
   |notion|mcp-proxy|--transport,streamablehttp,https://mcp.notion.com/mcp|
   |legacy|node     |/path/to/hand-added-server.js                        |
* Run cdcasasagi "list"
* The last command succeeds
* stdout contains "notion : https://mcp.notion.com/mcp"
* stdout does not contain "legacy"
* The config file is unchanged

## A config with no mcpServers key lists nothing

* Claude Desktop is used with no MCP server entries
* Run cdcasasagi "list"
* The last command succeeds
* stdout contains "No mcp-proxy MCP servers configured."
* stdout does not contain " : "
* The config file is unchanged

## An empty mcpServers object lists nothing

* Claude Desktop's config has an empty mcpServers object
* Run cdcasasagi "list"
* The last command succeeds
* stdout contains "No mcp-proxy MCP servers configured."
* stdout does not contain " : "
* The config file is unchanged

## Multiple managed entries are printed sorted by name

* Claude Desktop's config has the following mcpServers entries
   |name  |command  |args                                                |
   |------|---------|----------------------------------------------------|
   |zeta  |mcp-proxy|--transport,streamablehttp,https://z.example.com/mcp|
   |alpha |mcp-proxy|--transport,streamablehttp,https://a.example.com/mcp|
   |middle|mcp-proxy|--transport,streamablehttp,https://m.example.com/mcp|
* Run cdcasasagi "list"
* The last command succeeds
* stdout contains "alpha"
* stdout contains "middle"
* stdout contains "zeta"
* stdout has "alpha" listed before "middle"
* stdout has "middle" listed before "zeta"
* The config file is unchanged
