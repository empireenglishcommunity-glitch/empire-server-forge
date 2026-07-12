"""Unit tests for server-cmdbot/bot.py"""

import asyncio
import subprocess
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server-cmdbot"))

import bot


# ---------------------------------------------------------------------------
# Tests for run()
# ---------------------------------------------------------------------------


class TestRun:
    """Tests for the run() helper that wraps subprocess."""

    @patch("bot.subprocess.run")
    def test_returns_stdout(self, mock_run):
        mock_run.return_value = MagicMock(stdout="hello", stderr="")
        assert bot.run("echo hello") == "hello"

    @patch("bot.subprocess.run")
    def test_returns_stderr_when_stdout_empty(self, mock_run):
        mock_run.return_value = MagicMock(stdout="", stderr="some error")
        assert bot.run("bad cmd") == "some error"

    @patch("bot.subprocess.run")
    def test_returns_no_output_when_both_empty(self, mock_run):
        mock_run.return_value = MagicMock(stdout="", stderr="")
        assert bot.run("silent") == "(no output)"

    @patch("bot.subprocess.run")
    def test_returns_timed_out_on_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="slow", timeout=30)
        assert bot.run("slow") == "Timed out"

    @patch("bot.subprocess.run")
    def test_returns_exception_string_on_error(self, mock_run):
        mock_run.side_effect = OSError("permission denied")
        assert "permission denied" in bot.run("forbidden")

    @patch("bot.subprocess.run")
    def test_custom_timeout_passed(self, mock_run):
        mock_run.return_value = MagicMock(stdout="ok", stderr="")
        bot.run("cmd", timeout=60)
        mock_run.assert_called_once_with(
            "cmd", shell=True, capture_output=True, text=True, timeout=60
        )

    @patch("bot.subprocess.run")
    def test_strips_whitespace(self, mock_run):
        mock_run.return_value = MagicMock(stdout="  output  \n", stderr="")
        assert bot.run("cmd") == "output"


# ---------------------------------------------------------------------------
# Tests for get_cpu()
# ---------------------------------------------------------------------------


class TestGetCpu:
    """Tests for CPU usage parsing from /proc/stat."""

    @patch("bot.run")
    def test_parses_proc_stat(self, mock_run):
        # Simulated /proc/stat line: cpu  user nice system idle iowait irq softirq
        mock_run.return_value = "cpu  4000 100 1000 4000 200 50 50"
        result = bot.get_cpu()
        # total = 4000+100+1000+4000+200+50+50 = 9400, idle = 4000
        # usage = 100 * (9400 - 4000) / 9400 = ~57%
        assert result == "57"

    @patch("bot.run")
    def test_fallback_on_short_output(self, mock_run):
        # First call returns short output (not enough fields)
        # Second call (fallback) returns a value via the run() wrapper,
        # which get_cpu's fallback path reads .ok from.
        mock_run.side_effect = ["cpu  100 200", bot.CmdResult("45", ok=True)]
        result = bot.get_cpu()
        assert result == "45"

    @patch("bot.run")
    def test_zero_total(self, mock_run):
        # All zeros — total is 0, should fallback
        mock_run.side_effect = ["cpu  0 0 0 0 0 0 0", bot.CmdResult("10", ok=True)]
        result = bot.get_cpu()
        # total = 0, so it falls through to fallback
        assert result == "10"

    @patch("bot.run")
    def test_100_percent_usage(self, mock_run):
        # idle = 0 means 100% usage
        mock_run.return_value = "cpu  5000 500 1000 0 200 100 200"
        result = bot.get_cpu()
        assert result == "100"


# ---------------------------------------------------------------------------
# Tests for get_ram()
# ---------------------------------------------------------------------------


