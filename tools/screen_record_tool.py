import base64
import hashlib
import io
import logging
import threading
import time
import uuid
from datetime import datetime, timezone

import mss
import mss.tools
from langchain_core.tools import tool

from config import settings
from guardrails.confirmation_gate import ConfirmationDeniedError, request_confirmation
from tools.screen_context import get_active_app, get_browser_url, is_restricted

logger = logging.getLogger(__name__)

_state: dict = {
    "active": False,
    "stop_event": threading.Event(),
    "thread": None,
    "chunks_sent": 0,
}


def _frame_hash(screenshot, stride: int) -> str:
    """SHA-256 of a strided sample of raw BGRA bytes. No encoding cost; detects changes touching 250+ pixels."""
    return hashlib.sha256(bytes(screenshot.raw[::stride])).hexdigest()


def _encode_frame(screenshot, frame_format: str, jpeg_quality: int) -> bytes:
    """Encode a screenshot to JPEG or PNG bytes."""
    if frame_format == "jpeg":
        from PIL import Image as _PilImage
        img = _PilImage.frombytes("RGB", (screenshot.width, screenshot.height), screenshot.rgb)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=jpeg_quality, optimize=True)
        return buf.getvalue()
    return mss.tools.to_png(screenshot.rgb, screenshot.size)


def _record_loop(chunk_seconds: int) -> None:
    """Background thread: capture frames and publish chunks until stop_event is set."""
    from queue_backends import VideoChunkQueue

    queue = VideoChunkQueue.from_settings()
    sequence = 0
    interval = 1.0 / max(1, settings.screen_record_fps)
    frame_format = settings.screen_record_frame_format
    jpeg_quality = settings.screen_record_jpeg_quality
    dedup_enabled = settings.screen_record_dedup_enabled
    hash_stride = settings.screen_record_dedup_hash_stride

    # Persists across chunk boundaries so the last frame of chunk N suppresses
    # the identical first frame of chunk N+1.
    _last_hash: str | None = None

    try:
        with mss.mss() as sct:
            monitor = sct.monitors[0]  # full virtual screen
            while not _state["stop_event"].is_set():
                chunk_frames: list[bytes] = []
                chunk_start = time.monotonic()

                # Check active app / browser URL once per chunk window.
                app_name = get_active_app()
                logger.info("App name is " + app_name)
                url = get_browser_url(app_name)
                logger.info("Url is " + url)
                logger.info(settings.screen_record_restricted_domains)
                if is_restricted(app_name, url):
                    sequence += 1
                    logger.info(
                        "screen_record: restricted — skipping capture seq=%d app=%r url=%r",
                        sequence, app_name, url,
                    )
                    queue.publish({
                        "event_type": "restricted_access",
                        "chunk_id": str(uuid.uuid4()),
                        "sequence": sequence,
                        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                        "app_name": app_name,
                        "url": url,
                        "frames": [],
                    })
                    time.sleep(chunk_seconds)
                    continue

                while (time.monotonic() - chunk_start) < chunk_seconds:
                    if _state["stop_event"].is_set():
                        break
                    screenshot = sct.grab(monitor)

                    if dedup_enabled:
                        h = _frame_hash(screenshot, hash_stride)
                        if h == _last_hash:
                            logger.debug("screen_record: frame skipped (no change) seq=%d", sequence)
                            time.sleep(interval)
                            continue  # identical frame — skip encoding entirely
                        _last_hash = h

                    chunk_frames.append(_encode_frame(screenshot, frame_format, jpeg_quality))
                    time.sleep(interval)

                sequence += 1  # increment before the guard so sequence stays monotonic
                if not chunk_frames:
                    continue

                # Sample: 1 frame per second, max 20
                total = len(chunk_frames)
                step = max(1, total // min(chunk_seconds, 20))
                sampled = chunk_frames[::step][:20]

                encoded = [base64.b64encode(f).decode() for f in sampled]
                chunk = {
                    "chunk_id": str(uuid.uuid4()),
                    "sequence": sequence,
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "frame_format": frame_format,
                    "frames": encoded,
                }
                queue.publish(chunk)
                _state["chunks_sent"] += 1
                logger.info(
                    "screen_record: published chunk seq=%d frames=%d format=%s",
                    sequence, len(encoded), frame_format,
                )
    except Exception as e:
        logger.error("screen_record loop error: %s", e)
    finally:
        queue.close()
        _state["active"] = False
        logger.info("screen_record: loop exited, total chunks=%d", _state["chunks_sent"])


@tool
def start_screen_recording(chunk_seconds: int = 10) -> str:
    """Start recording the screen. Captures frames continuously and publishes a chunk
    to the video-analysis queue every `chunk_seconds` seconds (default 10).
    Only one recording session can be active at a time."""
    if _state["active"]:
        return "Recording is already active. Call stop_screen_recording first."

    try:
        request_confirmation(
            "Start screen recording",
            f"Capture screen and publish chunks every {chunk_seconds}s to queue '{settings.screen_record_queue_name}'.",
        )
    except ConfirmationDeniedError as e:
        return f"[Cancelled] {e}"

    _state["stop_event"].clear()
    _state["chunks_sent"] = 0
    _state["active"] = True
    t = threading.Thread(target=_record_loop, args=(chunk_seconds,), daemon=True, name="screen-recorder")
    _state["thread"] = t
    t.start()
    logger.info("screen_record: started chunk_seconds=%d fps=%d format=%s dedup=%s",
                chunk_seconds, settings.screen_record_fps,
                settings.screen_record_frame_format, settings.screen_record_dedup_enabled)
    return (
        f"Screen recording started. Chunks of {chunk_seconds}s will be published to "
        f"queue '{settings.screen_record_queue_name}' (backend: {settings.queue_backend}, "
        f"format: {settings.screen_record_frame_format}, dedup: {settings.screen_record_dedup_enabled}). "
        f"Call stop_screen_recording to stop."
    )


@tool
def stop_screen_recording() -> str:
    """Stop the active screen recording session."""
    if not _state["active"]:
        return "No active recording to stop."

    _state["stop_event"].set()
    if _state["thread"]:
        _state["thread"].join(timeout=5)
    sent = _state["chunks_sent"]
    logger.info("screen_record: stopped total_chunks=%d", sent)
    return f"Screen recording stopped. {sent} chunk(s) were published for analysis."


@tool
def get_recording_status() -> str:
    """Return whether screen recording is currently active and how many chunks have been sent."""
    if _state["active"]:
        return f"Recording is ACTIVE. {_state['chunks_sent']} chunk(s) sent so far."
    return f"Recording is INACTIVE. Last session sent {_state['chunks_sent']} chunk(s)."


@tool
def read_screen(question: str = "") -> str:
    """Take a single screenshot and answer a question about it using the configured vision model.
    Provide a specific question to get a focused answer (e.g. 'Is there an error message visible?').
    Leave blank for a general description of what is on screen."""
    from services.analyzers import VideoAnalyzer

    frame_format = settings.screen_record_frame_format
    try:
        with mss.mss() as sct:
            screenshot = sct.grab(sct.monitors[0])
            frame_bytes = _encode_frame(screenshot, frame_format, settings.screen_record_jpeg_quality)
    except Exception as e:
        return f"[Error] Failed to capture screen: {e}"

    try:
        result = VideoAnalyzer.from_settings().analyze(
            [base64.b64encode(frame_bytes).decode()],
            frame_format,
            prompt=question,
        )
    except Exception as e:
        return f"[Error] Vision model failed: {e}"

    logger.info("read_screen: analyzed one frame provider=%s", settings.video_analysis_provider)
    return result
