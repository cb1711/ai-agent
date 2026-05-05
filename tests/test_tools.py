import os
import pytest
from datetime import datetime, timezone, timedelta


# ── File tools ────────────────────────────────────────────────────────────────

class TestReadFileTool:
    def test_reads_existing_file(self, tmp_path):
        from tools.file_ops import read_file_tool
        f = tmp_path / "hello.txt"
        f.write_text("hello world")
        assert read_file_tool.invoke({"path": str(f)}) == "hello world"

    def test_missing_file_returns_error_string(self):
        from tools.file_ops import read_file_tool
        result = read_file_tool.invoke({"path": "/nonexistent/path/file.txt"})
        assert result.startswith("Error reading file:")

    def test_reads_utf8_content(self, tmp_path):
        from tools.file_ops import read_file_tool
        f = tmp_path / "unicode.txt"
        f.write_text("こんにちは", encoding="utf-8")
        assert read_file_tool.invoke({"path": str(f)}) == "こんにちは"


class TestWriteFileTool:
    def test_writes_content(self, tmp_path):
        from tools.file_ops import write_file_tool
        path = str(tmp_path / "out.txt")
        write_file_tool.invoke({"path": path, "content": "test content"})
        assert open(path).read() == "test content"

    def test_creates_parent_directories(self, tmp_path):
        from tools.file_ops import write_file_tool
        path = str(tmp_path / "a" / "b" / "c.txt")
        write_file_tool.invoke({"path": path, "content": "nested"})
        assert os.path.isfile(path)

    def test_returns_confirmation_string(self, tmp_path):
        from tools.file_ops import write_file_tool
        path = str(tmp_path / "f.txt")
        result = write_file_tool.invoke({"path": path, "content": "abc"})
        assert "Wrote" in result and "3" in result

    def test_overwrites_existing_file(self, tmp_path):
        from tools.file_ops import write_file_tool
        path = str(tmp_path / "f.txt")
        write_file_tool.invoke({"path": path, "content": "first"})
        write_file_tool.invoke({"path": path, "content": "second"})
        assert open(path).read() == "second"


# ── Shell tool ────────────────────────────────────────────────────────────────

class TestShellCommandTool:
    def test_runs_simple_command(self):
        from tools.shell_tool import shell_command_tool
        result = shell_command_tool.invoke({"command": "echo hello"})
        assert result.strip() == "hello"

    def test_captures_stderr(self):
        from tools.shell_tool import shell_command_tool
        result = shell_command_tool.invoke({"command": "ls /nonexistent_path_xyz 2>&1"})
        assert len(result) > 0  # some error message returned

    def test_returns_exit_code_message_on_no_output(self):
        from tools.shell_tool import shell_command_tool
        result = shell_command_tool.invoke({"command": "true"})
        # 'true' exits 0 with no output
        assert "exit code 0" in result or result == ""

    def test_timeout_returns_error_string(self, mocker):
        import subprocess
        from tools.shell_tool import shell_command_tool
        mocker.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("sleep", 30))
        result = shell_command_tool.invoke({"command": "sleep 999"})
        assert "timed out" in result


# ── Python REPL tool ──────────────────────────────────────────────────────────

class TestPythonREPLTool:
    def test_evaluates_expression(self):
        from tools.code_exec import python_repl_tool
        result = python_repl_tool.invoke({"code": "print(2 + 2)"})
        assert "4" in result

    def test_returns_string(self):
        from tools.code_exec import python_repl_tool
        result = python_repl_tool.invoke({"code": "x = 42"})
        assert isinstance(result, str)

    def test_state_persists_across_calls(self):
        from tools.code_exec import python_repl_tool
        python_repl_tool.invoke({"code": "repl_test_var = 99"})
        result = python_repl_tool.invoke({"code": "print(repl_test_var)"})
        assert "99" in result


# ── Memory tools ─────────────────────────────────────────────────────────────

class TestMemoryTools:
    def test_remember_fact_tool_returns_confirmation(self, isolated_db):
        from tools.memory_tools import remember_fact_tool
        result = remember_fact_tool.invoke({"key": "city", "value": "Tokyo"})
        assert "city" in result and "Tokyo" in result

    def test_recall_facts_tool_empty(self, isolated_db):
        from tools.memory_tools import recall_facts_tool
        result = recall_facts_tool.invoke({"query": ""})
        assert "No facts" in result

    def test_recall_facts_tool_returns_stored_facts(self, isolated_db):
        from tools.memory_tools import remember_fact_tool, recall_facts_tool
        remember_fact_tool.invoke({"key": "pet", "value": "dog"})
        result = recall_facts_tool.invoke({"query": ""})
        assert "pet" in result and "dog" in result

    def test_recall_facts_tool_filters_by_query(self, isolated_db):
        from tools.memory_tools import remember_fact_tool, recall_facts_tool
        remember_fact_tool.invoke({"key": "food", "value": "sushi"})
        remember_fact_tool.invoke({"key": "sport", "value": "tennis"})
        result = recall_facts_tool.invoke({"query": "food"})
        assert "sushi" in result
        assert "tennis" not in result

    def test_recall_facts_tool_no_match(self, isolated_db):
        from tools.memory_tools import recall_facts_tool
        result = recall_facts_tool.invoke({"query": "zzznomatch"})
        assert "No facts found" in result


# ── Scheduler tool ────────────────────────────────────────────────────────────

class TestScheduleReminderTool:
    def test_rejects_past_datetime(self, isolated_db):
        from tools.scheduler_tool import schedule_reminder_tool
        from scheduler.jobs import start_scheduler, stop_scheduler
        start_scheduler()
        try:
            past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
            result = schedule_reminder_tool.invoke({"message": "late", "when": past})
            assert "future" in result.lower()
        finally:
            stop_scheduler()

    def test_schedules_future_reminder(self, isolated_db):
        from tools.scheduler_tool import schedule_reminder_tool
        from scheduler.jobs import start_scheduler, stop_scheduler, get_scheduler
        start_scheduler()
        try:
            future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
            result = schedule_reminder_tool.invoke({"message": "hello", "when": future})
            assert "scheduled" in result.lower()
            jobs = get_scheduler().get_jobs()
            assert len(jobs) > 0
        finally:
            stop_scheduler()

    def test_rejects_invalid_datetime_string(self, isolated_db):
        from tools.scheduler_tool import schedule_reminder_tool
        from scheduler.jobs import start_scheduler, stop_scheduler
        start_scheduler()
        try:
            result = schedule_reminder_tool.invoke({"message": "x", "when": "not-a-date"})
            assert "Failed" in result or "Error" in result
        finally:
            stop_scheduler()
