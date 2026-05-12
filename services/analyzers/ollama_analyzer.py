import base64
import logging

import ollama

from config import settings
from services.analyzers import VideoAnalyzer

logger = logging.getLogger(__name__)

_PROMPT = (
    "These are sequential frames captured from a screen recording. "
    "Describe concisely what is happening on the screen — include active applications, "
    "visible content, and any notable user actions you can infer."
)


class OllamaAnalyzer(VideoAnalyzer):
    def __init__(self) -> None:
        self._client = ollama.Client(host=settings.ollama_base_url)
        logger.info("OllamaAnalyzer ready model=%s url=%s", settings.video_analysis_model, settings.ollama_base_url)

    def analyze(self, frames: list[str], frame_format: str = "png", prompt: str = "") -> str:
        # Ollama expects raw bytes for images
        raw_frames = [base64.b64decode(f) for f in frames]
        response = self._client.chat(
            model=settings.video_analysis_model,
            messages=[{
                "role": "user",
                "content": prompt or _PROMPT,
                "images": raw_frames,
            }],
        )
        return response["message"]["content"]
