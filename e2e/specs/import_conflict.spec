# cdcasasagi import: all-or-nothing

E2E for `cdcasasagi import` verifying that a conflict without `--force` blocks
the entire write, and that `--force --write` overwrites the conflict and
applies every entry. These checks run through a real subprocess with piped
stdin, so they exercise the non-TTY branch of `_read_stdin_jsonl`.

## A conflict without --force writes nothing

* Claude Desktop is used with no MCP server entries
* Run cdcasasagi "add https://mcp.notion.com/mcp --write"
* "notion" entry is written to the config file
* Pipe JSONL to cdcasasagi "import - --write"

   |url                              |
   |---------------------------------|
   |https://mcp.notion.com/mcp       |
   |https://developers.openai.com/mcp|
* The last command fails
* The config file is unchanged since the last write

## --force --write overwrites the conflict and applies every entry

* Claude Desktop is used with no MCP server entries
* Run cdcasasagi "add https://mcp.notion.com/mcp --write"
* "notion" entry is written to the config file
* Pipe JSONL to cdcasasagi "import - --force --write"

   |url                              |
   |---------------------------------|
   |https://mcp.notion.com/mcp       |
   |https://developers.openai.com/mcp|
* "notion,developers" entries are written to the config file
