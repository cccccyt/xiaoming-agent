from typing import Literal

from pydantic import BaseModel


class LLMConfig(BaseModel):
    provider: Literal["claude"] = "claude"
    model: str = "deepseek-v4-pro[1m]"
    temperature: float = 0.2
    max_tokens: int = 4096
    api_key: str = ""
    base_url: str = ""
