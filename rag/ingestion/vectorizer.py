"""
向量化模块 - 将文本转换为向量嵌入
"""

import os
from typing import Optional
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class Embedding:
    """向量嵌入数据结构"""
    vector: list[float]
    text: str
    model: str

class BaseEmbeddingProvider(ABC):
    """向量提供者基类"""

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        pass

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        pass

class OpenAIEmbedding(BaseEmbeddingProvider):
    """OpenAI 向量嵌入"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "text-embedding-3-small",
        dimensions: int = 1536
    ):
        from openai import OpenAI
        self.client = OpenAI(
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            base_url=base_url
        )
        self.model = model
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        response = self.client.embeddings.create(
            input=text,
            model=self.model,
            dimensions=self.dimensions
        )
        return response.data[0].embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        response = self.client.embeddings.create(
            input=texts,
            model=self.model,
            dimensions=self.dimensions
        )
        return [item.embedding for item in response.data]

class AnthropicEmbedding(BaseEmbeddingProvider):
    """Anthropic 向量嵌入（通过第三方接口或自建服务）"""

    def __init__(self, api_url: str, api_key: Optional[str] = None):
        import httpx
        self.api_url = api_url
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.client = httpx.Client(timeout=30.0)

    def embed(self, text: str) -> list[float]:
        response = self.client.post(
            f"{self.api_url}/embeddings",
            json={"input": text, "model": "claude-embedding"},
            headers={"Authorization": f"Bearer {self.api_key}"}
        )
        response.raise_for_status()
        return response.json()["embedding"]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        response = self.client.post(
            f"{self.api_url}/embeddings",
            json={"input": texts, "model": "claude-embedding"},
            headers={"Authorization": f"Bearer {self.api_key}"}
        )
        response.raise_for_status()
        return response.json()["embeddings"]

class LocalEmbedding(BaseEmbeddingProvider):
    """本地向量嵌入（使用 sentence-transformers）"""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model_name)

    def embed(self, text: str) -> list[float]:
        return self.model.encode(text).tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return self.model.encode(texts).tolist()

class Vectorizer:
    """
    向量化器
    负责将文本块转换为向量嵌入
    """

    def __init__(self, provider: BaseEmbeddingProvider):
        self.provider = provider

    def vectorize(self, text: str) -> Embedding:
        """将单个文本向量化"""
        vector = self.provider.embed(text)
        return Embedding(
            vector=vector,
            text=text,
            model=self.provider.__class__.__name__
        )

    def vectorize_batch(self, texts: list[str]) -> list[Embedding]:
        """批量向量化"""
        vectors = self.provider.embed_batch(texts)
        return [
            Embedding(vector=vec, text=text, model=self.provider.__class__.__name__)
            for vec, text in zip(vectors, texts)
        ]

def create_vectorizer(
    provider: str = "openai",
    **kwargs
) -> Vectorizer:
    """
    工厂函数：创建向量化器实例

    Args:
        provider: 提供者类型 ("openai", "openai_compatible", "anthropic", "local")
        **kwargs: 提供者特定参数

    Returns:
        Vectorizer 实例
    """
    providers = {
        "openai": OpenAIEmbedding,
        "openai_compatible": OpenAIEmbedding,
        "anthropic": AnthropicEmbedding,
        "local": LocalEmbedding,
    }

    if provider not in providers:
        raise ValueError(f"不支持的向量提供者: {provider}")

    embedding_provider = providers[provider](**kwargs)
    return Vectorizer(embedding_provider)
