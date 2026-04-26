---
name: cdcasasagi
description: Help a non-developer Claude Desktop user wire up remote (Streamable HTTP) MCP servers via the `cdcasasagi` CLI. Use when the user says things like "add the Notion / Linear / OpenAI MCP server", "I installed Claude Desktop and want to use a remote MCP server", "set up these N MCP servers for me", "import a list of MCP servers", or "undo the last MCP server change". The agent runs `cdcasasagi` on the user's behalf so they never have to read diffs, hand-edit `claude_desktop_config.json`, or compose CLI arguments themselves.
---

# cdcasasagi skill

`cdcasasagi` ("kasasagi" / 鵲) bridges Claude Desktop to Streamable HTTP MCP servers via `mcp-proxy`. It edits `claude_desktop_config.json` safely (atomic write, `.bak` backup, one-step `revert`).

This skill is for **non-developer Claude Desktop users**. The user just talks; you run the right `cdcasasagi` commands for them. They should never have to read a diff or pick CLI flags. Always confirm in plain words before any change.

> Note: Claude Desktop now supports official custom connectors for remote MCP servers. If the user can use those, recommend that path first. `cdcasasagi` is the right tool only when the official connector is not an option.

## Tool overview

```
cdcasasagi version             # is it installed?
cdcasasagi doctor              # is mcp-proxy + config path ready?
cdcasasagi list                # what is configured today?
cdcasasagi add <url> --write   # add one server
cdcasasagi import - --write    # add many servers (JSONL on stdin)
cdcasasagi revert              # undo the last --write
```

Useful facts (verified against the source, not assumed):

- `cdcasasagi` is installed via `uv tool install cdcasasagi`. `mcp-proxy` is a direct dependency and lands in the same venv automatically. Do **not** suggest `uvx` — the path written to the config must be persistent (see `src/cdcasasagi/mcp_proxy.py`).
- Every command that mutates the file defaults to a non-destructive **preview**; the agent must add `--write` to actually change anything.
- A `.bak` file is written next to the config on every successful `--write`. `cdcasasagi revert` restores from that `.bak` and deletes it. There is only one level of undo — the most recent `--write`.
- The Claude Desktop config path:
  - macOS / Linux: `~/Library/Application Support/Claude/claude_desktop_config.json`
  - Windows: `%APPDATA%\Claude\claude_desktop_config.json`
  - Override via the `CLAUDE_DESKTOP_CONFIG` environment variable.
- After any `--write`, the user **must restart Claude Desktop** for the change to take effect.

## Workflow A: Install / verify

Run this at the start of any session, and any time you suspect the tool may be missing or broken.

1. `cdcasasagi version`. If it prints a version, skip to step 4.
2. If `cdcasasagi` is missing: `uv tool install cdcasasagi`. If `uv` itself is missing, install it first:
   - macOS / Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
   - Windows (PowerShell): `irm https://astral.sh/uv/install.ps1 | iex`

   After a fresh `uv` install the user may need to open a new shell so `uv` is on `PATH`.
3. Re-run `cdcasasagi version` to confirm the install.
4. `cdcasasagi doctor`. The output is the canonical readiness signal — it checks `mcp-proxy`, the config file, and that the config directory is writable. Each line is `[PASS]` or `[FAIL]`.
   - If any line is `[FAIL]`, surface that to the user in plain words and stop. Do not run `--write` against a broken setup.
   - A `[FAIL] Config file: not found` is normal on a brand-new install (no servers added yet) — the first `--write` creates the file. The other two checks must pass.

## Workflow B: Add one or a few servers (conversational)

Use this when the user names one or a small handful of servers in chat.

1. Get the URL from the user. If the user did not pick a name, leave `--name` off — the tool derives one from the URL hostname (`developers.openai.com/mcp` -> `developers`, `mcp.notion.com/mcp` -> `notion`).
2. **Confirm in plain words** before writing. Say what you will run, what file it edits, and what name will appear in Claude Desktop. For non-developer users, do not paste the diff back; describe it. Example phrasing:

   > "I'll add the Notion MCP server to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`). It will show up under the name `notion`. OK to proceed?"

   If you are unsure whether the user wants the derived name, you may run `cdcasasagi add <url>` (no `--write`) first and look at the `Derived name from URL: "..."` line in the preview output, then confirm with the user.
3. On confirmation, run with `--write`:

   ```
   cdcasasagi add <url> --write
   # or, with an explicit name the user picked:
   cdcasasagi add <url> --name <name> --write
   ```

4. Repeat per server. Each `--write` overwrites the previous `.bak` — only the most recent change is reversible via `revert`.
5. End with: **"Restart Claude Desktop for the new server(s) to show up."**

### Edge cases for `add`

- **`localhost`, an IP address, or a single-label hostname** -> name derivation fails with "Cannot derive a name from the hostname. Please specify --name explicitly". Ask the user for an explicit name and retry with `--name`.
- **URL or name already exists** -> the command exits 1 with a message ending `Use --force to overwrite`. Do **not** silently retry with `--force`. Tell the user there is an existing entry under that name/URL (it may be hand-added by them or from a previous session), describe what overwriting means, and ask before re-running with `--force --write`.
- **`mcp-proxy not found`** -> the install is broken (likely installed via `uvx` or hand). Re-run Workflow A.

