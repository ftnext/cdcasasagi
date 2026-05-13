# cdcasasagi delete

E2E for `cdcasasagi delete`, which removes a cdcasasagi-managed MCP server
entry by name. These scenarios seed `claude_desktop_config.json` directly
(no `add --write`) so they can cover hand-added entries whose `command` is
not `mcp-proxy` -- a shape `add` would never produce. That lets us verify
`delete` refuses to touch them and returns a clear error.

The revert round-trip runs last on purpose: it unlinks the `.bak` the other
`--write` scenarios leave behind, so the next spec starts without a leftover
backup (mirrors `add_write.spec`).

## Preview is non-destructive

* Claude Desktop's config has the following mcpServers entries
   |name  |command  |args                                                 |
   |------|---------|-----------------------------------------------------|
   |notion|mcp-proxy|--transport,streamablehttp,https://mcp.notion.com/mcp|
* Run cdcasasagi "delete notion"
* The last command succeeds
* The delete preview announces removal of "notion"
* The config file is unchanged

## --write removes only the matching managed entry and creates a backup

* Claude Desktop's config has the following mcpServers entries
   |name      |command  |args                                                        |
   |----------|---------|------------------------------------------------------------|
   |notion    |mcp-proxy|--transport,streamablehttp,https://mcp.notion.com/mcp       |
   |developers|mcp-proxy|--transport,streamablehttp,https://developers.openai.com/mcp|
   |legacy    |node     |/path/to/hand-added-server.js                               |
* Run cdcasasagi "delete notion --write"
* The last command succeeds
* "developers,legacy" entries are written to the config file
* The backup file is created
* "notion,developers,legacy" entries are written to the backup file

## Refuses to delete a hand-added entry

The named entry's `command` is `node`, not `mcp-proxy`, so `delete` must
refuse with a specific "not managed by cdcasasagi" error rather than remove
it. A regression that dropped the command-basename check would silently
delete the hand-added entry, and this scenario would catch it.

* Claude Desktop's config has the following mcpServers entries
   |name       |command|args                                                 |
   |-----------|-------|-----------------------------------------------------|
   |notion-hand|node   |--transport,streamablehttp,https://mcp.notion.com/mcp|
* Run cdcasasagi "delete notion-hand --write"
* The last command fails
* stderr contains "not managed by cdcasasagi"
* The config file is unchanged

## delete fails when the name is not present

* Claude Desktop's config has the following mcpServers entries
   |name  |command  |args                                                 |
   |------|---------|-----------------------------------------------------|
   |notion|mcp-proxy|--transport,streamablehttp,https://mcp.notion.com/mcp|
* Run cdcasasagi "delete missing"
* The last command fails
* stderr contains "No entry found with name: missing"
* The config file is unchanged

## revert round-trips a delete --write

* Claude Desktop's config has the following mcpServers entries
   |name      |command  |args                                                        |
   |----------|---------|------------------------------------------------------------|
   |notion    |mcp-proxy|--transport,streamablehttp,https://mcp.notion.com/mcp       |
   |developers|mcp-proxy|--transport,streamablehttp,https://developers.openai.com/mcp|
   |legacy    |node     |/path/to/hand-added-server.js                               |
* Run cdcasasagi "delete notion --write"
* "developers,legacy" entries are written to the config file
* Run cdcasasagi "revert"
* "notion,developers,legacy" entries are written to the config file
* The URL of "notion" in the config file is "https://mcp.notion.com/mcp"
