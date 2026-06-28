#!/usr/bin/env python3
import os
import subprocess
import asyncio
import logging
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
NL = chr(10)
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)


def admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_chat.id != ADMIN_CHAT_ID:
            return
        return await func(update, context)

    return wrapper


def run(cmd, timeout=30):
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return r.stdout.strip() or r.stderr.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return "Timed out"
    except Exception as e:
        return str(e)


def get_cpu():
    out = run("grep 'cpu ' /proc/stat")
    parts = out.split()
    if len(parts) >= 5:
        idle = int(parts[4])
        total = sum(int(x) for x in parts[1:])
        if total > 0:
            return str(int(100 * (total - idle) / total))
    return run("top -bn1 -d0 | grep 'Cpu' | head -1 | grep -oP '[0-9.]+' | head -2 | paste -sd+ | bc | xargs printf '%.0f'")


def get_ram():
    out = run("free")
    for line in out.split(NL):
        if "Mem:" in line:
            parts = line.split()
            total = int(parts[1])
            used = int(parts[2])
            if total > 0:
                return str(int(100 * used / total))
    return "?"


def get_ram_detail():
    out = run("free -h")
    for line in out.split(NL):
        if "Mem:" in line:
            parts = line.split()
            return parts[2] + " / " + parts[1]
    return "?"


def get_disk():
    out = run("df -h /")
    for line in out.split(NL):
        if "/" in line and "Filesystem" not in line:
            parts = line.split()
            return parts[2] + " / " + parts[1] + " (" + parts[4] + ")"
    return "?"


def get_disk_overview():
    out = run("df -h /")
    for line in out.split(NL):
        if "/" in line and "Filesystem" not in line:
            p = line.split()
            return "Total: " + p[1] + " | Used: " + p[2] + " | Free: " + p[3] + " | " + p[4]
    return "?"


@admin_only
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    names = NL.join(ALL_CONTAINERS)
    t = "\U0001f3db\ufe0f <b>Empire Server Command Bot</b>" + NL + NL
    t += "/status - All containers + resources" + NL
    t += "/logs &lt;name&gt; - Last 15 lines" + NL
    t += "/restart &lt;name&gt; - Restart container" + NL
    t += "/disk - Disk breakdown" + NL
    t += "/backup - Manual backup" + NL
    t += "/uptime - Uptime + load" + NL
    t += "/services - Resource usage" + NL
    t += "/ram - Memory details" + NL
    t += "/ip - Network info" + NL + NL
    t += "Containers:" + NL + "<code>" + names + "</code>"
    await update.message.reply_text(t, parse_mode="HTML")


@admin_only
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("\u23f3 Checking...")
    cpu = get_cpu()
    ram = get_ram()
    ram_d = get_ram_detail()
    disk = get_disk()
    up = run("uptime -p")
    ct = run("docker ps -a --format '{{.Names}}|{{.Status}}' | sort")
    clines = []
    for l in ct.split(NL):
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
            clines.append("  " + i + " " + n)
    tunnel = run("systemctl is-active cloudflared")
    monitor = run("systemctl is-active empire-monitor.timer")
    text = "\U0001f3db\ufe0f <b>Empire Status</b>" + NL
    text += "\u23f0 " + datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC") + NL + NL
    text += "<b>Resources:</b>" + NL
    text += "  CPU: " + cpu + "%" + NL
    text += "  RAM: " + ram + "% (" + ram_d + ")" + NL
    text += "  Disk: " + disk + NL
    text += "  " + up + NL + NL
    text += "<b>Containers:</b>" + NL + NL.join(clines) + NL + NL
    text += "<b>Services:</b>" + NL
    text += "  Tunnel: " + tunnel + NL
    text += "  Monitor: " + monitor
    await msg.edit_text(text, parse_mode="HTML")


@admin_only
async def cmd_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Usage: /logs &lt;name&gt;" + NL + NL + "<code>" + NL.join(ALL_CONTAINERS) + "</code>",
            parse_mode="HTML",
        )
        return
    container = context.args[0]
    num = int(context.args[1]) if len(context.args) > 1 else 15
    if container not in ALL_CONTAINERS:
        matches = [c for c in ALL_CONTAINERS if container in c]
        container = matches[0] if len(matches) == 1 else None
    if not container:
        await update.message.reply_text("Unknown container")
        return
    output = run("docker logs " + container + " --tail=" + str(num) + " 2>&1", timeout=10)
    if len(output) > 3800:
        output = "...truncated" + NL + output[-3800:]
    await update.message.reply_text(
        "\U0001f4cb <b>" + container + "</b>" + NL + NL + "<pre>" + output + "</pre>",
        parse_mode="HTML",
    )


