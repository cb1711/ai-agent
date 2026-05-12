import logging

import anthropic

from config import settings
from services.analyzers import VideoAnalyzer

logger = logging.getLogger(__name__)

_PROMPT = (
    "These are sequential frames captured from a screen recording. "
    "Describe concisely what is happening on the screen — include active applications, "
    "visible content, and any notable user actions you can infer."
)


class ClaudeAnalyzer(VideoAnalyzer):
    def __init__(self) -> None:
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        logger.info("ClaudeAnalyzer ready model=%s", settings.video_analysis_model)

    def analyze(self, frames: list[str], frame_format: str = "png", prompt: str = "") -> str:
        media_type = f"image/{frame_format}"  # "image/jpeg" or "image/png"
        content: list[dict] = []
        for b64 in frames:
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": b64,
                },
            })
        content.append({"type": "text", "text": prompt or _PROMPT})

        response = self._client.messages.create(
            model=settings.video_analysis_model,
            max_tokens=1024,
            messages=[{"role": "user", "content": content}],
        )
        return response.content[0].text