class TestGetRam:
    """Tests for RAM usage parsing from `free`."""

    @patch("bot.run")
    def test_parses_free_output(self, mock_run):
        mock_run.return_value = (
            "              total        used        free      shared  buff/cache   available\n"
            "Mem:        8000000     4000000     2000000      100000     2000000     3500000\n"
            "Swap:       2000000           0     2000000"
        )
        result = bot.get_ram()
        # 100 * 4000000 / 8000000 = 50
        assert result == "50"

    @patch("bot.run")
    def test_returns_question_mark_on_missing_mem(self, mock_run):
        mock_run.return_value = "some garbage output"
        assert bot.get_ram() == "?"

    @patch("bot.run")
    def test_high_usage(self, mock_run):
        mock_run.return_value = (
            "              total        used        free\n"
            "Mem:       16000000    15200000      800000\n"
        )
        result = bot.get_ram()
        # 100 * 15200000 / 16000000 = 95
        assert result == "95"


# ---------------------------------------------------------------------------
# Tests for get_ram_detail()
# ---------------------------------------------------------------------------


class TestGetRamDetail:
    """Tests for human-readable RAM detail parsing."""

    @patch("bot.run")
    def test_parses_free_h_output(self, mock_run):
        mock_run.return_value = (
            "              total        used        free      shared  buff/cache   available\n"
            "Mem:          7.6Gi       3.8Gi       1.9Gi       100Mi       1.9Gi       3.4Gi\n"
            "Swap:         2.0Gi          0B       2.0Gi"
        )
        result = bot.get_ram_detail()
        assert result == "3.8Gi / 7.6Gi"

    @patch("bot.run")
    def test_returns_question_mark_on_garbage(self, mock_run):
        mock_run.return_value = "bad data"
        assert bot.get_ram_detail() == "?"


# ---------------------------------------------------------------------------
# Tests for get_disk()
# ---------------------------------------------------------------------------


class TestGetDisk:
    """Tests for disk usage parsing from `df -h /`."""

    @patch("bot.run")
    def test_parses_df_output(self, mock_run):
        mock_run.return_value = (
            "Filesystem      Size  Used Avail Use% Mounted on\n"
            "/dev/sda1        38G   22G   15G  60% /"
        )
        result = bot.get_disk()
        assert result == "22G / 38G (60%)"

    @patch("bot.run")
    def test_returns_question_mark_on_no_match(self, mock_run):
        mock_run.return_value = "Filesystem      Size  Used Avail Use% Mounted on"
        assert bot.get_disk() == "?"


# ---------------------------------------------------------------------------
# Tests for get_disk_overview()
# ---------------------------------------------------------------------------


class TestGetDiskOverview:
    """Tests for disk overview formatting."""

    @patch("bot.run")
    def test_parses_df_output(self, mock_run):
        mock_run.return_value = (
            "Filesystem      Size  Used Avail Use% Mounted on\n"
            "/dev/sda1        38G   22G   15G  60% /"
        )
        result = bot.get_disk_overview()
        assert result == "Total: 38G | Used: 22G | Free: 15G | 60%"

    @patch("bot.run")
    def test_returns_question_mark_on_no_match(self, mock_run):
        mock_run.return_value = ""
        assert bot.get_disk_overview() == "?"


# ---------------------------------------------------------------------------
# Tests for admin_only decorator
# ---------------------------------------------------------------------------


class TestAdminOnly:
    """Tests for the admin_only access control decorator."""

    @pytest.mark.asyncio
    async def test_allows_admin(self):
        mock_update = MagicMock()
        mock_update.effective_chat.id = bot.ADMIN_CHAT_ID
        mock_context = MagicMock()

        @bot.admin_only
        async def handler(update, context):
            return "allowed"

        result = await handler(mock_update, mock_context)
        assert result == "allowed"

    @pytest.mark.asyncio
    async def test_blocks_non_admin(self):
        mock_update = MagicMock()
        mock_update.effective_chat.id = 999999  # not the admin
        mock_context = MagicMock()

        @bot.admin_only
        async def handler(update, context):
            return "should not reach"

        result = await handler(mock_update, mock_context)
        assert result is None


# ---------------------------------------------------------------------------
# Tests for command handlers
# ---------------------------------------------------------------------------


