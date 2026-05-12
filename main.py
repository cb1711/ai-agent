import asyncio
import logging

from rich.console import Console
from rich.panel import Panel

# load_dotenv must run before any local imports that read os.getenv
from dotenv import load_dotenv
load_dotenv()

from audit.store import register_session
from config import settings
from event_bus import EventBus
from agent_loop import agent_consumer, scheduler_monitor, confirmation_handler
from scheduler.jobs import start_scheduler, stop_scheduler
from interfaces.cli_interface import cli_producer, cli_consumer

console = Console()


async def main() -> None:
    """Main async entry point: start all components and run until shutdown."""
    console.print(Panel.fit(
        f"[bold green]AI Agent[/bold green]\n"
        f"LLM: [cyan]{settings.llm_provider}[/cyan]  |  "
        f"Session: [cyan]{settings.session_id}[/cyan]\n"
        f"Type [bold]exit[/bold] to quit.",
        border_style="green",
    ))

    # Initialize
    register_session(settings.audit_db_path, settings.session_id, "cli", settings.llm_provider)
    event_bus = EventBus()
    start_scheduler()

    response_ready = asyncio.Event()
    pause_for_confirmation = asyncio.Event()
    confirmation_response_queue: asyncio.Queue = asyncio.Queue()

    # Start all async tasks
    tasks = [
        asyncio.create_task(agent_consumer(event_bus)),
        asyncio.create_task(scheduler_monitor(event_bus)),
        asyncio.create_task(confirmation_handler(event_bus, confirmation_response_queue)),
        asyncio.create_task(cli_producer(event_bus, response_ready, pause_for_confirmation, confirmation_response_queue)),
        asyncio.create_task(cli_consumer(event_bus, response_ready, pause_for_confirmation)),
    ]

    try:
        # Return as soon as any task finishes (cli_producer exits on "exit"/"quit")
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in done:
            exc = t.exception()
            if exc:
                raise exc
    except (KeyboardInterrupt, asyncio.CancelledError):
        console.print("\n[dim]Interrupted.[/dim]")
    finally:
        stop_scheduler()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


def _setup_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    file_handler = logging.FileHandler(settings.log_path, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))

    # Only WARNING+ to stderr so INFO doesn't clutter the Rich terminal output.
    stderr_handler = logging.StreamHandler()
    stderr_handler.setLevel(logging.WARNING)
    stderr_handler.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(file_handler)
    root.addHandler(stderr_handler)

    logging.info("Logging started — session=%s log=%s", settings.session_id, settings.log_path)


def run_cli() -> None:
    """Entry point for CLI. Runs the async event loop."""
    _setup_logging()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[dim]Shutdown.[/dim]")


if __name__ == "__main__":
    run_cli()
