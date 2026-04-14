@AGENTS.md

## Claude Code on the Web

- Prefer `gh` CLI over MCP servers. Always pass `-R ftnext/cdcasasagi` to `gh` commands.
- The default git remote URL points to a local proxy that lacks push permissions. Before `git push`, fix the remote URL:
  ```bash
  git remote set-url origin "https://ftnext:$(gh auth token)@github.com/ftnext/cdcasasagi.git"
  ```
