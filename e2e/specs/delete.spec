# cdcasasagi delete

E2E for `cdcasasagi delete`, which removes a cdcasasagi-managed MCP server
entry by URL. These scenarios seed `claude_desktop_config.json` directly
(no `add --write`) so they can cover hand-added entries whose `command` is
not `mcp-proxy` -- a shape `add` would never produce. That lets us verify
`delete` leaves such entries alone.

The revert round-trip runs last on purpose: it unlinks the `.bak` the other
`--write` scenarios leave behind, so the next spec starts without a leftover
backup (mirrors `add_write.spec`).

## Preview is non-destructive

* Claude Desktop's config has the following mcpServers entries
   |name  |command  |args                                                 |
   |------|---------|-----------------------------------------------------|
   |notion|mcp-proxy|--transport,streamablehttp,https://mcp.notion.com/mcp|
* Run cdcasasagi "delete https://mcp.notion.com/mcp"
* The last command succeeds
* The delete preview announces removal of "https://mcp.notion.com/mcp"
* The config file is unchanged

## --write removes only the matching managed entry and creates a backup

* Claude Desktop's config has the following mcpServers entries
   |name      |command  |args                                                        |
   |----------|---------|------------------------------------------------------------|
   |notion    |mcp-proxy|--transport,streamablehttp,https://mcp.notion.com/mcp       |
   |developers|mcp-proxy|--transport,streamablehttp,https://developers.openai.com/mcp|
   |legacy    |node     |/path/to/hand-added-server.js                               |
* Run cdcasasagi "delete https://mcp.notion.com/mcp --write"
* The last command succeeds
* "developers,legacy" entries are written to the config file
* The backup file is created
* "notion,developers,legacy" entries are written to the backup file

## A hand-added entry that shares the URL is left alone

* Claude Desktop's config has the following mcpServers entries
   |name       |command  |args                                                 |
   |-----------|---------|-----------------------------------------------------|
   |notion     |mcp-proxy|--transport,streamablehttp,https://mcp.notion.com/mcp|
   |notion-hand|node     |/path/to/notion-hand.js                              |
* Run cdcasasagi "delete https://mcp.notion.com/mcp --write"
* The last command succeeds
* "notion-hand" entry is written to the config file

## delete fails when only a hand-added entry matches the URL

* Claude Desktop's config has the following mcpServers entries
   |name       |command|args                   |
   |-----------|-------|-----------------------|
   |notion-hand|node   |/path/to/notion-hand.js|
* Run cdcasasagi "delete https://mcp.notion.com/mcp"
* The last command fails
* stderr contains "No cdcasasagi-managed entry found"
* The config file is unchanged

## delete fails when the URL is not present

* Claude Desktop's config has the following mcpServers entries
   |name  |command  |args                                                 |
   |------|---------|-----------------------------------------------------|
   |notion|mcp-proxy|--transport,streamablehttp,https://mcp.notion.com/mcp|
* Run cdcasasagi "delete https://other.example.com/mcp"
* The last command fails
* stderr contains "No cdcasasagi-managed entry found"
* The config file is unchanged

## revert round-trips a delete --write

* Claude Desktop's config has the following mcpServers entries
   |name      |command  |args                                                        |
   |----------|---------|------------------------------------------------------------|
   |notion    |mcp-proxy|--transport,streamablehttp,https://mcp.notion.com/mcp       |
   |developers|mcp-proxy|--transport,streamablehttp,https://developers.openai.com/mcp|
   |legacy    |node     |/path/to/hand-added-server.js                               |
* Run cdcasasagi "delete https://mcp.notion.com/mcp --write"
* "developers,legacy" entries are written to the config file
* Run cdcasasagi "revert"
* "notion,developers,legacy" entries are written to the config file
* The URL of "notion" in the config file is "https://mcp.notion.com/mcp"
