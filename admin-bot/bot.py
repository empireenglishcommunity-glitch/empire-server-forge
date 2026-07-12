#!/usr/bin/env python3
import html
import os
import subprocess
import asyncio
import logging
from datetime import datetime, timezone
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN")
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
MAX_LOG_LINES = 200
NL = chr(10)
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)


def admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_chat.id != ADMIN_CHAT_ID:
            logging.warning(
                "Unauthorized access attempt from chat_id=%s", update.effective_chat.id
            )
            return
        try:
            return await func(update, context)
        except Exception:
            logging.exception("Unhandled error in /%s", func.__name__)
            try:
                await update.message.reply_text(
                    "\u26a0\ufe0f Internal error. Check server logs."
                )
            except Exception:
                pass

    return wrapper


class CmdResult:
    """Wraps a shell command result with explicit success/failure, so
    callers can distinguish 'command ran and printed nothing interesting'
    from 'command actually failed' instead of guessing from output text."""

    def __init__(self, output, ok, returncode=None):
        self.output = output
        self.ok = ok
        self.returncode = returncode

    def __str__(self):
        return self.output

    def __eq__(self, other):
        return self.output == other

    def __contains__(self, item):
        return item in self.output

    def __hash__(self):
        return hash(self.output)


def run(cmd, timeout=30):
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        stdout = r.stdout.strip()
        stderr = r.stderr.strip()
        if r.returncode != 0:
            combined = stderr or stdout or "(no output)"
            logging.warning("cmd failed (rc=%d): %s \u2014 %s", r.returncode, cmd, combined)
            return CmdResult(combined, ok=False, returncode=r.returncode)
        return CmdResult(stdout or "(no output)", ok=True, returncode=0)
    except subprocess.TimeoutExpired:
        logging.error("cmd timed out after %ds: %s", timeout, cmd)
        return CmdResult("Timed out", ok=False)
    except Exception as e:
        logging.exception("cmd exception: %s", cmd)
        return CmdResult(str(e), ok=False)


def get_cpu():
    out = str(run("grep 'cpu ' /proc/stat"))
    try:
        parts = out.split()
        if len(parts) >= 5:
            idle = int(parts[4])
            total = sum(int(x) for x in parts[1:])
            if total > 0:
                return str(int(100 * (total - idle) / total))
    except (ValueError, IndexError):
        logging.warning("Failed to parse /proc/stat output: %s", out)
    fallback = run(
        "top -bn1 -d0 | grep 'Cpu' | head -1 | grep -oP '[0-9.]+' | head -2 | paste -sd+ | bc | xargs printf '%.0f'"
    )
    return str(fallback) if fallback.ok else "?"


def parse_mem_line(flag=""):
    out = str(run("free" + (" " + flag if flag else "")))
    for line in out.split(NL):
        if "Mem:" in line:
            return line.split()
    return None


def get_ram():
    parts = parse_mem_line()
    if parts and len(parts) >= 3:
        try:
            total = int(parts[1])
            used = int(parts[2])
            if total > 0:
                return str(int(100 * used / total))
        except ValueError:
            logging.warning("Failed to parse free output: %s", parts)
    return "?"


def get_ram_detail():
    parts = parse_mem_line("-h")
    if parts and len(parts) >= 3:
        return parts[2] + " / " + parts[1]
    return "?"


def parse_disk_line():
    out = str(run("df -h /"))
    for line in out.split(NL):
        if "/" in line and "Filesystem" not in line:
            return line.split()
    return None


def get_disk():
    parts = parse_disk_line()
    if parts and len(parts) >= 5:
        return parts[2] + " / " + parts[1] + " (" + parts[4] + ")"
    return "?"


def get_disk_overview():
    parts = parse_disk_line()
    if parts and len(parts) >= 5:
        return "Total: " + parts[1] + " | Used: " + parts[2] + " | Free: " + parts[3] + " | " + parts[4]
    return "?"


