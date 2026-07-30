from __future__ import annotations

from backend.app.ai.ollama_client import OllamaGenerateClient as SharedOllamaGenerateClient
from backend.app.translation.config import (
    LLM_HOST,
    LLM_MODEL,
    LLM_REQUEST_TIMEOUT_SECONDS,
    OLLAMA_HEALTHCHECK_TTL_SECONDS,
)


class OllamaGenerateClient(SharedOllamaGenerateClient):
    def __init__(self, api_url: str, model_name: str):
        super().__init__(
            api_url=api_url,
            model_name=model_name,
            request_timeout_seconds=LLM_REQUEST_TIMEOUT_SECONDS,
            healthcheck_ttl_seconds=OLLAMA_HEALTHCHECK_TTL_SECONDS,
            logger_name="translation.ollama",
        )

    def generate(
        self,
        prompt: str,
        *,
        temperature: float = 0.1,
        max_tokens: int = 1024,
        stop: list[str] | None = None,
    ) -> str:
        return self.generate_text(
            prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            stop=stop,
        )


_cached_client: OllamaGenerateClient | None = None


def get_ollama_client(force_refresh: bool = False) -> OllamaGenerateClient:
    global _cached_client

    if force_refresh or _cached_client is None:
        _cached_client = OllamaGenerateClient(api_url=LLM_HOST, model_name=LLM_MODEL)

    return _cached_client