## Workflow C: Bulk import (10+ servers)

Use this when the user hands you a list of URLs (a paste, a doc, a screenshot they read out, etc.). The strategy is: build one JSONL block, validate it once with no writes, then apply it once.

1. **Build JSONL.** One JSON object per line. Schema (every other key is rejected):
   - `url` — required, string, `http://` or `https://`.
   - `name` — optional, string. Omit to let the tool derive from the hostname.
   - `transport` — optional, string, defaults to `streamablehttp`. Only set if the user explicitly says the server uses something different (e.g. `sse`).
2. **Dry-run with `validate-import`.** This command never writes files; it is a safe schema + URL check (`src/cdcasasagi/cli.py`).

   ```bash
   cdcasasagi validate-import - <<'JSONL'
   {"url": "https://mcp.notion.com/mcp"}
   {"url": "https://developers.openai.com/mcp", "name": "openai-developer-docs"}
   {"url": "https://mcp.linear.app/mcp"}
   JSONL
   ```

   - On success the output starts with `Valid: stdin (N entries)` and lists every `name url` pair. Repeat the names back to the user for confirmation.
   - On failure the output starts with `Invalid: stdin (...)` followed by per-entry messages. Fix the JSONL and re-validate. Do not paper over errors by stripping fields or using `--force`.
3. **Confirm in plain words** with the user, e.g. "I'm about to add 12 MCP servers to your Claude Desktop config: notion, linear, openai-developer-docs, ... OK to proceed?"
4. **Apply with `import - --write`** — same JSONL, same heredoc:

   ```bash
   cdcasasagi import - --write <<'JSONL'
   {"url": "https://mcp.notion.com/mcp"}
   {"url": "https://developers.openai.com/mcp", "name": "openai-developer-docs"}
   {"url": "https://mcp.linear.app/mcp"}
   JSONL
   ```

5. End with the **restart Claude Desktop** reminder.

### All-or-nothing semantics

If any planned entry conflicts with something already in the user's config (a name collision, or the URL is already configured under a different name), `import` exits 1 and writes **nothing** — the file is unchanged. The output explains each conflict on a `! name url ...` line.

When this happens:

- Do not auto-retry with `--force`. The conflicting entry might be the user's own (hand-added or from an earlier session).
- List the conflicts to the user in plain words, explain that re-running with `--force --write` will overwrite those existing entries, and ask before doing so.

### Why heredoc, not echo

`'JSONL' ... JSONL` (single-quoted heredoc) prevents the shell from interpolating `$` or backticks inside the URLs. Stick with heredoc; do not use `echo`/`printf` chains for multi-line JSONL.

## Workflow D: Undo

Use proactively when the user says "undo", "that broke something", "remove the last server", "revert", or anything similar.

```
cdcasasagi revert
```

- Restores the config from the `.bak` written by the last `--write`, then deletes the `.bak`.
- Always applies; there is no preview. Confirm in plain words before running.
- **One level only.** If the user did two `--write`s in a row, `revert` only undoes the most recent one. After running `revert`, there is no `.bak` left, so a second `revert` will fail with `Backup not found`.
- Tell the user to restart Claude Desktop after `revert` too.

## Operating rules for the agent

- Run `cdcasasagi doctor` once before the first `--write` of a session. Don't re-run for every command.
- Always confirm with the user before any `--write` or `revert`. Describe the effect, don't show them the raw diff.
- Never edit `claude_desktop_config.json` directly with file tools. Always go through `cdcasasagi`.
- Never pass `--force` without explicit user consent. Treat every conflict as "ask the user".
- Tell the user to restart Claude Desktop after any `--write` or `revert`.
- `cdcasasagi` output is ASCII-only by project policy. Don't pretty-print it back with Unicode boxes or emoji.
- Use `cdcasasagi list` any time the user asks "what do I have configured?" — it lists only `cdcasasagi`-managed entries (`name : url`, sorted), and ignores hand-added entries.
- For exact flag semantics on a particular command, run `cdcasasagi <command> --help` rather than guessing.

## Manual verification (for the skill author)

To smoke-test this skill end-to-end on a real machine:

1. "install cdcasasagi if it isn't already" -> agent runs `uv tool install cdcasasagi` (and `uv` install if missing), then `cdcasasagi version` and `cdcasasagi doctor`.
2. "add the Notion remote MCP server" -> agent confirms in plain words, runs `cdcasasagi add https://mcp.notion.com/mcp --write`, then asks the user to restart Claude Desktop.
3. "set up these 12 servers: ..." -> agent builds JSONL, runs `cdcasasagi validate-import -` (no write), confirms, then runs `cdcasasagi import - --write` with the same JSONL via heredoc.
4. "undo that" -> agent confirms, runs `cdcasasagi revert`, asks the user to restart Claude Desktop.

The bulk path should match the shape of `e2e/specs/handoff.spec` in this repository: `validate-import -` -> `import - --write` -> `revert`.

## Installing this skill

Copy this directory into the user's local Claude skills directory:

```
cp -r skills/cdcasasagi ~/.claude/skills/
```

The skill is then auto-discovered the next time their agent starts. The skill itself does not install `cdcasasagi`; the agent does that on first use via Workflow A.
