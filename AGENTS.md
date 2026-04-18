# AGENTS.md

This file provides guidance to coding agents when working with code in this repository.

@README.md

## Build & Test Commands

```bash
uv sync                                        # Install dependencies
uv run pytest                                  # Run all tests
uv run pytest tests/test_cli.py                # Run a single test file
uv run pytest tests/test_cli.py -k test_name   # Run a single test by name
uv run ruff check --fix src/ tests/            # Lint
uv run ruff format src/ tests/                 # Format
uv build                                       # Build package
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
uv run ruff format src/ tests/
uv run ruff check --fix src/ tests/
uv run pytest
```

## Testing

Tests use `pytest` with `typer.testing.CliRunner`. The `config_env` fixture sets `CLAUDE_DESKTOP_CONFIG` to a temp path and stubs `mcp_proxy.sys.executable` — no real filesystem side effects.

## Audience & Distribution Model

cdcasasagi has two user layers, and command design must account for both. Both layers install the tool the same way (`uv tool install cdcasasagi`); the difference is who decides *what* to run:

1. **Developers** — install the tool and compose commands themselves, using preview mode to inspect changes before applying `--write`. README.md targets this audience.
2. **Non-developer Claude Desktop users** — also install the tool, but do not compose commands themselves. A developer (typically the author, but any developer helping them) runs preview commands locally, settles on the right arguments, and shares a finalized `--write` command. The non-developer's job is reduced to copy-paste — no diff reading, no argument tuning.

The goal for layer 2 is *"paste and done"*. This shapes command design:

- Commands intended for developer composition keep the preview-first / `--write`-to-mutate shape.
- Commands shared with non-developers must be expressible as a single copy-paste string with `--write` already included; the non-developer never sees a preview step.
- `validate-import` intentionally has no `--write` option: it is the developer's composition tool for validating JSONL shared by the non-developer, and saves to a predictable path so the follow-up `import --write` command can also be handed over as a fixed string. Splitting the two keeps the non-developer path a sequence of pure copy-pastes.

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
