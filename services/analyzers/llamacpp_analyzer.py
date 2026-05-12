import logging

from config import settings
from services.analyzers import VideoAnalyzer

logger = logging.getLogger(__name__)

_PROMPT = (
    "These are sequential frames captured from a screen recording. "
    "Describe concisely what is happening on the screen — include active applications, "
    "visible content, and any notable user actions you can infer."
)


class LlamaCppAnalyzer(VideoAnalyzer):
    def __init__(self) -> None:
        if settings.llamacpp_server_url:
            self._mode = "server"
            from openai import OpenAI
            self._client = OpenAI(
                base_url=f"{settings.llamacpp_server_url.rstrip('/')}/v1",
                api_key="not-required",
            )
            logger.info("LlamaCppAnalyzer ready mode=server url=%s", settings.llamacpp_server_url)
        else:
            if not settings.llamacpp_model_path:
                raise ValueError(
                    "Set LLAMACPP_SERVER_URL (server mode) or LLAMACPP_MODEL_PATH (in-process) "
                    "when VIDEO_ANALYSIS_PROVIDER=llamacpp"
                )
            if not settings.llamacpp_mmproj_path:
                raise ValueError("LLAMACPP_MMPROJ_PATH must be set for in-process vision with llamacpp")
            self._mode = "inprocess"
            from llama_cpp import Llama
            from llama_cpp.llama_chat_format import Llava15ChatHandler
            chat_handler = Llava15ChatHandler(
                clip_model_path=settings.llamacpp_mmproj_path,
                verbose=False,
            )
            self._client = Llama(
                model_path=settings.llamacpp_model_path,
                chat_handler=chat_handler,
                n_ctx=settings.llamacpp_n_ctx,
                n_gpu_layers=settings.llamacpp_n_gpu_layers,
                logits_all=True,
                verbose=False,
            )
            logger.info(
                "LlamaCppAnalyzer ready mode=inprocess model=%s mmproj=%s",
                settings.llamacpp_model_path,
                settings.llamacpp_mmproj_path,
            )

    def analyze(self, frames: list[str], frame_format: str = "png", prompt: str = "") -> str:
        content = [
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/{frame_format};base64,{b64}"},
            }
            for b64 in frames
        ]
        content.append({"type": "text", "text": prompt or _PROMPT})

        if self._mode == "server":
            response = self._client.chat.completions.create(
                model="local-model",
                messages=[{"role": "user", "content": content}],
            )
            return response.choices[0].message.content
        else:
            response = self._client.create_chat_completion(
                messages=[{"role": "user", "content": content}]
            )
            return response["choices"][0]["message"]["content"]
