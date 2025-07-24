from __future__ import annotations

import os
import time
from typing import List


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
        from google import genai
        self.client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    def embed(self, texts: List[str]) -> List[List[float]]:
        logger.info("Gemini embedding request", count=len(texts), dim=self.DIMENSION, texts=texts)
        # Retry indefinitely on rate limits or quota errors, sleeping based on Retry-After or fixed 60s
        while True:
            try:
                result = self.client.models.embed_content(
                    model=self.MODEL_NAME,
                    contents=texts
                )
                logger.info("Gemini embedding raw response", response=str(result))
                return [emb.values for emb in getattr(result, 'embeddings', [])]
            except Exception as exc:
                # Determine retry delay
                retry_after = 60
                headers = getattr(exc, 'headers', {}) or {}
                if headers.get('Retry-After'):
                    try:
                        retry_after = int(headers['Retry-After'])
                    except ValueError:
                        pass
                msg = str(exc).lower()
                # Retry on rate limit or quota errors
                if 'rate limit' in msg or 'quota' in msg or getattr(exc, 'code', None) == 429:
                    logger.warning("Gemini rate/quota limit exceeded, sleeping", retry_after=retry_after, error=str(exc))
                    time.sleep(retry_after)
                    continue
                # Other errors are fatal, return empty embeddings
                logger.error("Gemini embedding error", error=str(exc))
                return [[] for _ in texts]


def get_backend(name: str) -> BaseEmbeddingBackend:
    name = name.lower()
    if name == "openai":
        return OpenAIBackend()
    if name == "gemini":
        return GeminiBackend()
    return LocalBackend()
