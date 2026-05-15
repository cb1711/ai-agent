import concurrent.futures
import contextvars
import queue
import threading
from dataclasses import dataclass, field

CONFIRMATION_TIMEOUT = 120  # seconds before auto-deny

# Labels approved at least once this session — never ask again for these.
_approved_lock = threading.Lock()
_approved_labels: set[str] = set()


def _is_approved(label: str) -> bool:
    with _approved_lock:
        return label in _approved_labels


def _remember_approval(label: str) -> None:
    with _approved_lock:
        _approved_labels.add(label)

# Set by agent_consumer before calling invoke_agent so that tools running in
# executor threads can discover which interface originated the request.
# run_in_executor copies the current Context, so the tool thread sees the
# correct value without any extra plumbing.
_current_dest: contextvars.ContextVar[str] = contextvars.ContextVar(
    "current_dest", default="cli"
)


@dataclass
class ConfirmationRequest:
    action_label: str
    details: str
    dest: str                                          # originating interface
    future: concurrent.futures.Future = field(default_factory=concurrent.futures.Future)


# Thread-safe queue: tool threads push requests; confirmation_handler drains it.
confirmation_queue: queue.SimpleQueue[ConfirmationRequest] = queue.SimpleQueue()


class ConfirmationDeniedError(RuntimeError):
    pass


def request_confirmation(action_label: str, details: str) -> None:
    """Called from a tool (sync thread). Blocks until the human approves or denies.

    Discovers the originating interface via _current_dest context var (copied
    from the asyncio task by run_in_executor). Raises ConfirmationDeniedError
    if denied or timed out; the asyncio event loop stays free throughout.

    If the user already approved this action_label once in the current session,
    the prompt is skipped and the call returns immediately.
    """
    if _is_approved(action_label):
        return

    dest = _current_dest.get()
    req = ConfirmationRequest(action_label=action_label, details=details, dest=dest)
    confirmation_queue.put(req)
    try:
        approved = req.future.result(timeout=CONFIRMATION_TIMEOUT)
    except concurrent.futures.TimeoutError:
        raise ConfirmationDeniedError(f"Timed out waiting for confirmation: {action_label}")
    if not approved:
        raise ConfirmationDeniedError(f"User denied: {action_label}")
    _remember_approval(action_label)
