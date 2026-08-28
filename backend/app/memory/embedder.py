"""Gemini embedding adapter with a deterministic offline fallback."""

from __future__ import annotations

import hashlib
import math
import os
import re
import time
from collections.abc import Callable

from ..services.secrets import resolve_gemini_api_key

EMBEDDING_MODEL = "gemini-embedding-001"
LOCAL_DIMENSIONS = 128


class EmbeddingError(RuntimeError):
    """An embedding provider failed after all retries."""


def _local_embedding(text: str, dimensions: int = LOCAL_DIMENSIONS) -> list[float]:
    """Deterministic feature hashing for offline development and tests.

    Production automatically uses Gemini when GEMINI_API_KEY is present. This fallback
    is deliberately deterministic (rather than random) so local search remains useful.
    """

    tokens = re.findall(r"[\w\u0600-\u06ff]+", text.lower())
    vector = [0.0] * dimensions
    for token in tokens:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] & 1 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        # A non-empty input consisting only of punctuation still gets a stable vector.
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        vector[int.from_bytes(digest[:2], "big") % dimensions] = 1.0
        return vector
    return [value / norm for value in vector]


def _gemini_embedding(text: str, task_type: str) -> list[float]:
    from google import genai
    from google.genai import types

    api_key = resolve_gemini_api_key()
    if not api_key:
        raise EmbeddingError("Gemini API key is not configured")
    with genai.Client(api_key=api_key) as client:
        response = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text,
            config=types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=LOCAL_DIMENSIONS,
            ),
        )
    if not response.embeddings or not response.embeddings[0].values:
        raise EmbeddingError("Gemini returned an empty embedding")
    return [float(value) for value in response.embeddings[0].values]


def embed_text(
    text: str,
    *,
    task_type: str = "RETRIEVAL_DOCUMENT",
    max_attempts: int = 3,
    sleep: Callable[[float], None] = time.sleep,
) -> list[float]:
    """Embed text with Gemini, retrying transient errors with exponential backoff.

    `EMBEDDING_BACKEND=local` forces the offline implementation. `auto` (default)
    uses Gemini when a key exists and local embeddings otherwise.
    """

    if not text or not text.strip():
        raise ValueError("Cannot embed blank text")
    backend = os.getenv("EMBEDDING_BACKEND", "auto").lower()
    if backend == "local":
        return _local_embedding(text)
    has_key = bool(resolve_gemini_api_key())
    if backend == "auto" and not has_key:
        return _local_embedding(text)
    if backend not in {"auto", "gemini"}:
        raise EmbeddingError(f"Unsupported embedding backend: {backend}")

    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return _gemini_embedding(text, task_type)
        except Exception as exc:
            last_error = exc
            if attempt < max_attempts:
                sleep(0.25 * (2 ** (attempt - 1)))
    raise EmbeddingError(
        f"Embedding failed after {max_attempts} attempts: {last_error}"
    ) from last_error
