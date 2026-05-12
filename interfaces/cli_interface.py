import asyncio

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table

from audit.store import query_events, list_sessions
from config import settings
from event_bus import EventBus
from events import Event, ResponseEvent

console = Console()

_HISTORY_HELP = (
    "Usage: /history [tools|sessions|session <id>|all]\n"
    "  /history           — last 20 events in current session\n"
    "  /history tools     — tool calls only\n"
    "  /history sessions  — list all sessions\n"
    "  /history session <id> — events for a specific session\n"
    "  /history all       — last 20 events across all sessions"
)


def _render_events(rows: list[dict], title: str) -> None:
    if not rows:
        console.print("[dim]No events found.[/dim]")
        return
    t = Table(title=title, show_lines=False, highlight=True)
    t.add_column("Time", style="dim", width=19, no_wrap=True)
    t.add_column("Type", width=16)
    t.add_column("Source", width=20)
    t.add_column("Content")
    for row in reversed(rows):
        ts = (row["timestamp"] or "")[:19].replace("T", " ")
        content = (row["content"] or "")
        if len(content) > 100:
            content = content[:100] + "…"
        t.add_row(ts, row["event_type"], row["source"] or "-", content)
    console.print(t)


def _handle_history_command(line: str) -> bool:
    """Return True if the line was a /history command (handled here, skip event bus)."""
    if not line.startswith("/history"):
        return False

    parts = line.split(maxsplit=2)
    sub = parts[1] if len(parts) > 1 else ""

    if sub == "sessions":
        rows = list_sessions(settings.audit_db_path)
        if not rows:
            console.print("[dim]No sessions recorded yet.[/dim]")
        else:
            t = Table(title="Sessions", show_lines=False)
            t.add_column("Session ID", style="cyan")
            t.add_column("Started", style="dim", width=19)
            t.add_column("Interface", width=10)
            t.add_column("LLM Provider", width=14)
            t.add_column("Events", justify="right")
            for r in rows:
                t.add_row(
                    r["session_id"],
                    (r["started_at"] or "")[:19].replace("T", " "),
                    r["interface"] or "-",
                    r["llm_provider"] or "-",
                    str(r["event_count"]),
                )
            console.print(t)

    elif sub == "tools":
        rows = query_events(settings.audit_db_path, session_id=settings.session_id, event_type="tool_call", limit=20)
        _render_events(rows, f"Tool Calls — session: {settings.session_id}")

    elif sub == "session" and len(parts) == 3:
        sid = parts[2].strip()
        rows = query_events(settings.audit_db_path, session_id=sid, limit=20)
        _render_events(rows, f"Events — session: {sid}")

    elif sub == "all":
        rows = query_events(settings.audit_db_path, limit=20)
        _render_events(rows, "All Sessions — last 20 events")

    elif sub in ("", "help"):
        if sub == "help":
            console.print(_HISTORY_HELP)
        else:
            rows = query_events(settings.audit_db_path, session_id=settings.session_id, limit=20)
            _render_events(rows, f"Events — session: {settings.session_id}")

    else:
        console.print(f"[yellow]Unknown /history subcommand.[/yellow]\n{_HISTORY_HELP}")

    return True


async def cli_producer(
    event_bus: EventBus,
    response_ready: asyncio.Event,
    pause_for_confirmation: asyncio.Event,
    confirmation_response_queue: asyncio.Queue,
) -> None:
    """Read user input; show spinner while the agent is working.

    When a confirmation prompt arrives (pause_for_confirmation is set by
    cli_consumer), the spinner stops, the user types yes/no, and the answer
    is placed on confirmation_response_queue for confirmation_handler to pick up.
    """
    loop = asyncio.get_event_loop()

    def read_line() -> str:
        return console.input("\n[bold blue]You:[/bold blue] ").strip()

    while True:
        user_input = await loop.run_in_executor(None, read_line)

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "bye"):
            console.print("[dim]Goodbye.[/dim]")
            return
        if _handle_history_command(user_input):
            continue

        event = Event(
            type="user_message",
            user_id="cli",
            source="cli",
            content=user_input,
        )
        response_ready.clear()
        await event_bus.put_input(event)

        # Show spinner until final response arrives, pausing for any confirmations.
        while not response_ready.is_set():
            if pause_for_confirmation.is_set():
                # Terminal is needed for the confirmation prompt — skip spinner,
                # read the user's yes/no, and hand it to confirmation_handler.
                answer = await loop.run_in_executor(
                    None,
                    lambda: console.input("[bold yellow]→ Approve? (yes/no):[/bold yellow] ").strip(),
                )
                await confirmation_response_queue.put(answer)
                pause_for_confirmation.clear()
                # Resume the outer loop; spinner will show again while agent continues.
                continue

            resp_task = asyncio.create_task(response_ready.wait())
            conf_task = asyncio.create_task(pause_for_confirmation.wait())

            with Live(
                Spinner("dots", text="[dim]Thinking…[/dim]"),
                console=console,
                refresh_per_second=12,
                transient=True,
            ):
                _, pending = await asyncio.wait(
                    {resp_task, conf_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )

            for task in pending:
                task.cancel()


async def cli_consumer(
    event_bus: EventBus,
    response_ready: asyncio.Event,
    pause_for_confirmation: asyncio.Event,
) -> None:
    """Display responses and confirmation prompts from the event bus."""
    while True:
        event = await event_bus.get_output()

        if event.dest != "cli":
            continue

        if event.type == "confirmation_request":
            # Print the prompt and signal cli_producer to stop the spinner
            # and read the user's answer.
            console.print(Panel(
                f"[yellow]{event.content}[/yellow]",
                title="[bold yellow]⚠  CONFIRMATION REQUIRED[/bold yellow]",
                border_style="yellow",
            ))
            pause_for_confirmation.set()

        elif event.type == "reminder_fired":
            console.print(Panel(
                f"[bold yellow]{event.content}[/bold yellow]",
                title="[yellow] REMINDER[/yellow]",
                border_style="yellow",
            ))

        else:
            console.print(f"\n[bold green]Agent:[/bold green] {event.content}")
            # Only mark response complete for actual agent/guardrail messages,
            # not for intermediate guardrail feedback that arrives before the
            # agent finishes all its tool calls.
            if event.source == "agent":
                response_ready.set()
