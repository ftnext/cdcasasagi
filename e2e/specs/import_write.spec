# cdcasasagi import --write

E2E for `cdcasasagi import` covering the non-conflict `--write` round-trip:
preview is non-destructive, the first `--write` writes every entry, and a
second `--write` merges new entries with existing ones while saving the
previous state to `.bak`.

## A preview is shown

* Claude Desktop is used with no MCP server entries
* Pipe JSONL to cdcasasagi "import -"

   |url                          |
   |-----------------------------|
   |https://mcp.notion.com/mcp   |
   |https://mcp.linear.app/mcp   |
* A preview is shown
* The config file is unchanged

## The second --write merges new entries and preserves the previous state in .bak

* Claude Desktop is used with no MCP server entries
* Pipe JSONL to cdcasasagi "import - --write"

   |url                          |
   |-----------------------------|
   |https://mcp.notion.com/mcp   |
   |https://mcp.linear.app/mcp   |
* "notion,linear" entries are written to the config file
* Pipe JSONL to cdcasasagi "import - --write"

   |url                          |
   |-----------------------------|
   |https://huggingface.co/mcp   |
* "notion,linear,huggingface" entries are written to the config file
* "notion,linear" entries are written to the backup file
