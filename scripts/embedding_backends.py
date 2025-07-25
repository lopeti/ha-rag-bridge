from __future__ import annotations

import os
import time
from typing import List


import httpx
import openai
from openai import RateLimitError  # correct import

from ha_rag_bridge.logging import get_logger

logger = get_logger(__name__)


class BaseEmbeddingBackend:
    """Abstract embedding backend interface."""

    DIMENSION: int

    def embed(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError


class LocalBackend(BaseEmbeddingBackend):
    """Embed texts locally using SentenceTransformers."""

    DIMENSION = 384

    def __init__(self) -> None:
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")

    def embed(self, texts: List[str]) -> List[List[float]]:
        embeddings = self.model.encode(
            texts,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return [e.tolist() for e in embeddings]


class OpenAIBackend(BaseEmbeddingBackend):
    """Embed texts using the OpenAI API."""

    DIMENSION = 1536

    def __init__(self) -> None:
        self.client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    def embed(self, texts: List[str]) -> List[List[float]]:
        model = "text-embedding-3-large"
        # Retry indefinitely on rate limits or quota errors, sleeping based on Retry-After or fixed 60s
        while True:
            try:
                resp = self.client.embeddings.create(model=model, input=texts)
                return [item.embedding for item in resp.data]  # type: ignore[index]
            except RateLimitError as exc:
                retry_after = 60
                if hasattr(exc, 'headers') and exc.headers.get('Retry-After'):
                    try:
                        retry_after = int(exc.headers['Retry-After'])
                    except ValueError:
                        pass
                logger.warning("rate limit exceeded, sleeping", retry_after=retry_after)
                time.sleep(retry_after)
            except Exception as exc:
                msg = str(exc).lower()
                if 'quota' in msg:
                    retry_after = 60
                    headers = getattr(exc, 'headers', {}) or {}
                    if headers.get('Retry-After'):
                        try:
                            retry_after = int(headers['Retry-After'])
                        except ValueError:
                            pass
                    logger.warning("quota exceeded, sleeping", retry_after=retry_after)
                    time.sleep(retry_after)
                    continue
                # Other errors are fatal
                logger.error("embedding error", error=str(exc))
                raise


class GeminiBackend(BaseEmbeddingBackend):
    MODEL_NAME = "gemini-embedding-001"
    DIMENSION = int(os.getenv("GEMINI_OUTPUT_DIM", 1536))

    def __init__(self) -> None:
        self.api_key = os.environ["GEMINI_API_KEY"]

    def _post(self, payload: dict) -> dict:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.MODEL_NAME}:embedContent?key={self.api_key}"
        )
        resp = httpx.post(url, json=payload)
        return resp.json()

    def embed(self, texts: List[str]) -> List[List[float]]:
        logger.info(
            "Gemini embedding request", count=len(texts), dim=self.DIMENSION, texts=texts
        )
        results: List[List[float]] = []
        for text in texts:
            try:
                data = self._post({"content": {"parts": [{"text": text}]}})
                values = data.get("embeddings", [{}])[0].get("values", [])
                results.append(values)
            except Exception as exc:  # pragma: no cover - network errors
                logger.error("Gemini embedding error", error=str(exc))
                results.append([])
        return results


def get_backend(name: str) -> BaseEmbeddingBackend:
    name = name.lower()
    if name == "openai":
        return OpenAIBackend()
    if name == "gemini":
        return GeminiBackend()
    return LocalBackend()
