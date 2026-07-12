# empire-server-forge — AI Agent Steering Rules

> This file is automatically loaded by Kiro and any AI agent working on
> this repository.

## Session Protocol

Full session commands (`/start`, `/status`, `/sync`, `/sync dry`,
`/checkpoint`) and standing ecosystem-wide rules live in
`empireenglishcommunity-glitch/empire-english-project-memory/.kiro/steering/AI-AGENT-PROTOCOL.md`
(this repo was formerly named `Kiro-Master-Index`). Read that file at
the start of every session, before anything below.

## Project Identity

- **Project:** Server/infrastructure operations for the Empire English Community Hetzner deployment.
- **Parent brand:** Empire English Community.
- **Repository:** `empireenglishcommunity-glitch/empire-server-forge`
- **Assembled from:** `EEC-REPO/infrastructure/` + `Kiro-Master-Index/server-cmdbot/`, split out 2026-07-12. Full history from both sources preserved (see README).

## Repo-Specific Notes

- This repo contains real production infrastructure config — server hardening scripts, n8n workflow JSON, MCP server deploy config. Treat with the same caution as live-server work, not ordinary app code.
- `admin-bot/` has 42 unit tests (`pytest admin-bot/tests/`) — run them before changing `admin-bot/bot.py`, and add new tests for new commands rather than letting coverage regress.
- This org's history includes multiple real leaked secrets (Telegram tokens, n8n API keys, an MCP auth token) found inside `n8n-workflows/` and checkpoint docs. Never hardcode a credential here — reference where it lives on the server (env var name, `.env` path) instead.
- `admin-bot`'s commands (`/restart`, `/backup`) can affect real production containers on the Hetzner server — the bot's only access control is `ADMIN_CHAT_ID`, not the token itself. Treat the bot token with real production-secret care.
