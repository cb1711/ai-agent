"""Standalone video analysis service.

Run with:
    python -m services.video_analyzer

Reads screen-recording chunks from the configured queue backend, sends frames
to the configured vision model, and appends analysis results to a JSONL log.
"""

import json
import logging
import signal
from datetime import datetime, timezone

from config import settings
from queue_backends import VideoChunkQueue
from services.analyzers import VideoAnalyzer

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("video_analyzer")

def run() -> None:
    logger.info(
        "Starting video analyzer — queue=%s backend=%s provider=%s model=%s log=%s",
        settings.screen_record_queue_name,
        settings.queue_backend,
        settings.video_analysis_provider,
        settings.video_analysis_model,
        settings.analysis_log_path,
    )

    queue = VideoChunkQueue.from_settings()
    analyzer = VideoAnalyzer.from_settings()

    def _handle_signal(sig, frame):
        logger.info("Shutdown signal received (%s) — stopping queue consume", sig)
        queue.stop()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    with open(settings.analysis_log_path, "a", encoding="utf-8") as log_file:
        for chunk in queue.consume():
            try:
                if chunk.get("event_type") == "restricted_access":
                    app = chunk.get("app_name", "unknown")
                    url = chunk.get("url", "")
                    detail = f"{app} — {url}" if url else app
                    entry = {
                        "chunk_id": chunk["chunk_id"],
                        "sequence": chunk["sequence"],
                        "recorded_at": chunk["timestamp_utc"],
                        "analyzed_at": datetime.now(timezone.utc).isoformat(),
                        "event_type": "restricted_access",
                        "app_name": app,
                        "url": url,
                        "frame_count": 0,
                        "analysis": f"[Restricted] Content not captured: {detail}",
                    }
                    logger.info("chunk seq=%d restricted app=%r url=%r", chunk["sequence"], app, url)
                else:
                    frame_format = chunk.get("frame_format", "png")  # default for old chunks
                    analysis = analyzer.analyze(chunk["frames"], frame_format)
                    entry = {
                        "chunk_id": chunk["chunk_id"],
                        "sequence": chunk["sequence"],
                        "recorded_at": chunk["timestamp_utc"],
                        "analyzed_at": datetime.now(timezone.utc).isoformat(),
                        "provider": settings.video_analysis_provider,
                        "model": settings.video_analysis_model,
                        "frame_format": frame_format,
                        "frame_count": len(chunk["frames"]),
                        "analysis": analysis,
                    }
                log_file.write(json.dumps(entry) + "\n")
                log_file.flush()
                if chunk.get("event_type") != "restricted_access":
                    logger.info("chunk seq=%d analyzed (%d frames)", chunk["sequence"], len(chunk["frames"]))
            except Exception as e:
                logger.error("Failed to analyze chunk seq=%s: %s", chunk.get("sequence"), e)

    queue.close()
    logger.info("Video analyzer stopped.")


if __name__ == "__main__":
    run()
