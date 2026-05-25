import json
import os
from typing import Any

import anthropic
from pydantic import BaseModel

from .schemas import LLMConfig


class LLMClient:
    def __init__(self, config: LLMConfig):
        self.config = config
        self.provider = config.provider

        if config.provider == "claude":
            kwargs = {"api_key": config.api_key}
            if config.base_url:
                kwargs["base_url"] = config.base_url
            self._client = anthropic.Anthropic(**kwargs)

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        return self._chat_claude(system_prompt, user_prompt)

    def _chat_claude(self, system_prompt: str, user_prompt: str) -> str:
        resp = self._client.messages.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        for block in resp.content:
            if hasattr(block, "text") and block.text.strip():
                return self._extract_json(block.text)
        raise ValueError(f"响应中无文本内容: {[type(b).__name__ for b in resp.content]}")

    @staticmethod
    def _extract_json(text: str) -> str:
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

    def analyze(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[BaseModel],
        retries: int = 2,
    ) -> BaseModel:
        last_error: str | None = None
        for attempt in range(retries + 1):
            try:
                raw = self.chat(system_prompt, user_prompt)
                data = json.loads(raw)
                return response_model.model_validate(data)
            except (json.JSONDecodeError, Exception) as e:
                last_error = str(e)
                if attempt < retries:
                    user_prompt = (
                        user_prompt
                        + f"\n\n上次输出的JSON解析失败：{last_error}\n请确保返回严格符合Schema的JSON。"
                    )
        raise ValueError(f"LLM响应解析失败（已重试{retries}次）: {last_error}")
