import importlib
import pathlib
import sqlite3
import threading
from datetime import datetime, timezone

from langchain.agents import create_agent
from langgraph.checkpoint.sqlite import SqliteSaver

from audit.logger import audit_callback
from config import settings
import tools as _tools_module

_PROMPT_PATH = pathlib.Path(__file__).parent / "prompts" / "system_prompt.md"

# --- Agent holder for hot-reload ---
_agent_lock = threading.Lock()
_current_agent = None


def _load_system_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def get_agent():
    with _agent_lock:
        return _current_agent


def set_agent(new_agent) -> None:
    global _current_agent
    with _agent_lock:
        _current_agent = new_agent


def rebuild_agent() -> None:
    """Reload the tools package and build a fresh agent, then install it atomically."""
    importlib.reload(_tools_module)
    new_agent = build_agent()
    set_agent(new_agent)


def _build_llm():
    provider = settings.llm_provider.lower()
    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.google_api_key,
        )
    if provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
        )
    if provider == "llamacpp":
        if settings.llamacpp_server_url:
            # Server mode: llama.cpp exposes an OpenAI-compatible API
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                base_url=f"{settings.llamacpp_server_url.rstrip('/')}/v1",
                api_key="not-required",
                model="local-model",
            )
        if not settings.llamacpp_model_path:
            raise ValueError(
                "Set LLAMACPP_SERVER_URL (server mode) or LLAMACPP_MODEL_PATH (in-process) "
                "when LLM_PROVIDER=llamacpp"
            )
        from langchain_community.chat_models import ChatLlamaCpp
        return ChatLlamaCpp(
            model_path=settings.llamacpp_model_path,
            n_ctx=settings.llamacpp_n_ctx,
            n_gpu_layers=settings.llamacpp_n_gpu_layers,
            verbose=False,
        )
    from langchain_anthropic import ChatAnthropic
    return ChatAnthropic(
        model=settings.claude_model,
        anthropic_api_key=settings.anthropic_api_key,
        max_tokens=4096,
    )


def build_agent():
    llm = _build_llm()
    tools = _tools_module.get_all_tools()

    conn = sqlite3.connect(settings.memory_db_path, check_same_thread=False)
    checkpointer = SqliteSaver(conn)

    system_prompt = _load_system_prompt().format(
        current_datetime=datetime.now(timezone.utc).isoformat()
    )

    return create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt,
        checkpointer=checkpointer,
    )


def invoke_agent(agent, user_message: str) -> str:
    config = {
        "configurable": {"thread_id": settings.session_id},
        "callbacks": [audit_callback],
    }
    response = agent.invoke(
        {"messages": [{"role": "user", "content": user_message}]},
        config=config,
    )
    content = response["messages"][-1].content
    if isinstance(content, list):
        return "".join(
            block["text"] if isinstance(block, dict) else str(block)
            for block in content
            if not isinstance(block, dict) or block.get("type") == "text"
        )
    return content
