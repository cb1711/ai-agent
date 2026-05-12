from __future__ import annotations

from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler

from audit.store import log_event
from config import settings


class AuditCallbackHandler(BaseCallbackHandler):
    """LangChain callback handler that writes every tool call/result to the audit log."""

    def __init__(self) -> None:
        super().__init__()
        self._run_tool: dict[UUID, str] = {}

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        name = serialized.get("name", "unknown_tool")
        self._run_tool[run_id] = name
        log_event(
            settings.audit_db_path,
            settings.session_id,
            "tool_call",
            source=name,
            content=input_str,
        )

    def on_tool_end(
        self,
        output: Any,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        name = self._run_tool.pop(run_id, "unknown_tool")
        log_event(
            settings.audit_db_path,
            settings.session_id,
            "tool_result",
            source=name,
            content=str(output),
        )

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        name = self._run_tool.pop(run_id, "unknown_tool")
        log_event(
            settings.audit_db_path,
            settings.session_id,
            "tool_error",
            source=name,
            content=str(error),
        )


# Singleton shared by agent_loop and agent invoke
audit_callback = AuditCallbackHandler()


def log_user_message(content: str, source: str = "cli") -> None:
    log_event(settings.audit_db_path, settings.session_id, "user_message", source=source, content=content)


def log_agent_response(content: str) -> None:
    log_event(settings.audit_db_path, settings.session_id, "agent_response", source="agent", content=content)


def log_guardrail_block(label: str, snippet: str, stage: str = "input") -> None:
    log_event(
        settings.audit_db_path,
        settings.session_id,
        "guardrail_block",
        source=f"guardrail:{stage}",
        content=snippet,
        metadata={"label": label},
    )


def log_confirmation(action_label: str, details: str, approved: bool, dest: str) -> None:
    log_event(
        settings.audit_db_path,
        settings.session_id,
        "confirmation",
        source="guardrail",
        content=action_label,
        metadata={"details": details[:300], "approved": approved, "dest": dest},
    )