def resolve_container(name):
    """Fuzzy-match a container name against ALL_CONTAINERS. Returns the
    exact match, the single fuzzy match, or None (ambiguous/no match)."""
    if name in ALL_CONTAINERS:
        return name
    matches = [c for c in ALL_CONTAINERS if name in c]
    return matches[0] if len(matches) == 1 else None


def container_usage_msg(command):
    return "Usage: /" + command + " &lt;name&gt;" + NL + NL + "<code>" + NL.join(ALL_CONTAINERS) + "</code>"


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
    if not ct.ok:
        clines.append("  \u26a0\ufe0f Failed to list containers")
    else:
        for l in str(ct).split(NL):
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
                clines.append("  " + i + " " + html.escape(n))
    tunnel = run("systemctl is-active cloudflared")
    monitor = run("systemctl is-active empire-monitor.timer")
    text = "\U0001f3db\ufe0f <b>Empire Status</b>" + NL
    text += "\u23f0 " + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC") + NL + NL
    text += "<b>Resources:</b>" + NL
    text += "  CPU: " + html.escape(cpu) + "%" + NL
    text += "  RAM: " + html.escape(ram) + "% (" + html.escape(ram_d) + ")" + NL
    text += "  Disk: " + html.escape(disk) + NL
    text += "  " + html.escape(str(up)) + NL + NL
    text += "<b>Containers:</b>" + NL + NL.join(clines) + NL + NL
    text += "<b>Services:</b>" + NL
    text += "  Tunnel: " + html.escape(str(tunnel)) + NL
    text += "  Monitor: " + html.escape(str(monitor))
    await msg.edit_text(text, parse_mode="HTML")


@admin_only
async def cmd_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(container_usage_msg("logs"), parse_mode="HTML")
        return
    raw_name = context.args[0]
    try:
        num = int(context.args[1]) if len(context.args) > 1 else 15
    except ValueError:
        await update.message.reply_text("\u26a0\ufe0f Line count must be a number.")
        return
    num = max(1, min(num, MAX_LOG_LINES))
    container = resolve_container(raw_name)
    if not container:
        matches = [c for c in ALL_CONTAINERS if raw_name in c]
        hint = ("Did you mean: " + ", ".join(matches)) if matches else "No matching container"
        await update.message.reply_text("\u26a0\ufe0f Unknown container. " + hint)
        return
    result = run("docker logs " + container + " --tail=" + str(num) + " 2>&1", timeout=10)
    output = html.escape(str(result))
    if len(output) > 3800:
        output = "...truncated" + NL + output[-3800:]
    prefix = "\U0001f4cb" if result.ok else "\u26a0\ufe0f"
    await update.message.reply_text(
        prefix + " <b>" + html.escape(container) + "</b>" + NL + NL + "<pre>" + output + "</pre>",
        parse_mode="HTML",
    )


@admin_only
async def cmd_restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(container_usage_msg("restart"), parse_mode="HTML")
        return
    container = resolve_container(context.args[0])
    if not container:
        await update.message.reply_text("Unknown container")
        return
    msg = await update.message.reply_text("\U0001f504 Restarting " + container + "...")
    d = COMPOSE_DIRS[container]
    restart_result = run("cd " + d + " && docker compose restart", timeout=60)
    if not restart_result.ok:
        await msg.edit_text(
            "\u274c <b>" + html.escape(container) + "</b> restart failed" + NL
            + "<pre>" + html.escape(str(restart_result)) + "</pre>",
            parse_mode="HTML",
        )
        return
    await asyncio.sleep(10)
    st = run("docker inspect --format='{{.State.Status}}' " + container)
    status_text = str(st)
    icon = "\u2705" if status_text == "running" else "\u26a0\ufe0f"
    await msg.edit_text(
        icon + " <b>" + html.escape(container) + "</b>: " + html.escape(status_text),
        parse_mode="HTML",
    )


