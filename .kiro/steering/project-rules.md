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

## SSH Key Safety — CRITICAL RULE

**NEVER overwrite `/root/.ssh/authorized_keys` on the server.**

The owner's personal SSH key MUST always remain in the file:
```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICt2S+uTpEDhBO4ur7SIlK6CgeIYqjHm8CeYlLBHFDJ4 empire-n8n
```

Rules for any session that touches SSH keys on the Hetzner server (`77.42.43.250`):
1. **ALWAYS append** (`>>`) — NEVER overwrite (`>`) the `authorized_keys` file.
2. **ALWAYS verify** the owner's `empire-n8n` key is still present after any modification.
3. **If you need to add a session key**, use: `echo "your-key" >> /root/.ssh/authorized_keys`
4. **Before disconnecting**, run: `grep empire-n8n /root/.ssh/authorized_keys` — if it's missing, you've broken access. Fix it immediately.
5. **Clean up session keys when done** — remove your temporary session key but NEVER remove the `empire-n8n` key.

Violation of this rule locks the owner out of the server and requires Hetzner Rescue Mode to recover.

---

## Repo-Specific Notes

- This repo contains real production infrastructure config — server hardening scripts, n8n workflow JSON, MCP server deploy config. Treat with the same caution as live-server work, not ordinary app code.
- `admin-bot/` has 42 unit tests (`pytest admin-bot/tests/`) — run them before changing `admin-bot/bot.py`, and add new tests for new commands rather than letting coverage regress.
- This org's history includes multiple real leaked secrets (Telegram tokens, n8n API keys, an MCP auth token) found inside `n8n-workflows/` and checkpoint docs. Never hardcode a credential here — reference where it lives on the server (env var name, `.env` path) instead.
- `admin-bot`'s commands (`/restart`, `/backup`) can affect real production containers on the Hetzner server — the bot's only access control is `ADMIN_CHAT_ID`, not the token itself. Treat the bot token with real production-secret care.
