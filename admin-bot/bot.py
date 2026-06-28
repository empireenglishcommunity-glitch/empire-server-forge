#!/usr/bin/env python3
import os, subprocess, asyncio, logging
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

BOT_TOKEN = "8890602313:AAFaJRgHEP6yM7DrwkT5PwxRabKuqa4Bnlw"
ADMIN_CHAT_ID = 8355378781
COMPOSE_DIRS = {
    "empire-n8n": "/opt/n8n",
    "empire-challenge-bot": "/opt/empire-challenge/empire-challenge-bot",
    "empire-english-bot": "/opt/empire-english-bot",
    "empire-assessment": "/opt/empire-assessment",
    "empire-n8n-mcp": "/opt/n8n-mcp",
    "emos-postgres": "/opt/emos-db",
}
ALL_CONTAINERS = list(COMPOSE_DIRS.keys())
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)

def admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_chat.id != ADMIN_CHAT_ID:
            await update.message.reply_text("Unauthorized.")
            return
        return await func(update, context)
    return wrapper

def run(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() or r.stderr.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return "Timed out"
    except Exception as e:
        return f"Error: {e}"

@admin_only
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    names = "\n".join(ALL_CONTAINERS)
    t = "\U0001f3db\ufe0f <b>Empire Server Command Bot</b>\n\n"
    t += "/status - All containers + resources\n"
    t += "/logs &lt;name&gt; - Last 15 lines\n"
    t += "/restart &lt;name&gt; - Restart container\n"
    t += "/disk - Disk breakdown\n"
    t += "/backup - Manual backup\n"
    t += "/uptime - Uptime + load\n"
    t += "/services - Resource usage\n"
    t += "/ram - Memory details\n"
    t += "/ip - Network info\n\n"
    t += f"Containers:\n<code>{names}</code>"
    await update.message.reply_text(t, parse_mode="HTML")

@admin_only
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("\u23f3 Checking...")
    cpu = run("top -bn1 | grep 'Cpu(s)' | awk '{print int($2+$4)}'")
    ram = run("free | awk '/Mem:/{printf \"%.0f\", $3/$2*100}'")
    ram_d = run("free -h | awk '/Mem:/{printf \"%s / %s\", $3, $2}'")
    disk = run("df -h / | awk 'NR==2{printf \"%s / %s (%s)\", $3, $2, $5}'")
    up = run("uptime -p")
    ct = run("docker ps -a --format '{{.Names}}|{{.Status}}' | sort")
    lines = []
    for l in ct.split("\n"):
        if "|" in l:
            n, s = l.split("|", 1)
            if "Up" in s:
                if "unhealthy" in s:
                    i = "\U0001f7e1"
                elif "healthy" in s:
                    i = "\U0001f7e2"
                else:
                    i = "\U0001f535"
            else:
                i = "\U0001f534"
            lines.append(f"  {i} {n}")
    tunnel = run("systemctl is-active cloudflared")
    monitor = run("systemctl is-active empire-monitor.timer")
    text = "\U0001f3db\ufe0f <b>Empire Status</b>\n"
    text += f"\u23f0 {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n\n"
    text += f"<b>Resources:</b>\n  CPU: {cpu}%\n  RAM: {ram}% ({ram_d})\n  Disk: {disk}\n  {up}\n\n"
    text += "<b>Containers:</b>\n" + "\n".join(lines) + "\n\n"
    text += f"<b>Services:</b>\n  Tunnel: {tunnel}\n  Monitor: {monitor}"
    await msg.edit_text(text, parse_mode="HTML")

@admin_only
async def cmd_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        names = "\n".join(ALL_CONTAINERS)
        await update.message.reply_text(f"Usage: /logs &lt;name&gt;\n\n<code>{names}</code>", parse_mode="HTML")
        return
    container = context.args[0]
    num_lines = int(context.args[1]) if len(context.args) > 1 else 15
    if container not in ALL_CONTAINERS:
        matches = [c for c in ALL_CONTAINERS if container in c]
        container = matches[0] if len(matches) == 1 else None
    if not container:
        await update.message.reply_text("Unknown container")
        return
    output = run(f"docker logs {container} --tail={num_lines} 2>&1", timeout=10)
    if len(output) > 3800:
        output = "...truncated\n" + output[-3800:]
    await update.message.reply_text(f"\U0001f4cb <b>{container}</b>\n\n<pre>{output}</pre>", parse_mode="HTML")

@admin_only
async def cmd_restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        names = "\n".join(ALL_CONTAINERS)
        await update.message.reply_text(f"Usage: /restart &lt;name&gt;\n<code>{names}</code>", parse_mode="HTML")
        return
    container = context.args[0]
    if container not in COMPOSE_DIRS:
        matches = [c for c in ALL_CONTAINERS if container in c]
        container = matches[0] if len(matches) == 1 else None
    if not container:
        await update.message.reply_text("Unknown container")
        return
    msg = await update.message.reply_text(f"\U0001f504 Restarting {container}...")
    d = COMPOSE_DIRS[container]
    run(f"cd {d} && docker compose restart", timeout=60)
    await asyncio.sleep(10)
    st = run(f"docker inspect --format='{{{{.State.Status}}}}' {container}")
    icon = "\u2705" if st == "running" else "\u26a0\ufe0f"
    await msg.edit_text(f"{icon} <b>{container}</b>: {st}", parse_mode="HTML")

@admin_only
async def cmd_disk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ov = run("df -h / | awk 'NR==2{printf \"Total: %s | Used: %s | Free: %s | %s\", $2, $3, $4, $5}'")
    bd = run("du -sh /var/lib/docker/ /opt/ /var/log/ /tmp/ 2>/dev/null | sort -rh")
    dd = run("docker system df")
    await update.message.reply_text(f"\U0001f4be <b>Disk</b>\n\n<b>{ov}</b>\n\n<pre>{bd}</pre>\n\n<pre>{dd}</pre>", parse_mode="HTML")

@admin_only
async def cmd_backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("\U0001f504 Running backup...")
    run("/opt/backups/backup-n8n.sh 2>&1", timeout=120)
    n = run("ls -lht /opt/backups/n8n/ 2>/dev/null | head -3")
    a = run("ls -lht /opt/backups/assessment/ 2>/dev/null | head -3")
    await msg.edit_text(f"\u2705 <b>Backup Done</b>\n\n<pre>{n}</pre>\n\n<pre>{a}</pre>", parse_mode="HTML")

@admin_only
async def cmd_uptime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = run("uptime")
    l = run("cat /proc/loadavg | awk '{print $1, $2, $3}'")
    await update.message.reply_text(f"\u23f1\ufe0f <b>Uptime</b>\n\n<pre>{u}</pre>\nLoad: {l}", parse_mode="HTML")

@admin_only
async def cmd_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    o = run("docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}'")
    await update.message.reply_text(f"\U0001f433 <b>Resources</b>\n\n<pre>{o}</pre>", parse_mode="HTML")

@admin_only
async def cmd_ram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    f = run("free -h")
    t = run("ps aux --sort=-%mem | head -6 | tail -5 | awk '{print $11, $4}'")
    await update.message.reply_text(f"\U0001f9e0 <b>Memory</b>\n\n<pre>{f}</pre>\n\n<b>Top:</b>\n<pre>{t}</pre>", parse_mode="HTML")

@admin_only
async def cmd_ip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ip = run("curl -sf -4 ifconfig.me")
    hn = run("hostname")
    tun = run("systemctl is-active cloudflared")
    await update.message.reply_text(f"\U0001f310 <b>Network</b>\n\nIPv4: <code>{ip}</code>\nHost: <code>{hn}</code>\nTunnel: {tun}", parse_mode="HTML")

def main():
    logging.info("Starting Empire Server Command Bot...")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("logs", cmd_logs))
    app.add_handler(CommandHandler("restart", cmd_restart))
    app.add_handler(CommandHandler("disk", cmd_disk))
    app.add_handler(CommandHandler("backup", cmd_backup))
    app.add_handler(CommandHandler("uptime", cmd_uptime))
    app.add_handler(CommandHandler("services", cmd_services))
    app.add_handler(CommandHandler("ram", cmd_ram))
    app.add_handler(CommandHandler("ip", cmd_ip))
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
