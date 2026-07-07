from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

import httpx
from openai import OpenAI


class EmbeddingClient(Protocol):
    dimensions: int

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...

    def embed_query(self, text: str) -> list[float]:
        ...


class HashEmbeddingClient:
    def __init__(self, dimensions: int = 256):
        self.dimensions = dimensions

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in _tokens(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            vector[index] += 1.0
        return _normalize(vector)


class OpenAIEmbeddingClient:
    def __init__(self, api_key: str, base_url: str, model: str, dimensions: int = 1536):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.dimensions = dimensions

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self.client.embeddings.create(model=self.model, input=texts)
        return [item.embedding for item in response.data]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]


class OllamaEmbeddingClient:
    def __init__(self, base_url: str, model: str, dimensions: int):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.dimensions = dimensions

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        try:
            response = httpx.post(
                f"{self.base_url}/api/embed",
                json={"model": self.model, "input": texts},
                timeout=120,
            )
            response.raise_for_status()
            embeddings = parse_ollama_embeddings(response.json())
        except httpx.HTTPError:
            embeddings = [self._embed_legacy(text) for text in texts]

        for embedding in embeddings:
            if len(embedding) != self.dimensions:
                raise ValueError(
                    f"Ollama returned dimension {len(embedding)}, expected {self.dimensions}. "
                    "Update RAG_EMBED_DIMENSIONS to match the model."
                )
        return embeddings

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]

    def _embed_legacy(self, text: str) -> list[float]:
        response = httpx.post(
            f"{self.base_url}/api/embeddings",
            json={"model": self.model, "prompt": text},
            timeout=120,
        )
        response.raise_for_status()
        return parse_ollama_embeddings(response.json())[0]


def parse_ollama_embeddings(response: dict) -> list[list[float]]:
    if "embeddings" in response:
        embeddings = response["embeddings"]
        if isinstance(embeddings, list) and all(isinstance(item, list) for item in embeddings):
            return embeddings
    if "embedding" in response and isinstance(response["embedding"], list):
        return [response["embedding"]]
    raise ValueError("Unsupported Ollama embedding response")


def _tokens(text: str) -> list[str]:
    return re.findall(r"[\w\u4e00-\u9fff]+", text.lower())


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]
