from tools.code_exec import python_repl_tool
from tools.web_search import web_search_tool
from tools.file_ops import read_file_tool, write_file_tool
from tools.shell_tool import shell_command_tool
from tools.email_tool import send_email_tool
from tools.telegram_tool import send_telegram_tool
from tools.memory_tools import remember_fact_tool, recall_facts_tool
from tools.scheduler_tool import schedule_reminder_tool
from tools.audit_tool import query_history_tool
from tools.screen_record_tool import start_screen_recording, stop_screen_recording, get_recording_status, read_screen
from tools.desktop_control_tool import (
    get_screen_info, get_clipboard_text, list_windows, execute_gui_sequence,
)
from tools.self_improve_tool import analyze_agent_performance, get_current_system_prompt
from tools.tool_creator_tool import create_new_tool
from tools.prompt_editor_tool import read_system_prompt, update_system_prompt
from tools.self_reflect_schedule_tool import configure_self_reflection

# === BEGIN AGENT-CREATED TOOLS ===


def get_all_tools():
    return [
        python_repl_tool,
        web_search_tool,
        read_file_tool,
        write_file_tool,
        shell_command_tool,
        send_email_tool,
        send_telegram_tool,
        remember_fact_tool,
        recall_facts_tool,
        schedule_reminder_tool,
        query_history_tool,
        start_screen_recording,
        stop_screen_recording,
        get_recording_status,
        read_screen,
        get_screen_info,
        get_clipboard_text,
        list_windows,
        execute_gui_sequence,
        analyze_agent_performance,
        get_current_system_prompt,
        create_new_tool,
        read_system_prompt,
        update_system_prompt,
        configure_self_reflection,
    ]
