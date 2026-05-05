from tools.code_exec import python_repl_tool
from tools.web_search import web_search_tool
from tools.file_ops import read_file_tool, write_file_tool
from tools.shell_tool import shell_command_tool
from tools.email_tool import send_email_tool
from tools.telegram_tool import send_telegram_tool
from tools.memory_tools import remember_fact_tool, recall_facts_tool
from tools.scheduler_tool import schedule_reminder_tool


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
    ]
