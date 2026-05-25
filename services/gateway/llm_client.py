"""
LLM 客户端 - 支持 OpenAI 兼容接口（mimo、DeepSeek、Moonshot 等）
"""

import os
from typing import Optional
from openai import OpenAI

class LLMClient:
    """
    LLM 客户端
    支持所有 OpenAI 兼容接口
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ):
        self.client = OpenAI(
            api_key=api_key or os.getenv("LLM_API_KEY"),
            base_url=base_url or os.getenv("LLM_API_BASE")
        )
        self.model = model or os.getenv("LLM_MODEL", "mimo-v2.5-pro")

    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> str:
        """非流式对话"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content

    def chat_stream(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 1000
    ):
        """流式对话"""
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True
        )
        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

def get_llm_client() -> LLMClient:
    """获取 LLM 客户端实例"""
    return LLMClient()
