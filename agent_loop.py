import asyncio
import logging
import queue as queue_module

from rich.console import Console

from agent import invoke_agent, build_agent, get_agent, set_agent
from audit.logger import log_user_message, log_agent_response, log_guardrail_block, log_confirmation
from events import Event, ResponseEvent
from scheduler.jobs import task_queue
from guardrails.input_sanitizer import sanitize_input, InputSanitizationError
from guardrails.output_validator import validate_output
from guardrails.confirmation_gate import confirmation_queue, ConfirmationRequest, _current_dest

console = Console()


async def agent_consumer(event_bus) -> None:
    """Consume input events, run the agent, emit responses."""
    set_agent(build_agent())
    loop = asyncio.get_event_loop()

    while True:
        event = await event_bus.get_input()

        if event.type == "user_message":
            logging.info("user_message from=%s content=%.120s", event.source, event.content)
            log_user_message(event.content, source=event.source)
            try:
                sanitize_input(event.content)
            except InputSanitizationError as e:
                logging.warning("guardrail:input blocked label=%s", e.label)
                log_guardrail_block(e.label, event.content[:200], stage="input")
                await event_bus.put_output(ResponseEvent(
                    user_id=event.user_id,
                    content=f"[Blocked] Input flagged for potential prompt injection ({e.label}). Please rephrase.",
                    dest=event.source,
                    source="agent",
                ))
                continue

            # Store originating channel so tools can route confirmation prompts correctly.
            _current_dest.set(event.source)

            logging.info("invoking agent session=%s", event.source)
            current_agent = get_agent()
            response_text = await loop.run_in_executor(
                None, lambda: invoke_agent(current_agent, event.content)
            )
            logging.info("agent response length=%d chars", len(response_text))

            for w in validate_output(response_text):
                logging.warning("guardrail:output label=%s snippet=%.80s", w.label, w.snippet)
                log_guardrail_block(w.label, w.snippet, stage="output")

            log_agent_response(response_text)
            await event_bus.put_output(ResponseEvent(
                user_id=event.user_id,
                content=response_text,
                dest=event.source,
                source="agent",
            ))

        elif event.type == "reminder_fired":
            logging.info("reminder fired dest=%s", event.dest)
            await event_bus.put_output(ResponseEvent(
                user_id=event.user_id,
                content=event.content,
                dest=event.dest,
                source="scheduler",
            ))


async def scheduler_monitor(event_bus) -> None:
    """Drain task_queue and route ScheduledTask objects onto the async event bus."""
    while True:
        try:
            task = task_queue.get(timeout=0.1)
            logging.info("scheduled task type=%s dest=%s", task.task_type, task.dest)
            if task.task_type == "reminder":
                event = ResponseEvent(
                    user_id=task.dest,
                    source="scheduler",
                    content=task.payload["message"],
                    dest=task.dest,
                )
                event.type = "reminder_fired"
                await event_bus.put_input(event)
            elif task.task_type == "agent_prompt":
                await event_bus.put_input(Event(
                    type="user_message",
                    user_id=task.dest,
                    source=task.dest,
                    content=task.payload["prompt"],
                ))
        except queue_module.Empty:
            await asyncio.sleep(0.1)


async def confirmation_handler(
    event_bus,
    confirmation_response_queue: asyncio.Queue,
) -> None:
    """Human-in-the-loop: route approval prompts to the originating interface.

    For each ConfirmationRequest the tool placed on confirmation_queue:
      1. Emit a confirmation_request ResponseEvent to the correct dest (cli, telegram, …).
      2. Await the user's answer from confirmation_response_queue (populated by
         whichever interface consumer/producer handles that dest).
      3. Resolve the Future so the blocked tool thread can proceed or abort.

    This keeps all I/O through the event bus so CLI, Telegram, and any future
    interface work without changes here.
    """
    while True:
        try:
            req: ConfirmationRequest = confirmation_queue.get_nowait()
        except queue_module.Empty:
            await asyncio.sleep(0.05)
            continue

        # Route the prompt to the originating interface.
        prompt = ResponseEvent(
            user_id=req.dest,
            source="guardrail",
            content=(
                f"Action : {req.action_label}\n"
                f"Details: {req.details}\n"
                f"Reply 'yes' to approve or 'no' to cancel."
            ),
            dest=req.dest,
        )
        prompt.type = "confirmation_request"
        await event_bus.put_output(prompt)

        # Block (async) until the interface delivers the user's answer.
        answer = await confirmation_response_queue.get()
        approved = answer.strip().lower() in ("yes", "y")
        logging.info("confirmation action=%s approved=%s dest=%s", req.action_label, approved, req.dest)
        log_confirmation(req.action_label, req.details, approved, req.dest)
        req.future.set_result(approved)

        # Send feedback back through the same interface.
        feedback = ResponseEvent(
            user_id=req.dest,
            source="guardrail",
            content="✓ Approved — proceeding." if approved else "✗ Denied — action cancelled.",
            dest=req.dest,
        )
        await event_bus.put_output(feedback)
