# AI Agent

An autonomous AI agent built on LangChain and LangGraph with persistent memory, self-improvement, and multi-interface support.

## Features

- **Multi-LLM support** — Claude (Anthropic), Ollama, or llama.cpp
- **Persistent memory** — SQLite-backed conversation checkpointing and fact storage across sessions
- **Multi-interface** — CLI and Telegram, unified through an async event bus
- **Guardrails** — Input sanitization (prompt injection detection), output validation, and human-in-the-loop confirmations for sensitive actions
- **Job scheduling** — APScheduler for reminders and autonomous scheduled prompts
- **Self-improvement** — Agent can analyze its own performance and update its system prompt and tools at runtime
- **Screen & desktop control** — Screen recording, frame capture, GUI automation (mouse/keyboard/window management)
- **Audit logging** — Persistent log of all user messages, agent responses, and guardrail blocks

## Setup

### Requirements

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Install

```bash
uv sync
# or
pip install -e .
```

### Configure

Copy `.env.example` to `.env` (or set environment variables directly):

```bash
# Required for Claude backend
ANTHROPIC_API_KEY=sk-...

# Optional — LLM provider (default: claude)
LLM_PROVIDER=claude          # claude | ollama | llamacpp
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3

# Optional — Telegram interface
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...

# Optional — Queue backend for screen recording (default: memory)
QUEUE_BACKEND=redis           # memory | redis | rabbitmq
REDIS_URL=redis://localhost:6379
```

### Run

```bash
uv run agent
# or
python -m main
```

## Architecture

```
main.py
 └── Event Bus
      ├── CLI Interface         ← terminal input/output
      ├── Telegram Interface    ← bot input/output
      ├── Agent Consumer        ← LangChain agent + tools
      ├── Scheduler Monitor     ← APScheduler jobs
      └── Confirmation Handler  ← human-in-the-loop gate
```

The agent is built in `agent.py` and supports hot-reload — new tools or system prompt changes take effect without restarting.

## Tools

| Tool | Description |
|------|-------------|
| `python_repl_tool` | Execute Python code |
| `web_search_tool` | Search the web |
| `read_file_tool` / `write_file_tool` | Read and write local files |
| `shell_command_tool` | Run shell commands |
| `send_email_tool` | Send emails via SMTP |
| `send_telegram_tool` | Send Telegram messages |
| `remember_fact_tool` / `recall_facts_tool` | Persist and retrieve facts across sessions |
| `schedule_reminder_tool` | Schedule future reminders |
| `query_history_tool` | Query the audit log |
| `start_screen_recording` / `stop_screen_recording` | Record the screen |
| `read_screen` | Capture and interpret screen frames |
| `get_screen_info` / `execute_gui_sequence` | Desktop automation |
| `analyze_agent_performance` | Self-improvement — analyze errors and guardrail blocks |
| `update_system_prompt` | Modify agent instructions at runtime |
| `create_new_tool` | Dynamically build and hot-reload new tools |
| `configure_self_reflection` | Schedule periodic self-improvement analysis |

## Project Structure

```
agent.py                  # Agent builder and hot-reload
agent_loop.py             # Async event consumers
main.py                   # Entry point
config.py                 # Settings from environment
prompts/system_prompt.md  # Agent instructions
tools/                    # All tool implementations
guardrails/               # Input/output safety checks
audit/                    # Audit logging and storage
interfaces/               # CLI and Telegram interfaces
scheduler/                # APScheduler job definitions
queue_backends/           # Memory / Redis / RabbitMQ queues
services/                 # Video analysis (Claude, Ollama, llama.cpp)
event_bus.py              # Async pub/sub event bus
events.py                 # Event type definitions
```
