import signal
import sys

# load_dotenv must run before any local imports that read os.getenv
from dotenv import load_dotenv
load_dotenv()

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner

from config import settings
from scheduler.jobs import reminder_queue, start_scheduler, stop_scheduler
from agent import build_agent, invoke_agent

console = Console()


def _handle_sigint(sig, frame):
    console.print("\n[dim]Interrupted. Type 'exit' to quit.[/dim]")


signal.signal(signal.SIGINT, _handle_sigint)


def drain_reminders() -> None:
    while not reminder_queue.empty():
        msg = reminder_queue.get_nowait()
        console.print(Panel(
            f"[bold yellow]{msg}[/bold yellow]",
            title="[yellow] REMINDER[/yellow]",
            border_style="yellow",
        ))


def run_cli() -> None:
    console.print(Panel.fit(
        f"[bold green]AI Agent[/bold green]\n"
        f"LLM: [cyan]{settings.llm_provider}[/cyan]  |  "
        f"Session: [cyan]{settings.session_id}[/cyan]\n"
        f"Type [bold]exit[/bold] to quit.",
        border_style="green",
    ))

    start_scheduler()

    try:
        agent = build_agent()
    except Exception as e:
        console.print(f"[red]Failed to build agent:[/red] {e}")
        stop_scheduler()
        sys.exit(1)

    while True:
        drain_reminders()

        try:
            user_input = console.input("\n[bold blue]You:[/bold blue] ").strip()
        except EOFError:
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "bye"):
            console.print("[dim]Goodbye.[/dim]")
            break

        with Live(
            Spinner("dots", text="[dim]Thinking...[/dim]"),
            console=console,
            refresh_per_second=10,
            transient=True,
        ):
            try:
                answer = invoke_agent(agent, user_input)
            except Exception as e:
                answer = f"[red]Agent error:[/red] {e}"

        console.print(f"\n[bold green]Agent:[/bold green] {answer}")

    stop_scheduler()


if __name__ == "__main__":
    run_cli()
