# cdcasasagi error surfacing

E2E for errors surfacing through the subprocess boundary: non-zero exit code,
expected stderr, and no config mutation on the error path.

## add rejects an invalid URL and leaves the config file unchanged

* Claude Desktop is used with no MCP server entries
* Run cdcasasagi "add not-a-url --write"
* The last command fails
* stderr contains "Please specify a valid HTTP(S) URL"
* The config file is unchanged

## revert fails when the backup file does not exist

* Claude Desktop is used with no MCP server entries
* Run cdcasasagi "revert"
* The last command fails
* stderr contains "Backup not found"
* The config file is unchanged

## Broken JSONL writes nothing even with import --write

* Claude Desktop is used with no MCP server entries
* Run cdcasasagi "import - --write" with stdin <stdin>
   """
   {"url": "https://mcp.notion.com/mcp"}
   {not json}
   """
* The last command fails
* stderr contains "Failed to parse JSON Lines"
* The config file is unchanged