class TestCmdStart:
    """Tests for /start command handler."""

    @pytest.mark.asyncio
    async def test_sends_help_text(self):
        update = MagicMock()
        update.effective_chat.id = bot.ADMIN_CHAT_ID
        update.message.reply_text = AsyncMock()
        context = MagicMock()

        await bot.cmd_start(update, context)

        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args
        text = call_args[0][0]
        assert "Empire Server Command Bot" in text
        assert "/status" in text
        assert "/logs" in text
        assert "/restart" in text

    @pytest.mark.asyncio
    async def test_blocked_for_non_admin(self):
        update = MagicMock()
        update.effective_chat.id = 12345
        update.message.reply_text = AsyncMock()
        context = MagicMock()

        await bot.cmd_start(update, context)
        update.message.reply_text.assert_not_called()


class TestCmdLogs:
    """Tests for /logs command handler."""

    @pytest.mark.asyncio
    async def test_shows_usage_without_args(self):
        update = MagicMock()
        update.effective_chat.id = bot.ADMIN_CHAT_ID
        update.message.reply_text = AsyncMock()
        context = MagicMock()
        context.args = []

        await bot.cmd_logs(update, context)

        update.message.reply_text.assert_called_once()
        text = update.message.reply_text.call_args[0][0]
        assert "Usage" in text

    @pytest.mark.asyncio
    @patch("bot.run")
    async def test_shows_logs_for_valid_container(self, mock_run):
        mock_run.return_value = bot.CmdResult("line1\nline2\nline3", ok=True)
        update = MagicMock()
        update.effective_chat.id = bot.ADMIN_CHAT_ID
        update.message.reply_text = AsyncMock()
        context = MagicMock()
        context.args = ["empire-n8n"]

        await bot.cmd_logs(update, context)

        update.message.reply_text.assert_called_once()
        text = update.message.reply_text.call_args[0][0]
        assert "empire-n8n" in text
        assert "line1" in text

    @pytest.mark.asyncio
    @patch("bot.run")
    async def test_truncates_long_output(self, mock_run):
        mock_run.return_value = bot.CmdResult("x" * 5000, ok=True)
        update = MagicMock()
        update.effective_chat.id = bot.ADMIN_CHAT_ID
        update.message.reply_text = AsyncMock()
        context = MagicMock()
        context.args = ["empire-n8n"]

        await bot.cmd_logs(update, context)

        text = update.message.reply_text.call_args[0][0]
        assert "truncated" in text

    @pytest.mark.asyncio
    async def test_unknown_container(self):
        update = MagicMock()
        update.effective_chat.id = bot.ADMIN_CHAT_ID
        update.message.reply_text = AsyncMock()
        context = MagicMock()
        context.args = ["nonexistent-xyz"]

        await bot.cmd_logs(update, context)

        text = update.message.reply_text.call_args[0][0]
        assert "Unknown" in text

    @pytest.mark.asyncio
    @patch("bot.run")
    async def test_fuzzy_match_container(self, mock_run):
        mock_run.return_value = bot.CmdResult("log output", ok=True)
        update = MagicMock()
        update.effective_chat.id = bot.ADMIN_CHAT_ID
        update.message.reply_text = AsyncMock()
        context = MagicMock()
        context.args = ["challenge"]  # partial match -> empire-challenge-bot

        await bot.cmd_logs(update, context)

        text = update.message.reply_text.call_args[0][0]
        assert "empire-challenge-bot" in text


