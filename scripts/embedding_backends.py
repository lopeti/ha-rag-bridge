from __future__ import annotations

import asyncio
import os
import time
from typing import List, Optional

import openai
from openai import RateLimitError  # correct import
import httpx

try:
    import google.genai as genai
except Exception:  # pragma: no cover - optional dependency
    genai = None

from ha_rag_bridge.logging import get_logger

logger = get_logger(__name__)


class BaseEmbeddingBackend:
    """Abstract embedding backend interface."""

    DIMENSION: int

    def embed(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError


class LocalBackend(BaseEmbeddingBackend):
    """Embed texts locally using SentenceTransformers optimized for CPU."""

    DIMENSION = 384
    _MODEL = None

    def __init__(self) -> None:
        from sentence_transformers import SentenceTransformer
        import os
        import torch

        # Model selection based on environment variable or default to best multilingual model
        model_name = os.getenv(
            "SENTENCE_TRANSFORMER_MODEL", "paraphrase-multilingual-mpnet-base-v2"
        )

        # CPU optimization for VM environment
        device = "cpu"

        # Set optimal CPU threads for embedding (only if not already set)
        cpu_threads = int(
            os.getenv("EMBEDDING_CPU_THREADS", "4")
        )  # Conservative default for VM

        # Only set threads if not already configured
        try:
            torch.set_num_threads(cpu_threads)
            torch.set_num_interop_threads(cpu_threads)
        except RuntimeError:
            # Threads already set, skip
            pass

        if LocalBackend._MODEL is None:
            print(f"Loading SentenceTransformer model: {model_name} on {device}")
            print(f"CPU threads: {cpu_threads}")
            LocalBackend._MODEL = SentenceTransformer(model_name, device=device)
            
            # Dynamic dimension detection based on model (only once)
            sample_embedding = LocalBackend._MODEL.encode(
                ["test"], convert_to_numpy=True, normalize_embeddings=True
            )
            LocalBackend.DIMENSION = len(sample_embedding[0])
            print(f"Model dimension: {LocalBackend.DIMENSION}")
            
        self.model = LocalBackend._MODEL

    def embed(self, texts: List[str]) -> List[List[float]]:
        embeddings = self.model.encode(
            texts,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return [e.tolist() for e in embeddings]


class EnhancedLocalBackend(LocalBackend):
    """Enhanced Local Backend with instruction templates and query/document encoding split."""
    
    def __init__(self) -> None:
        super().__init__()
        
        # Import config here to avoid circular imports
        try:
            from ha_rag_bridge.config import get_settings
            self.settings = get_settings()
            self.use_instruction_templates = self.settings.use_instruction_templates
            self.query_prefix = self.settings.query_prefix_template
            self.document_prefix = self.settings.document_prefix_template
        except ImportError:
            # Fallback if config not available
            self.use_instruction_templates = True
            self.query_prefix = "query: "
            self.document_prefix = "passage: "
    
    def embed_query(self, text: str) -> List[float]:
        """Query-specific embedding with instruction template."""
        if self.use_instruction_templates:
            prefixed_text = f"{self.query_prefix}{text}"
        else:
            prefixed_text = text
            
        return self.embed([prefixed_text])[0]
    
    def embed_document(self, text: str) -> List[float]:
        """Document-specific embedding with instruction template.""" 
        if self.use_instruction_templates:
            prefixed_text = f"{self.document_prefix}{text}"
        else:
            prefixed_text = text
            
        return self.embed([prefixed_text])[0]
    
    def embed_multi_query(self, queries: List[str]) -> List[List[float]]:
        """Batch multi-query embedding with query prefix."""
        if self.use_instruction_templates:
            prefixed_queries = [f"{self.query_prefix}{q}" for q in queries]
        else:
            prefixed_queries = queries
            
        return self.embed(prefixed_queries)
    
    def embed_multi_document(self, documents: List[str]) -> List[List[float]]:
        """Batch multi-document embedding with document prefix."""
        if self.use_instruction_templates:
            prefixed_docs = [f"{self.document_prefix}{d}" for d in documents]
        else:
            prefixed_docs = documents
            
        return self.embed(prefixed_docs)


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
        # Configure GenAI client if available, otherwise fall back to HTTP API
        api_key = os.environ["GEMINI_API_KEY"]
        use_sdk = os.getenv("GEMINI_USE_SDK", "0").lower() in ("1", "true", "yes")
        if use_sdk and genai is not None:
            self.client = genai.Client(api_key=api_key)
            self._api_key = None
        else:
            self.client = None
            self._api_key = api_key

        # Rate limiting követéséhez
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

    def _embed_content(self, text: str) -> dict:
        """Synchronously embed a single text using Google GenAI SDK or HTTP."""
        try:
            if self.client is None:
                resp = httpx.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{self.MODEL_NAME}:embedContent",
                    params={"key": self._api_key},
                    json={"content": {"parts": [{"text": text}]}},
                )
                result = resp.json()
                result["_status_code"] = getattr(resp, "status_code", 200)
            else:
                result = self.client.models.embed_content(
                    model=self.MODEL_NAME, contents=text
                )

            # --- extract embedding vector regardless of response shape ---
            def _extract_values(resp: dict | object) -> list[float] | None:
                # 1) régi/lapos {"values": [...]}
                if isinstance(resp, dict) and "values" in resp:
                    return resp["values"]

                # 2) új {"embedding": {"values": [...]}}
                if isinstance(resp, dict) and resp.get("embedding"):
                    return resp["embedding"].get("values")

                # 3) top-level {"embeddings": [{"values": [...] }]}
                if isinstance(resp, dict) and resp.get("embeddings"):
                    first = resp["embeddings"][0]
                    if isinstance(first, dict) and "values" in first:
                        return first["values"]

                # 4) predictions listás
                if isinstance(resp, dict) and resp.get("predictions"):
                    emb = resp["predictions"][0].get("embedding", {})
                    return emb.get("values")

                # 5) SDK-objektum (result.embeddings[0].values)
                if hasattr(resp, "embeddings") and resp.embeddings:
                    return resp.embeddings[0].values

                return None

            values = _extract_values(result)
            if values:
                return {"_status_code": 200, "embeddings": [{"values": values}]}

            logger.error("Gemini API unexpected response format: %s", result)
            return {
                "_status_code": 200,
                "error": {"message": "No embedding in response"},
            }
        except Exception as e:
            if (
                "quota" in str(e).lower()
                or "rate" in str(e).lower()
                or "limit" in str(e).lower()
            ):
                # Rate limit vagy quota error esetén 429-et adunk vissza
                logger.error(f"Gemini API quota or rate limit exceeded: {str(e)}")
                return {"_status_code": 429, "error": {"message": str(e)}}
            else:
                # Egyéb hiba esetén 500-as kód
                logger.error(f"Gemini API error: {str(e)}")
                return {"_status_code": 500, "error": {"message": str(e)}}

    async def _embed_content_async(self, text: str) -> dict:
        """Asynchronously embed a single text using Google GenAI SDK.

        Note: A genai SDK nem támogat asyncio-t natively, ezért
        ugyanazt a szinkron metódust hívjuk, amit a háttérben futtatunk.
        """
        # Visszaadjuk ugyanazt a szinkron hívást, amit majd task-ként futtatunk
        return self._embed_content(text)

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
                    data = self._embed_content(text)
                    # Csak 429 esetén próbálkozzunk újra
                    status_code = data.pop("_status_code", 200)

                    if status_code == 429 and attempt < self.MAX_RETRIES:
                        wait_time = 2**attempt
                        logger.warning(
                            f"Gemini: Rate limited (idx={idx}, attempt={attempt}), retrying in {wait_time}s"
                        )
                        time.sleep(wait_time)
                        continue

                    if "embeddings" in data and data["embeddings"]:
                        values = data["embeddings"][0].get("values", [])
                        results.append(values)
                        success = True
                        break
                    else:
                        # Más hibák esetén csak naplózunk és megyünk tovább
                        logger.error(
                            f"Gemini: API error (idx={idx}) - {data.get('error', {}).get('message', 'No embeddings in response')}"
                        )
                except Exception as exc:
                    # Hálózati hibák esetén próbálkozzunk újra
                    if attempt < self.MAX_RETRIES:
                        wait_time = 2**attempt
                        logger.warning(
                            f"Gemini: network error (idx={idx}, attempt={attempt}), retrying in {wait_time}s: {exc}"
                        )
                        time.sleep(wait_time)
                    else:
                        logger.error(
                            f"Gemini: network error after {self.MAX_RETRIES} attempts (idx={idx}): {exc}"
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

                # Használjuk az asyncio.to_thread segítségével a szinkron metódust
                # mivel a genai SDK nem támogatja natively az asyncio-t
                try:
                    loop = asyncio.get_event_loop()
                    data = await loop.run_in_executor(None, self._embed_content, text)

                    # Csak 429 esetén próbálkozzunk újra
                    status_code = data.pop("_status_code", 200)

                    if status_code == 429 and attempt < self.MAX_RETRIES:
                        wait_time = 2**attempt
                        logger.warning(
                            f"Gemini: Rate limited (idx={idx}, attempt={attempt}), retrying in {wait_time}s"
                        )
                        await asyncio.sleep(wait_time)
                        continue

                    if "embeddings" in data and data["embeddings"]:
                        values = data["embeddings"][0].get("values", [])
                        results.append(values)
                        success = True
                        break
                    else:
                        # Más hibák esetén csak naplózunk és megyünk tovább
                        logger.error(
                            f"Gemini: API error (idx={idx}) - {data.get('error', {}).get('message', 'No embeddings in response')}"
                        )
                except Exception as exc:
                    # Hálózati hibák esetén próbálkozzunk újra
                    if attempt < self.MAX_RETRIES:
                        wait_time = 2**attempt
                        logger.warning(
                            f"Gemini: network error (idx={idx}, attempt={attempt}), retrying in {wait_time}s: {exc}"
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(
                            f"Gemini: network error after {self.MAX_RETRIES} attempts (idx={idx}): {exc}"
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
    if name == "enhanced" or name == "enhanced_local":
        return EnhancedLocalBackend()
    return LocalBackend()


def get_enhanced_backend() -> EnhancedLocalBackend:
    """Get the enhanced backend with instruction template support."""
    return EnhancedLocalBackend()
