# AGENTS.md

This file provides guidance to coding agents when working with code in this repository.

@README.md

## Build & Test Commands

```bash
uv sync --frozen                                         # Install dependencies
uv run --no-sync pytest                                  # Run all tests
uv run --no-sync pytest tests/test_cli.py                # Run a single test file
uv run --no-sync pytest tests/test_cli.py -k test_name   # Run a single test by name
uv run --no-sync ruff check --fix src/ tests/            # Lint
uv run --no-sync ruff format src/ tests/                 # Format
uv build                                                 # Build package
```

## Architecture

`src/cdcasasagi/` with src layout. Entry point: `cdcasasagi:main` → `cli.app` (Typer).

- `cli.py` — CLI commands: `add`, `doctor`, `import`, `revert`
- `desktop_config.py` — Config file I/O, entry merging, import planning, atomic writes with `.bak` backups
- `mcp_proxy.py` — Locates `mcp-proxy` binary in the same venv
- `server_name.py` — Derives server name from URL hostname
- `output.py` — All user-facing output formatting (diffs, messages)

## Workflow

After implementation is complete, run the following in order:

```bash
uv run --no-sync ruff format src/ tests/
uv run --no-sync ruff check --fix src/ tests/
uv run --no-sync pytest
```

## Testing

Tests use `pytest` with `typer.testing.CliRunner`. The `config_env` fixture sets `CLAUDE_DESKTOP_CONFIG` to a temp path and stubs `mcp_proxy.sys.executable` — no real filesystem side effects.

End-to-end tests live under `e2e/specs/` and are written with [Gauge](https://gauge.org/). Specs are organized by *behavior* rather than per-command — e.g. preview vs `--write` round-trip (`add.spec` / `add_write.spec`), all-or-nothing semantics (`import_conflict.spec`), the non-developer handoff journey (`handoff.spec`), and error surfacing through the subprocess boundary (`errors.spec`). Not every command has its own spec; a command is only covered here when its behavior needs to be verified through a real subprocess (exit codes, stdin/stdout, `.bak` round-trips).

When adding or changing a command, decide whether any of these behaviors apply and add/update the matching spec. Do not skip this step silently — if you judge no E2E is needed, say so explicitly in the PR.

## Audience & Distribution Model

cdcasasagi has two user layers, and command design must account for both. Both layers install the tool the same way (`uv tool install cdcasasagi`); the difference is who decides *what* to run:

1. **Developers** — install the tool and compose commands themselves, using preview mode to inspect changes before applying `--write`. README.md targets this audience.
2. **Non-developer Claude Desktop users** — also install the tool, but do not compose commands themselves. A developer (typically the author, but any developer helping them) runs preview commands locally, settles on the right arguments, and shares a finalized `--write` command. The non-developer's job is reduced to copy-paste — no diff reading, no argument tuning.

The goal for layer 2 is *"paste and done"*. This shapes command design:

- Commands intended for developer composition keep the preview-first / `--write`-to-mutate shape.
- Commands shared with non-developers must be expressible as a single copy-paste string with `--write` already included; the non-developer never sees a preview step.
- `validate-import` intentionally has no `--write` option and never writes any files: it is the developer's read-only composition tool for checking that a JSONL snippet is schema-valid before sharing it. The non-developer handoff is a single `cdcasasagi import - --write` copy-paste into which they paste the JSONL directly — stdin replaces the earlier "stage a file, then import it" two-step.

When adding a new command, decide which layer it serves and whether it participates in the developer-to-non-developer handoff. See `docs/author-workflow.md` for the concrete flow that motivated this model.

## Design Rules

- Always default to preview (non-destructive). Require `--write` to mutate files.
- Import is all-or-nothing: any validation/planning/conflict error → nothing is written.
- Never modify top-level keys other than `mcpServers`.
- Assume config structure is valid (Claude Desktop is using it). Only handle `mcpServers` key being absent (create as `{}`). Do not add handling for non-object JSON or non-dict `mcpServers` (see reverts `0f936eb`, `9a7cb75`).
- Never fall back to PATH / `shutil.which` for `mcp-proxy`. Resolve from the same venv only.
- Reject unknown keys in import JSONL — never silently ignore.
- CLI output must be ASCII-only — no emoji or Unicode symbols (Windows cp1252 cannot encode them).

## Git Rules

- Do not commit removal of `exclude-newer` in `uv.lock` — it disappears in some environments.

## Conventions

- Feature specs are written as detailed GitHub issues (see #1, #4). New commands should follow the same level of specification.
- Write all documentation in English, whether it targets human developers or coding agents.
