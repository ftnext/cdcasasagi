# Author Workflow

This document records the author's own context: why cdcasasagi was built and how the author intends to use it. It is not a spec for all developers — the *Audience & Distribution Model* section of `AGENTS.md` generalizes from this context into policy.

README.md covers the developer-facing usage. This document covers the motivating situation that shaped the tool's design.

> **Note:** As noted in README.md, Claude Desktop now supports custom connectors for remote MCP servers, and that is the recommended path when it fits. This document is about the scenario where custom connectors *cannot* be used — the case that still motivates cdcasasagi.

## Why the author built this tool

The author has non-developer Claude Desktop users around them who want to use remote MCP servers for which custom connectors are not an option. Without cdcasasagi, the path they would have to take is roughly:

1. `uv tool install mcp-proxy`.
2. Figure out the absolute path to the installed `mcp-proxy` binary.
3. Open `claude_desktop_config.json`, hand-edit the `mcpServers` section with the correct `command`, `args`, and server name, and save it without breaking the JSON.

Each of those steps is a significant ask for a non-developer. The author wanted the end-to-end experience to be *much* simpler — ideally a single copy-paste. cdcasasagi exists to make that possible: the author runs the inspection and argument selection locally, and hands the non-developer a finalized command that is safe to copy-paste.

Both sides install cdcasasagi the same way (`uv tool install cdcasasagi`). What the tool optimizes is the *handoff* between them.

## How the author uses `add`

1. The author runs `cdcasasagi add <url>` locally (preview mode) and inspects the diff.
2. If the diff is correct, the author sends the non-developer the `--write` form as a copy-paste string, for example:
   ```
   cdcasasagi add https://developers.openai.com/mcp --write
   ```
3. The non-developer pastes and runs it against their own `uv tool`-installed cdcasasagi. No preview step on their side.

If the derived server name is wrong, the author settles on `--name` during local preview and sends the final command with `--name` baked in.

## How the author uses `import` (with `validate-import`)

Used when multiple servers need to be added at once.

The baseline flow is:

1. The author writes a JSONL file locally.
2. The author runs `cdcasasagi import <file>` in preview mode to confirm the planned changes.
3. The author shares both the JSONL content and a copy-paste `import --write` command with the non-developer.
4. The non-developer obtains the JSONL as a file on their machine and runs the shared `cdcasasagi import <file> --write`.

The stumbling point is step 4. The author typically shares JSONL through chat tools or documentation tools — as *text*, not as an attached file. Asking a non-developer to take that text and save it to a file at a known path (with the right filename, no trailing whitespace, correct line endings) is exactly the kind of friction cdcasasagi is meant to remove.

`import -` closes that gap. The non-developer pastes the shared JSONL directly into `cdcasasagi import - --write` — no intermediate file, no saving step. One copy-paste command, one paste of the JSONL.

So the handoff the author actually sends is:

```
cdcasasagi import - --write
# paste the JSONL, Ctrl+D (or blank line)
```

The only keyboard action is pasting the JSONL and terminating stdin.

`validate-import` is the *author's* composition tool. Before sharing the JSONL, the author can paste it into `cdcasasagi validate-import -` locally to confirm schema / URL validity without touching their own config. `validate-import` deliberately has no `--write` option and does not write any files — it is strictly a read-only validator, keeping "validate" and "mutate the config" as separate concerns.

## Recovery

If a `--write` command produces an unexpected result, the non-developer runs:

```
cdcasasagi revert
```

This restores the `.bak` backup written by the previous `--write`. The author mentions `revert` alongside any `--write` command handed over, so the non-developer has a one-line escape hatch.

## What this context implies for new commands

When the author (or another developer) adds a new command, the questions that fall out of this usage context are:

- Is this for the author's local composition, or will it be handed to a non-developer as a finalized string?
- If handed off, can it be expressed as a single copy-paste `--write` command?
- If the command needs input beyond arguments (e.g. JSONL content), can that input be delivered via stdin (`-`) in the same paste-and-done motion, rather than asking the non-developer to stage a file?

Commands that cannot be reduced to a copy-paste string should stay in the author's local composition toolkit rather than being surfaced to non-developers.
