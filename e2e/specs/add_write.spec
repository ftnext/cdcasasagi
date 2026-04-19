# cdcasasagi add --write

E2E for the `--write` round-trip (write the config file / create .bak / revert from .bak)

## add --write creates the config file and .bak

* Claude Desktop is used with no MCP server entries
* Run cdcasasagi "add https://mcp.notion.com/mcp --write"
* "notion" entry is written to the config file
* The backup file is created

## The second --write preserves the previous state in .bak

* Claude Desktop is used with no MCP server entries
* Run cdcasasagi "add https://mcp.notion.com/mcp --write"
* "notion" entry is written to the config file
* Run cdcasasagi "add https://developers.openai.com/mcp --write"
* "notion,developers" entries are written to the config file
* "notion" entry is written to the backup file

## add --write fails on a conflict without --force

* Claude Desktop is used with no MCP server entries
* Run cdcasasagi "add https://mcp.notion.com/mcp --write"
* "notion" entry is written to the config file
* Run cdcasasagi "add https://mcp.notion.com/mcp --write"
* The last command fails
* The config file is unchanged since the last write

## --write with a different name for the same URL fails

* Claude Desktop is used with no MCP server entries
* Run cdcasasagi "add https://mcp.notion.com/mcp --write"
* "notion" entry is written to the config file
* Run cdcasasagi "add https://mcp.notion.com/mcp --name my-notion --write"
* The last command fails
* The config file is unchanged since the last write

## With --force the entry is renamed

* Claude Desktop is used with no MCP server entries
* Run cdcasasagi "add https://mcp.notion.com/mcp --write"
* "notion" entry is written to the config file
* Run cdcasasagi "add https://mcp.notion.com/mcp --name my-notion --write --force"
* "my-notion" entry is written to the config file
* The URL of "my-notion" in the config file is "https://mcp.notion.com/mcp"

## revert restores the state from the backup file

* Claude Desktop is used with no MCP server entries
* Run cdcasasagi "add https://mcp.notion.com/mcp --write"
* Run cdcasasagi "add https://developers.openai.com/mcp --write"
* "notion,developers" entries are written to the config file
* Run cdcasasagi "revert"
* "notion" entry is written to the config file
