import sqlite3
from datetime import datetime, timezone

from langchain.agents import create_agent
from langgraph.checkpoint.sqlite import SqliteSaver

from config import settings
from tools import get_all_tools

SYSTEM_PROMPT = """You are a helpful AI assistant with access to powerful tools.

Capabilities:
- Remember and recall facts across sessions (use memory tools proactively)
- Search the web for current information
- Execute Python code for calculations and data processing
- Read and write files on the local filesystem
- Run shell commands
- Send emails and Telegram messages
- Schedule future reminders that appear in this terminal

Guidelines:
- When the user asks you to remember something, always use the remember_fact_tool
- Before answering questions about things you may have been told, use recall_facts_tool
- When scheduling reminders, always include the exact ISO 8601 datetime with timezone offset
- For emails/Telegram, confirm what you sent and to whom

Current date/time (UTC): {current_datetime}
"""


def _build_llm():
    if settings.llm_provider.lower() == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
        )
    else:
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=settings.claude_model,
            anthropic_api_key=settings.anthropic_api_key,
            max_tokens=4096,
        )


def build_agent():
    llm = _build_llm()
    tools = get_all_tools()

    conn = sqlite3.connect(settings.memory_db_path, check_same_thread=False)
    checkpointer = SqliteSaver(conn)

    system_prompt = SYSTEM_PROMPT.format(
        current_datetime=datetime.now(timezone.utc).isoformat()
    )

    return create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt,
        checkpointer=checkpointer,
    )


def invoke_agent(agent, user_message: str) -> str:
    config = {"configurable": {"thread_id": settings.session_id}}
    response = agent.invoke(
        {"messages": [{"role": "user", "content": user_message}]},
        config=config,
    )
    return response["messages"][-1].content
