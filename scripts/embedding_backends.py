from __future__ import annotations

import asyncio
import os
import time
from typing import List, Optional


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
                if hasattr(exc, "headers") and exc.headers.get("Retry-After"):
                    try:
                        retry_after = int(exc.headers["Retry-After"])
                    except ValueError:
                        pass
                logger.warning("rate limit exceeded, sleeping", retry_after=retry_after)
                time.sleep(retry_after)
            except Exception as exc:
                msg = str(exc).lower()
                if "quota" in msg:
                    retry_after = 60
                    headers = getattr(exc, "headers", {}) or {}
                    if headers.get("Retry-After"):
                        try:
                            retry_after = int(headers["Retry-After"])
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
    MAX_RETRIES = 3
    RATE_LIMIT = 100  # requests per minute

    def __init__(self) -> None:
        self.api_key = os.environ["GEMINI_API_KEY"]
        self._last_request_time = 0.0
        self._min_interval = 60.0 / self.RATE_LIMIT
        # Use a semaphore to enforce rate limiting across threads/async
        # Initialize with proper type annotation for mypy
        self._semaphore: Optional[asyncio.Semaphore] = None
        try:
            self._semaphore = asyncio.Semaphore(1)
        except RuntimeError:
            # Not in an async context
            pass

    def _post(self, payload: dict) -> dict:
        """Synchronous post request to Gemini API."""
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.MODEL_NAME}:embedContent?key={self.api_key}"
        )
        resp = httpx.post(url, json=payload)
        return resp.json()

    async def _post_async(self, payload: dict) -> dict:
        """Asynchronous post request to Gemini API."""
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.MODEL_NAME}:embedContent?key={self.api_key}"
        )
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload)
            return resp.json()

    def _rate_limit_sync(self) -> None:
        """Apply rate limiting for synchronous calls."""
        now = time.time()
        elapsed = now - self._last_request_time
        wait_time = max(0, self._min_interval - elapsed)
        if wait_time > 0:
            time.sleep(wait_time)
        self._last_request_time = time.time()

    async def _rate_limit_async(self) -> None:
        """Apply rate limiting for async calls."""
        now = time.time()
        elapsed = now - self._last_request_time
        wait_time = max(0, self._min_interval - elapsed)
        if wait_time > 0:
            await asyncio.sleep(wait_time)
        self._last_request_time = time.time()

    def embed(self, texts: List[str]) -> List[List[float]]:
        """Embed texts using Gemini API with rate limiting and retry logic."""
        logger.info(f"Gemini embedding: count={len(texts)}, dim={self.DIMENSION}")

        # Check if we're in an async context
        in_async_context = False
        try:
            asyncio.get_running_loop()
            in_async_context = True
        except RuntimeError:
            # Not in async context, use synchronous version
            pass

        if in_async_context:
            # We're in an async context but being called synchronously
            # Create a new event loop for this thread to prevent blocking
            logger.info("Running Gemini embedding in async-compatible mode")
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(self._embed_async(texts))
            finally:
                loop.close()
        else:
            # Regular synchronous operation
            return self._embed_sync(texts)

    def _embed_sync(self, texts: List[str]) -> List[List[float]]:
        """Synchronous implementation of embed."""
        results: List[List[float]] = []
        failed = 0

        for idx, text in enumerate(texts):
            success = False
            for attempt in range(1, self.MAX_RETRIES + 1):
                # Apply rate limiting
                self._rate_limit_sync()

                try:
                    data = self._post({"content": {"parts": [{"text": text}]}})
                    if "embeddings" in data and data["embeddings"]:
                        values = data["embeddings"][0].get("values", [])
                        results.append(values)
                        success = True
                        break
                    else:
                        if attempt < self.MAX_RETRIES:
                            wait_time = 2**attempt
                            logger.warning(
                                f"Gemini: No embeddings (idx={idx}, attempt={attempt}), retrying in {wait_time}s"
                            )
                            time.sleep(wait_time)
                        else:
                            logger.error(
                                f"Gemini: No embeddings after {self.MAX_RETRIES} attempts (idx={idx})"
                            )
                except Exception as exc:
                    if attempt < self.MAX_RETRIES:
                        wait_time = 2**attempt
                        logger.warning(
                            f"Gemini: error (idx={idx}, attempt={attempt}), retrying in {wait_time}s: {exc}"
                        )
                        time.sleep(wait_time)
                    else:
                        logger.error(
                            f"Gemini: failed after {self.MAX_RETRIES} attempts (idx={idx}): {exc}"
                        )

            if not success:
                results.append([])
                failed += 1

        logger.info(f"Gemini embedding done: total={len(texts)}, failed={failed}")
        return results

    async def _embed_async(self, texts: List[str]) -> List[List[float]]:
        """Asynchronous implementation of embed."""
        results: List[List[float]] = []
        failed = 0

        for idx, text in enumerate(texts):
            success = False
            for attempt in range(1, self.MAX_RETRIES + 1):
                # Apply rate limiting with semaphore if available
                if self._semaphore is not None:
                    async with self._semaphore:
                        await self._rate_limit_async()
                else:
                    await self._rate_limit_async()

                try:
                    data = await self._post_async(
                        {"content": {"parts": [{"text": text}]}}
                    )
                    if "embeddings" in data and data["embeddings"]:
                        values = data["embeddings"][0].get("values", [])
                        results.append(values)
                        success = True
                        break
                    else:
                        if attempt < self.MAX_RETRIES:
                            wait_time = 2**attempt
                            logger.warning(
                                f"Gemini: No embeddings (idx={idx}, attempt={attempt}), retrying in {wait_time}s"
                            )
                            await asyncio.sleep(wait_time)
                        else:
                            logger.error(
                                f"Gemini: No embeddings after {self.MAX_RETRIES} attempts (idx={idx})"
                            )
                except Exception as exc:
                    if attempt < self.MAX_RETRIES:
                        wait_time = 2**attempt
                        logger.warning(
                            f"Gemini: error (idx={idx}, attempt={attempt}), retrying in {wait_time}s: {exc}"
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(
                            f"Gemini: failed after {self.MAX_RETRIES} attempts (idx={idx}): {exc}"
                        )

            if not success:
                results.append([])
                failed += 1

        logger.info(f"Gemini embedding done: total={len(texts)}, failed={failed}")
        return results


def get_backend(name: str) -> BaseEmbeddingBackend:
    name = name.lower()
    if name == "openai":
        return OpenAIBackend()
    if name == "gemini":
        return GeminiBackend()
    return LocalBackend()