class TestCmdRestart:
    """Tests for /restart command handler."""

    @pytest.mark.asyncio
    async def test_shows_usage_without_args(self):
        update = MagicMock()
        update.effective_chat.id = bot.ADMIN_CHAT_ID
        update.message.reply_text = AsyncMock()
        context = MagicMock()
        context.args = []

        await bot.cmd_restart(update, context)

        text = update.message.reply_text.call_args[0][0]
        assert "Usage" in text

    @pytest.mark.asyncio
    async def test_unknown_container(self):
        update = MagicMock()
        update.effective_chat.id = bot.ADMIN_CHAT_ID
        update.message.reply_text = AsyncMock()
        context = MagicMock()
        context.args = ["nonexistent-xyz"]

        await bot.cmd_restart(update, context)

        text = update.message.reply_text.call_args[0][0]
        assert "Unknown" in text

    @pytest.mark.asyncio
    @patch("bot.asyncio.sleep", new_callable=AsyncMock)
    @patch("bot.run")
    async def test_restarts_valid_container(self, mock_run, mock_sleep):
        # First call: docker compose restart (checked via .ok), second: docker inspect (status string)
        mock_run.side_effect = [bot.CmdResult("", ok=True), bot.CmdResult("running", ok=True)]
        update = MagicMock()
        update.effective_chat.id = bot.ADMIN_CHAT_ID
        update.message.reply_text = AsyncMock(return_value=MagicMock(edit_text=AsyncMock()))
        context = MagicMock()
        context.args = ["empire-n8n"]

        await bot.cmd_restart(update, context)

        msg = update.message.reply_text.return_value
        msg.edit_text.assert_called_once()
        text = msg.edit_text.call_args[0][0]
        assert "empire-n8n" in text
        assert "running" in text


class TestCmdStatus:
    """Tests for /status command handler."""

    @pytest.mark.asyncio
    @patch("bot.run")
    @patch("bot.get_cpu", return_value="25")
    @patch("bot.get_ram", return_value="60")
    @patch("bot.get_ram_detail", return_value="4.8Gi / 8.0Gi")
    @patch("bot.get_disk", return_value="22G / 38G (60%)")
    async def test_status_output(self, mock_disk, mock_ram_d, mock_ram, mock_cpu, mock_run):
        mock_run.side_effect = [
            bot.CmdResult("up 5 days", ok=True),
            bot.CmdResult("empire-n8n|Up 5 days (healthy)\nempire-challenge-bot|Up 3 days", ok=True),
            bot.CmdResult("active", ok=True),
            bot.CmdResult("active", ok=True),
        ]
        update = MagicMock()
        update.effective_chat.id = bot.ADMIN_CHAT_ID
        mock_msg = MagicMock(edit_text=AsyncMock())
        update.message.reply_text = AsyncMock(return_value=mock_msg)
        context = MagicMock()

        await bot.cmd_status(update, context)

        mock_msg.edit_text.assert_called_once()
        text = mock_msg.edit_text.call_args[0][0]
        assert "Empire Status" in text
        assert "CPU: 25%" in text
        assert "RAM: 60%" in text
        assert "22G / 38G" in text


class TestCmdDisk:
    """Tests for /disk command handler."""

    @pytest.mark.asyncio
    @patch("bot.run")
    @patch("bot.get_disk_overview", return_value="Total: 38G | Used: 22G | Free: 15G | 60%")
    async def test_disk_output(self, mock_overview, mock_run):
        mock_run.side_effect = [
            "/var/lib/docker\t12G\n/opt\t5G",
            "TYPE   TOTAL   ACTIVE  SIZE    RECLAIMABLE\nImages 5      3       2.1GB   800MB",
        ]
        update = MagicMock()
        update.effective_chat.id = bot.ADMIN_CHAT_ID
        update.message.reply_text = AsyncMock()
        context = MagicMock()

        await bot.cmd_disk(update, context)

        text = update.message.reply_text.call_args[0][0]
        assert "Disk" in text
        assert "Total: 38G" in text


class TestCmdUptime:
    """Tests for /uptime command handler."""

    @pytest.mark.asyncio
    @patch("bot.run")
    async def test_uptime_output(self, mock_run):
        mock_run.side_effect = [
            "12:00:00 up 5 days, 3:22, 1 user, load average: 0.50, 0.30, 0.20",
            "0.50 0.30 0.20 1/234 5678",
        ]
        update = MagicMock()
        update.effective_chat.id = bot.ADMIN_CHAT_ID
        update.message.reply_text = AsyncMock()
        context = MagicMock()

        await bot.cmd_uptime(update, context)

        text = update.message.reply_text.call_args[0][0]
        assert "Uptime" in text
        assert "0.50 0.30 0.20" in text