@admin_only
async def cmd_disk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ov = get_disk_overview()
    bd = run("du -sh /var/lib/docker/ /opt/ /var/log/ /tmp/ 2>/dev/null | sort -rh")
    dd = run("docker system df")
    text = "\U0001f4be <b>Disk</b>" + NL + NL
    text += "<b>" + html.escape(ov) + "</b>" + NL + NL
    text += "<pre>" + html.escape(str(bd)) + "</pre>" + NL + NL
    text += "<pre>" + html.escape(str(dd)) + "</pre>"
    await update.message.reply_text(text, parse_mode="HTML")


@admin_only
async def cmd_backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("\U0001f504 Running backup...")
    backup_result = run("/opt/backups/backup-n8n.sh 2>&1", timeout=120)
    n = run("ls -lht /opt/backups/n8n/ 2>/dev/null | head -3")
    a = run("ls -lht /opt/backups/assessment/ 2>/dev/null | head -3")
    if backup_result.ok:
        icon = "\u2705"
        title = "Backup Done"
    else:
        icon = "\u26a0\ufe0f"
        title = "Backup may have failed (exit code " + str(backup_result.returncode) + ")"
    text = icon + " <b>" + title + "</b>" + NL + NL
    if not backup_result.ok:
        text += "<pre>" + html.escape(str(backup_result)) + "</pre>" + NL + NL
    text += "<b>n8n backups:</b>" + NL + "<pre>" + html.escape(str(n)) + "</pre>" + NL + NL
    text += "<b>Assessment backups:</b>" + NL + "<pre>" + html.escape(str(a)) + "</pre>"
    await msg.edit_text(text, parse_mode="HTML")


@admin_only
async def cmd_uptime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = run("uptime")
    loadavg = str(run("cat /proc/loadavg"))
    parts = loadavg.split()
    load = " ".join(parts[:3]) if len(parts) >= 3 else loadavg
    text = "\u23f1\ufe0f <b>Uptime</b>" + NL + NL
    text += "<pre>" + html.escape(str(u)) + "</pre>" + NL
    text += "Load (1/5/15): " + html.escape(load)
    await update.message.reply_text(text, parse_mode="HTML")


@admin_only
async def cmd_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    o = run("docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}'")
    text = "\U0001f433 <b>Resources</b>" + NL + NL + "<pre>" + html.escape(str(o)) + "</pre>"
    await update.message.reply_text(text, parse_mode="HTML")


@admin_only
async def cmd_ram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    f = run("free -h")
    t = run("ps aux --sort=-%mem | head -6 | tail -5 | awk '{print $11, $4}'")
    text = "\U0001f9e0 <b>Memory</b>" + NL + NL
    text += "<pre>" + html.escape(str(f)) + "</pre>" + NL + NL
    text += "<b>Top:</b>" + NL + "<pre>" + html.escape(str(t)) + "</pre>"
    await update.message.reply_text(text, parse_mode="HTML")


@admin_only
async def cmd_ip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ip = run("curl -sf -4 ifconfig.me")
    hn = run("hostname")
    tun = run("systemctl is-active cloudflared")
    text = "\U0001f310 <b>Network</b>" + NL + NL
    text += "IPv4: <code>" + html.escape(str(ip)) + "</code>" + NL
    text += "Host: <code>" + html.escape(str(hn)) + "</code>" + NL
    text += "Tunnel: " + html.escape(str(tun))
    await update.message.reply_text(text, parse_mode="HTML")


async def error_handler(update, context: ContextTypes.DEFAULT_TYPE):
    """Global fallback for exceptions not already caught by admin_only's
    own try/except (e.g. errors during Telegram's own update dispatch)."""
    logging.error("Unhandled exception: %s", context.error, exc_info=context.error)
    if update and getattr(update, "message", None):
        try:
            await update.message.reply_text("\u26a0\ufe0f Internal error. Check server logs.")
        except Exception:
            pass


def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN environment variable is not set. "
            "Copy .env.example to .env and fill in your bot token, "
            "or export BOT_TOKEN before running this script."
        )
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
    app.add_error_handler(error_handler)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
