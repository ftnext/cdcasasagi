@AGENTS.md

## Claude Code on the Web

- Prefer `gh` CLI over MCP servers. Always pass `-R ftnext/cdcasasagi` to `gh` commands.
- The default git remote URL points to a local proxy that lacks push permissions. Before `git push`, fix the remote URL:
  ```bash
  gh auth setup-git
  git remote set-url origin https://github.com/ftnext/cdcasasagi.git
  ```
- When a review comment is dismissed during auto-fix (judged as no action needed), reply to that comment with the reason. Write the reply in the same language as the original comment.