class TestCmdIp:
    """Tests for /ip command handler."""

    @pytest.mark.asyncio
    @patch("bot.run")
    async def test_ip_output(self, mock_run):
        mock_run.side_effect = ["77.42.43.250", "myserver", "active"]
        update = MagicMock()
        update.effective_chat.id = bot.ADMIN_CHAT_ID
        update.message.reply_text = AsyncMock()
        context = MagicMock()

        await bot.cmd_ip(update, context)

        text = update.message.reply_text.call_args[0][0]
        assert "Network" in text
        assert "77.42.43.250" in text
        assert "myserver" in text


class TestCmdServices:
    """Tests for /services command handler."""

    @pytest.mark.asyncio
    @patch("bot.run")
    async def test_services_output(self, mock_run):
        mock_run.return_value = (
            "NAME            CPU %   MEM USAGE / LIMIT   MEM %\n"
            "empire-n8n      2.50%   250MiB / 8GiB       3.05%"
        )
        update = MagicMock()
        update.effective_chat.id = bot.ADMIN_CHAT_ID
        update.message.reply_text = AsyncMock()
        context = MagicMock()

        await bot.cmd_services(update, context)

        text = update.message.reply_text.call_args[0][0]
        assert "Resources" in text
        assert "empire-n8n" in text


class TestCmdRam:
    """Tests for /ram command handler."""

    @pytest.mark.asyncio
    @patch("bot.run")
    async def test_ram_output(self, mock_run):
        mock_run.side_effect = [
            "              total   used   free\nMem:          8Gi    4Gi    4Gi",
            "/usr/bin/node 3.5\n/usr/bin/python 1.2",
        ]
        update = MagicMock()
        update.effective_chat.id = bot.ADMIN_CHAT_ID
        update.message.reply_text = AsyncMock()
        context = MagicMock()

        await bot.cmd_ram(update, context)

        text = update.message.reply_text.call_args[0][0]
        assert "Memory" in text
        assert "Top" in text


class TestCmdBackup:
    """Tests for /backup command handler."""

    @pytest.mark.asyncio
    @patch("bot.run")
    async def test_backup_output(self, mock_run):
        mock_run.side_effect = [
            bot.CmdResult("backup complete", ok=True),
            bot.CmdResult("-rw-r--r-- 1 root root 5.2M Jul  1 backup-2026-07-01.tar.gz", ok=True),
            bot.CmdResult("-rw-r--r-- 1 root root 1.1M Jul  1 assessment-2026-07-01.tar.gz", ok=True),
        ]
        update = MagicMock()
        update.effective_chat.id = bot.ADMIN_CHAT_ID
        mock_msg = MagicMock(edit_text=AsyncMock())
        update.message.reply_text = AsyncMock(return_value=mock_msg)
        context = MagicMock()

        await bot.cmd_backup(update, context)

        mock_msg.edit_text.assert_called_once()
        text = mock_msg.edit_text.call_args[0][0]
        assert "Backup Done" in text


# ---------------------------------------------------------------------------
# Tests for module-level constants
# ---------------------------------------------------------------------------


class TestConstants:
    """Tests for module configuration constants."""

    def test_compose_dirs_has_expected_entries(self):
        expected = [
            "empire-n8n",
            "empire-challenge-bot",
            "empire-english-bot",
            "empire-assessment",
            "empire-n8n-mcp",
            "emos-postgres",
        ]
        for name in expected:
            assert name in bot.COMPOSE_DIRS

    def test_all_containers_matches_compose_dirs(self):
        assert set(bot.ALL_CONTAINERS) == set(bot.COMPOSE_DIRS.keys())

    def test_admin_chat_id_is_int(self):
        assert isinstance(bot.ADMIN_CHAT_ID, int)
