# Empire Server Forge

Infrastructure and server operations for the Empire English Community
Hetzner deployment: n8n workflow automation, the n8n-MCP server (AI
agent tooling), server hardening scripts, and the admin Telegram
command bot for remote server management.

**Parent brand:** Empire English Community — for full cross-project
context, see `empireenglishcommunity-glitch/empire-english-project-memory`
(formerly `Kiro-Master-Index`).

## History note

This repo was assembled on 2026-07-12 from two sources that had been
scattered as subfolders inside other repos, even though "server/infra
ops" is a genuinely distinct concern from the product code it supports:

- `n8n-mcp/`, `n8n-workflows/`, `server-hardening/` — split out of
  `EEC-REPO`'s `infrastructure/` folder (13 original commits preserved)
- `admin-bot/` — split out of `Kiro-Master-Index`'s `server-cmdbot/`
  (6 original commits preserved, including the 2026-07-12
  security-hardening + test-suite rewrite that combined 4 previously
  stranded PRs — see `admin-bot/tests/` for the 42-test suite)

Both histories were extracted independently via
`git filter-repo --subdirectory-filter` / `--path`, verified, then
combined with `git merge --allow-unrelated-histories` — every original
commit from both sources is preserved and browsable in this repo's log.

## What's in this repo

| Path | Purpose |
|------|---------|
| `n8n-mcp/` | MCP server exposing n8n workflow management to AI agent tooling |
| `n8n-workflows/` | Exported n8n workflow JSON (bot automations, imports) |
| `server-hardening/` | Hetzner VPS security/monitoring/backup scripts |
| `admin-bot/` | Telegram bot for remote server admin (`/status`, `/restart`, `/backup`, `/logs`) — has 42 unit tests, run via `pytest admin-bot/tests/` |

## Running the admin bot's tests

```bash
pip install -r requirements-dev.txt
BOT_TOKEN=x python3 -m pytest admin-bot/tests/ -v
```

## AI Agent Notes

See `.kiro/steering/project-rules.md` for the session protocol before
making changes here. This repo holds real production infrastructure
config (server hardening scripts, n8n workflow definitions) — treat
changes here with the same care as live-server work, not as ordinary
app code.
