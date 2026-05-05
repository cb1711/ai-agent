from dotenv import load_dotenv
import os

load_dotenv()


class Settings:
    llm_provider: str = os.getenv("LLM_PROVIDER", "claude")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    claude_model: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.2")
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")
    email_smtp_host: str = os.getenv("EMAIL_SMTP_HOST", "smtp.gmail.com")
    email_smtp_port: int = int(os.getenv("EMAIL_SMTP_PORT", "587"))
    email_username: str = os.getenv("EMAIL_USERNAME", "")
    email_password: str = os.getenv("EMAIL_PASSWORD", "")
    email_from: str = os.getenv("EMAIL_FROM", "")
    memory_db_path: str = os.getenv("MEMORY_DB_PATH", "agent_memory.db")
    scheduler_db_path: str = os.getenv("SCHEDULER_DB_PATH", "agent_scheduler.db")
    session_id: str = os.getenv("SESSION_ID", "default")
    max_history_turns: int = int(os.getenv("MAX_HISTORY_TURNS", "20"))


settings = Settings()
