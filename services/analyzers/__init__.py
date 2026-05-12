from abc import ABC, abstractmethod


class VideoAnalyzer(ABC):
    """Analyze a sequence of screen-recording frames and return a text description."""

    @abstractmethod
    def analyze(self, frames: list[str], frame_format: str = "png", prompt: str = "") -> str:
        """frames: list of base64-encoded image strings.
        frame_format: 'jpeg' or 'png'.
        prompt: override the default analysis prompt. Returns analysis text."""
        ...

    @staticmethod
    def from_settings() -> "VideoAnalyzer":
        """Factory: return the analyzer backend configured in settings."""
        from config import settings
        provider = settings.video_analysis_provider.lower()
        if provider == "ollama":
            from services.analyzers.ollama_analyzer import OllamaAnalyzer
            return OllamaAnalyzer()
        if provider == "llamacpp":
            from services.analyzers.llamacpp_analyzer import LlamaCppAnalyzer
            return LlamaCppAnalyzer()
        from services.analyzers.claude_analyzer import ClaudeAnalyzer
        return ClaudeAnalyzer()