@admin_only
async def cmd_restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Usage: /restart &lt;name&gt;" + NL + "<code>" + NL.join(ALL_CONTAINERS) + "</code>",
            parse_mode="HTML",
        )
        return
    container = context.args[0]
    if container not in COMPOSE_DIRS:
        matches = [c for c in ALL_CONTAINERS if container in c]
        container = matches[0] if len(matches) == 1 else None
    if not container:
        await update.message.reply_text("Unknown container")
        return
    msg = await update.message.reply_text("\U0001f504 Restarting " + container + "...")
    d = COMPOSE_DIRS[container]
    run("cd " + d + " && docker compose restart", timeout=60)
    await asyncio.sleep(10)
    st = run("docker inspect --format='{{.State.Status}}' " + container)
    icon = "\u2705" if st == "running" else "\u26a0\ufe0f"
    await msg.edit_text(icon + " <b>" + container + "</b>: " + st, parse_mode="HTML")


@admin_only
async def cmd_disk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ov = get_disk_overview()
    bd = run("du -sh /var/lib/docker/ /opt/ /var/log/ /tmp/ 2>/dev/null | sort -rh")
    dd = run("docker system df")
    text = "\U0001f4be <b>Disk</b>" + NL + NL
    text += "<b>" + ov + "</b>" + NL + NL
    text += "<pre>" + bd + "</pre>" + NL + NL
    text += "<pre>" + dd + "</pre>"
    await update.message.reply_text(text, parse_mode="HTML")


@admin_only
async def cmd_backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("\U0001f504 Running backup...")
    run("/opt/backups/backup-n8n.sh 2>&1", timeout=120)
    n = run("ls -lht /opt/backups/n8n/ 2>/dev/null | head -3")
    a = run("ls -lht /opt/backups/assessment/ 2>/dev/null | head -3")
    text = "\u2705 <b>Backup Done</b>" + NL + NL
    text += "<pre>" + n + "</pre>" + NL + NL
    text += "<pre>" + a + "</pre>"
    await msg.edit_text(text, parse_mode="HTML")


@admin_only
async def cmd_uptime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = run("uptime")
    l = run("cat /proc/loadavg")
    parts = l.split()
    load = " ".join(parts[:3]) if len(parts) >= 3 else l
    text = "\u23f1\ufe0f <b>Uptime</b>" + NL + NL
    text += "<pre>" + u + "</pre>" + NL
    text += "Load (1/5/15): " + load
    await update.message.reply_text(text, parse_mode="HTML")


@admin_only
async def cmd_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    o = run("docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}'")
    text = "\U0001f433 <b>Resources</b>" + NL + NL + "<pre>" + o + "</pre>"
    await update.message.reply_text(text, parse_mode="HTML")


@admin_only
async def cmd_ram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    f = run("free -h")
    t = run("ps aux --sort=-%mem | head -6 | tail -5 | awk '{print $11, $4}'")
    text = "\U0001f9e0 <b>Memory</b>" + NL + NL
    text += "<pre>" + f + "</pre>" + NL + NL
    text += "<b>Top:</b>" + NL + "<pre>" + t + "</pre>"
    await update.message.reply_text(text, parse_mode="HTML")


@admin_only
async def cmd_ip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ip = run("curl -sf -4 ifconfig.me")
    hn = run("hostname")
    tun = run("systemctl is-active cloudflared")
    text = "\U0001f310 <b>Network</b>" + NL + NL
    text += "IPv4: <code>" + ip + "</code>" + NL
    text += "Host: <code>" + hn + "</code>" + NL
    text += "Tunnel: " + tun
    await update.message.reply_text(text, parse_mode="HTML")


def main():
    logging.info("Starting Empire Server Command Bot...")
    app = Application.builder().token(BOT_TOKEN).build()
    handlers = [
        ("start", cmd_start), ("help", cmd_start),
        ("status", cmd_status), ("logs", cmd_logs),
        ("restart", cmd_restart), ("disk", cmd_disk),
        ("backup", cmd_backup), ("uptime", cmd_uptime),
        ("services", cmd_services), ("ram", cmd_ram),
        ("ip", cmd_ip),
    ]
    for cmd, fn in handlers:
        app.add_handler(CommandHandler(cmd, fn))
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
