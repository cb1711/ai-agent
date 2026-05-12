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
    # Queue backends
    queue_backend: str              = os.getenv("QUEUE_BACKEND", "redis")
    redis_url: str                  = os.getenv("REDIS_URL", "redis://localhost:6379")
    rabbitmq_url: str               = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost/")
    screen_record_queue_name: str   = os.getenv("SCREEN_RECORD_QUEUE", "screen_chunks")

    # Screen recorder
    screen_record_fps: int               = int(os.getenv("SCREEN_RECORD_FPS", "3"))
    screen_record_chunk_secs: int        = int(os.getenv("SCREEN_RECORD_CHUNK_SECS", "10"))
    screen_record_frame_format: str      = os.getenv("SCREEN_RECORD_FRAME_FORMAT", "jpeg")
    screen_record_jpeg_quality: int      = int(os.getenv("SCREEN_RECORD_JPEG_QUALITY", "85"))
    screen_record_dedup_enabled: bool    = os.getenv("SCREEN_RECORD_DEDUP_ENABLED", "true").lower() == "true"
    screen_record_dedup_hash_stride: int = int(os.getenv("SCREEN_RECORD_DEDUP_HASH_STRIDE", "64"))
    # Comma-separated app names and domains to block from recording.
    # e.g. SCREEN_RECORD_RESTRICTED_APPS=zoom,facetime
    #      SCREEN_RECORD_RESTRICTED_DOMAINS=chase.com,health.gov
    screen_record_restricted_apps: list = [
        a.strip() for a in os.getenv("SCREEN_RECORD_RESTRICTED_APPS", "").split(",") if a.strip()
    ]
    screen_record_restricted_domains: list = [
        d.strip() for d in os.getenv("SCREEN_RECORD_RESTRICTED_DOMAINS", "").split(",") if d.strip()
    ]

    # Desktop / GUI control
    gui_action_pause: float = float(os.getenv("GUI_ACTION_PAUSE", "0.15"))

    # llama.cpp (used by main agent and video analyzer when provider = "llamacpp")
    # LLAMACPP_MMPROJ_PATH is required for vision / video analysis
    llamacpp_server_url: str    = os.getenv("LLAMACPP_SERVER_URL", "")   # e.g. http://127.0.0.1:8080
    llamacpp_model_path: str    = os.getenv("LLAMACPP_MODEL_PATH", "")   # in-process only
    llamacpp_mmproj_path: str   = os.getenv("LLAMACPP_MMPROJ_PATH", "")  # in-process vision only
    llamacpp_n_ctx: int         = int(os.getenv("LLAMACPP_N_CTX", "4096"))
    llamacpp_n_gpu_layers: int  = int(os.getenv("LLAMACPP_N_GPU_LAYERS", "-1"))  # -1 = all on GPU

    # Video analysis
    # VIDEO_ANALYSIS_PROVIDER: "claude", "ollama", or "llamacpp"
    # VIDEO_ANALYSIS_MODEL: e.g. "claude-sonnet-4-6" (claude), "llava" (ollama), unused for llamacpp (path used instead)
    video_analysis_provider: str    = os.getenv("VIDEO_ANALYSIS_PROVIDER", "claude")
    video_analysis_model: str       = os.getenv("VIDEO_ANALYSIS_MODEL", "claude-sonnet-4-6")
    analysis_log_path: str          = os.getenv("ANALYSIS_LOG_PATH", "analysis_results.jsonl")

    self_reflect_interval_hours: int = int(os.getenv("SELF_REFLECT_INTERVAL_HOURS", "24"))

    memory_db_path: str = os.getenv("MEMORY_DB_PATH", "agent_memory.db")
    scheduler_db_path: str = os.getenv("SCHEDULER_DB_PATH", "agent_scheduler.db")
    audit_db_path: str = os.getenv("AUDIT_DB_PATH", "agent_audit.db")
    log_path: str = os.getenv("LOG_PATH", "agent.log")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    session_id: str = os.getenv("SESSION_ID", "default")
    max_history_turns: int = int(os.getenv("MAX_HISTORY_TURNS", "20"))


settings = Settings()
