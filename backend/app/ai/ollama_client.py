from __future__ import annotations

import logging
import re
import time
from typing import Any, TypeVar

import requests
from pydantic import BaseModel

HTTP_SESSION = requests.Session()
TModel = TypeVar("TModel", bound=BaseModel)


class OllamaGenerateClient:
    def __init__(
        self,
        *,
        api_url: str,
        model_name: str,
        request_timeout_seconds: int,
        healthcheck_ttl_seconds: int,
        logger_name: str,
    ) -> None:
        self.api_url = api_url
        self.model_name = model_name
        self.request_timeout_seconds = request_timeout_seconds
        self.healthcheck_ttl_seconds = healthcheck_ttl_seconds
        self.logger = logging.getLogger(logger_name)
        self._last_health_check_at = 0.0
        self._last_health_check_result = False

    @property
    def base_url(self) -> str:
        return self.api_url.removesuffix("/api/generate")

    def check_health(self, force: bool = False) -> bool:
        now = time.monotonic()
        if (
            not force
            and self._last_health_check_at
            and now - self._last_health_check_at < self.healthcheck_ttl_seconds
        ):
            return self._last_health_check_result

        try:
            service_response = HTTP_SESSION.get(self.base_url, timeout=5)
            service_response.raise_for_status()

            tags_response = HTTP_SESSION.get(f"{self.base_url}/api/tags", timeout=5)
            tags_response.raise_for_status()
            available_models = [
                model.get("name", "")
                for model in tags_response.json().get("models", [])
            ]
            self._last_health_check_result = any(
                model_name == self.model_name
                or model_name.startswith(f"{self.model_name}:")
                for model_name in available_models
            )
            if not self._last_health_check_result:
                self.logger.error(
                    "Model '%s' not found in Ollama tags: %s",
                    self.model_name,
                    available_models,
                )
        except Exception as error:
            self.logger.error("Ollama health check failed: %s", error)
            self._last_health_check_result = False

        self._last_health_check_at = now
        return self._last_health_check_result

    def generate_text(
        self,
        prompt: str,
        *,
        temperature: float = 0.1,
        max_tokens: int = 1024,
        stop: list[str] | None = None,
    ) -> str:
        if not self.check_health(force=True):
            raise RuntimeError("Ollama is unavailable or the configured model is missing")

        payload: dict[str, Any] = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if stop:
            payload["options"]["stop"] = stop

        response = HTTP_SESSION.post(
            self.api_url,
            json=payload,
            timeout=self.request_timeout_seconds,
        )
        response.raise_for_status()
        result = str(response.json().get("response", "")).strip()
        result = re.sub(r"<think>.*?</think>", "", result, flags=re.DOTALL).strip()
        if not result:
            raise ValueError("Empty response from Ollama")
        return result

    def generate_json(
        self,
        prompt: str,
        *,
        response_model: type[TModel],
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> TModel:
        raw_response = self.generate_text(
            prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        extracted_json = self._extract_json_payload(raw_response)
        return response_model.model_validate_json(extracted_json)

    def _extract_json_payload(self, response_text: str) -> str:
        candidate = response_text.strip()
        fenced_match = re.search(r"```(?:json)?\s*(.*?)\s*```", candidate, re.DOTALL)
        if fenced_match:
            candidate = fenced_match.group(1).strip()

        for open_char, close_char in (("{", "}"), ("[", "]")):
            start_index = candidate.find(open_char)
            end_index = candidate.rfind(close_char)
            if start_index != -1 and end_index != -1 and end_index > start_index:
                return candidate[start_index : end_index + 1]

        raise ValueError("LLM response did not contain a JSON object or array")
