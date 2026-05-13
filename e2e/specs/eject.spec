# cdcasasagi eject

E2E for `cdcasasagi eject`: it prints cdcasasagi-managed entries as JSONL on
stdout, removes them from the config (preserving hand-added entries), and
its stdout can be piped straight back into `import` to restore them. These
checks run through real subprocesses so the stdout/stderr split and `.bak`
side effect are exercised end-to-end.

The revert round-trip runs last on purpose: it unlinks the `.bak` the other
`--write` scenarios leave behind, so the next spec starts without a leftover
backup (mirrors `delete.spec`).

## eject prints JSONL on stdout and clears managed entries

* Claude Desktop's config has the following mcpServers entries
   |name      |command  |args                                                        |
   |----------|---------|------------------------------------------------------------|
   |notion    |mcp-proxy|--transport,streamablehttp,https://mcp.notion.com/mcp       |
   |developers|mcp-proxy|--transport,streamablehttp,https://developers.openai.com/mcp|
   |legacy    |node     |/path/to/hand-added-server.js                               |
* Run cdcasasagi "eject"
* The last command succeeds
* stdout has "2" JSONL lines
* stdout contains "https://mcp.notion.com/mcp"
* stdout contains "https://developers.openai.com/mcp"
* stderr contains "Ejected 2 entries"
* "legacy" entry is written to the config file
* "notion,developers,legacy" entries are written to the backup file

## eject is a no-op when no managed entries exist

* Claude Desktop's config has the following mcpServers entries
   |name  |command|args                          |
   |------|-------|------------------------------|
   |legacy|node   |/path/to/hand-added-server.js |
* Run cdcasasagi "eject"
* The last command succeeds
* stderr contains "No cdcasasagi-managed entries to eject."
* The config file is unchanged

## ejected JSONL piped back into import restores the entries

* Claude Desktop's config has the following mcpServers entries
   |name      |command  |args                                                        |
   |----------|---------|------------------------------------------------------------|
   |notion    |mcp-proxy|--transport,streamablehttp,https://mcp.notion.com/mcp       |
   |developers|mcp-proxy|--transport,streamablehttp,https://developers.openai.com/mcp|
* Run cdcasasagi "eject"
* The last command succeeds
* Pipe the previous stdout to cdcasasagi "import - --write"
* "notion,developers" entries are written to the config file

## revert round-trips an eject

* Claude Desktop's config has the following mcpServers entries
   |name  |command  |args                                                 |
   |------|---------|-----------------------------------------------------|
   |notion|mcp-proxy|--transport,streamablehttp,https://mcp.notion.com/mcp|
   |legacy|node     |/path/to/hand-added-server.js                        |
* Run cdcasasagi "eject"
* "legacy" entry is written to the config file
* Run cdcasasagi "revert"
* "notion,legacy" entries are written to the config file
* The URL of "notion" in the config file is "https://mcp.notion.com/mcp"
