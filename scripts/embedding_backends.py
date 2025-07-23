from __future__ import annotations

import os
import time
from typing import List

import httpx
import openai

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
        for attempt in range(3):
            try:
                resp = self.client.embeddings.create(model=model, input=texts)
                return [item.embedding for item in resp.data]  # type: ignore[index]
            except Exception as exc:  # pragma: no cover - network errors
                if "quota" in str(exc).lower() and model != "text-embedding-3-small":
                    logger.warning(
                        "quota exceeded", action="fallback", model="small"
                    )
                    model = "text-embedding-3-small"
                    continue

                if attempt == 2:
                    raise
                wait = 2**attempt
                logger.warning(
                    "embedding retry", wait_s=wait, error=str(exc)
                )
                time.sleep(wait)

        return [[] for _ in texts]


class GeminiBackend(BaseEmbeddingBackend):
    MODEL_NAME = "gemini-embedding-001"
    DIMENSION = int(os.getenv("GEMINI_OUTPUT_DIM", 1536))

    def __init__(self) -> None:
        self.api_key = os.environ["GEMINI_API_KEY"]
        self.base_url = os.getenv(
            "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com"
        )

    def embed(self, texts: List[str]) -> List[List[float]]:
        logger.info("Gemini embedding request", count=len(texts), dim=self.DIMENSION)
        response = httpx.post(
            f"{self.base_url}/v1beta/models/{self.MODEL_NAME}:embedText",
            headers={"x-goog-api-key": self.api_key},
            json={
                "texts": texts,
                "task_type": "RETRIEVAL_DOCUMENT",
                "output_dimensionality": self.DIMENSION,
            },
            timeout=30,
        )
        logger.info("Gemini embedding response", status_code=response.status_code, text=response.text[:500])
        rsp = response.json()
        if "embeddings" not in rsp:
            logger.error("Gemini response missing 'embeddings'", response=rsp)
            raise RuntimeError(f"Gemini API error: {rsp}")
        return [row["values"] for row in rsp["embeddings"]]


def get_backend(name: str) -> BaseEmbeddingBackend:
    name = name.lower()
    if name == "openai":
        return OpenAIBackend()
    if name == "gemini":
        return GeminiBackend()
    return LocalBackend()
