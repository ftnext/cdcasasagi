# cdcasasagi handoff (validate-import - -> import --write -> revert)

tags: handoff

E2E for the non-developer handoff journey described in `docs/author-workflow.md`:
paste JSONL into `validate-import -`, run `import --write`, and `revert` as the
escape hatch.

## Paste JSONL, import --write, then revert back to the empty initial state

* Claude Desktop is used with no MCP server entries
* Run cdcasasagi "validate-import -" with the following JSONL piped to stdin
     |url                                |name                 |
     |-----------------------------------|---------------------|
     |https://developers.openai.com/mcp  |openai-developer-docs|
     |https://mcp.notion.com/mcp         |                     |
* The staging file "mcp-servers.jsonl" is created
* Run cdcasasagi "import ./mcp-servers.jsonl --write"
* "openai-developer-docs,notion" entries are written to the config file
* The backup file is created
* Run cdcasasagi "revert"
* The config file has no MCP server entries
