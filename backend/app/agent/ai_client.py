"""Google Gemini Interactions API client with model fallback and audit hooks.

Everything runtime-related uses the Interactions API (``client.aio.interactions.create``)
instead of the deprecated ``generateContent`` path. The model choice is configurable
through ``GEMINI_MODEL`` / the dashboard preference; if a chosen model answers with
404 / "no longer available", the client advances to the next supported candidate
instead of retrying the dead model.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from fastapi import Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.preferences import resolved_model_name
from ..services.secrets import resolve_gemini_api_key

# Current stable Flash model per the official Gemini docs (August 2026).
DEFAULT_GEMINI_MODEL = "gemini-3.7-flash"

# Ordered fallback chain of stable/recent Flash models.
SUPPORTED_MODEL_CANDIDATES: tuple[str, ...] = (
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash",
    "gemini-flash-latest",
)

MODEL_UNAVAILABLE_MARKERS = (
    "no longer available",
    "not found",
    "doesn't exist",
    "does not exist",
    "unsupported model",
)


class AIConfigurationError(RuntimeError):
    """The runtime has no usable Gemini credential."""


class AIProviderError(RuntimeError):
    """A provider call failed after exhausting retries/fallbacks."""


class ModelUnavailableError(AIProviderError):
    """The model is gone (404 / marked unavailable); try the next candidate."""


def default_model_from_env() -> str:
    return os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip() or DEFAULT_GEMINI_MODEL


def configured_model_candidates(preferred: str | None = None) -> list[str]:
    """Return the candidate chain: preferred model first, then supported models."""

    base = [preferred] if preferred and preferred.strip() else []
    chain: list[str] = []
    for name in [*base, *SUPPORTED_MODEL_CANDIDATES]:
        if name not in chain:
            chain.append(name)
    return chain


def is_model_unavailable_error(exc: Exception) -> bool:
    text = f"{exc.__class__.__name__}: {exc}".lower()
    if "404" in text or "not_found" in text:
        return True
    return any(marker in text for marker in MODEL_UNAVAILABLE_MARKERS)


def is_transient_error(exc: Exception) -> bool:
    """Timeout, rate limit, and provider 5xx errors are retryable."""

    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return True
    try:
        import httpx

        if isinstance(exc, httpx.TimeoutException):
            return True
        if isinstance(exc, (httpx.ConnectError, httpx.ReadError)):
            return True
    except ImportError:  # pragma: no cover - httpx is always installed
        pass
    try:
        from google.genai import errors

        if isinstance(exc, errors.ClientError) and exc.code in {429, 408}:
            return True
        if isinstance(exc, errors.ServerError):
            return True
        if exc.__class__.__name__ in {"ClientError", "ServerError"}:
            code = getattr(exc, "code", None)
            if code is not None and (code == 429 or code >= 500):
                return True
    except ImportError:  # pragma: no cover
        pass
    return False


@dataclass(slots=True)
class InteractionResult:
    """Normalized output of one Interactions API call."""

    model: str
    output_text: str
    steps: list[Any] = field(default_factory=list)
    interaction_id: str | None = None

    def function_calls(self) -> list[Any]:
        return [step for step in self.steps if getattr(step, "type", None) == "function_call"]

    def serialized_steps(self) -> list[dict[str, Any]]:
        """Provider step dicts to feed back into stateless history (store=False)."""

        serialized: list[dict[str, Any]] = []
        for step in self.steps:
            dict_value = getattr(step, "model_dump", None)
            if callable(dict_value):
                serialized.append(dict_value(mode="json"))
            elif isinstance(step, dict):
                serialized.append(step)
        return serialized


class ChatClient(Protocol):
    """Provider-agnostic interface used by the assistant orchestration layer."""

    model: str

    async def chat(
        self,
        *,
        input: Any,
        tools: list[dict[str, Any]],
        system_instruction: str = "",
        operation: str = "assistant_chat",
        log_attempt: Callable[..., None] | None = None,
    ) -> InteractionResult: ...

    async def generate(self, prompt: str, operation: str = "decompose_task") -> str: ...


class GeminiInteractionsClient:
    """Async Interactions API adapter with candidate fallback and backoff."""

    def __init__(
        self,
        api_key: str | None,
        *,
        preferred_model: str | None = None,
        candidates: Sequence[str] | None = None,
        max_retries: int = 3,
        backoff_base: float = 1.0,
        call_timeout: float = 60.0,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        self.api_key = api_key or ""
        self.preferred_model = preferred_model or default_model_from_env()
        self.candidates = (
            list(candidates) if candidates else configured_model_candidates(self.preferred_model)
        )
        self.model = self.candidates[0] if self.candidates else self.preferred_model
        self.max_retries = max(1, min(max_retries, 5))
        self.backoff_base = max(0.0, backoff_base)
        self.call_timeout = call_timeout
        self._sleep = sleep or asyncio.sleep

    def _require_key(self) -> None:
        if not self.api_key:
            raise AIConfigurationError(
                "Gemini API key is not configured; add and validate it in Dashboard settings"
            )

    async def _create_interaction(self, model: str, **payload: Any) -> Any:
        """One low-level Interactions API call through the fetched SDK client."""

        self._require_key()
        from google import genai

        async with genai.Client(api_key=self.api_key).aio as client:
            return await asyncio.wait_for(
                client.interactions.create(model=model, **payload),
                timeout=self.call_timeout,
            )

    async def _run_with_fallback(
        self,
        *,
        operation: str,
        attempt_callback: Callable[[str], None] | None,
        log_attempt: Callable[..., None] | None,
        payload_factory: Callable[[], dict[str, Any]],
    ) -> InteractionResult:
        """Try candidates; retry transient errors with backoff; log every attempt."""

        last_error: Exception | None = None
        used_model: str | None = None
        for model in self.candidates:
            attempt_no = 0
            while attempt_no < self.max_retries:
                attempt_no += 1
                used_model = model
                if attempt_callback is not None:
                    attempt_callback(model)
                try:
                    response = await self._create_interaction(model, **payload_factory())
                    result = InteractionResult(
                        model=model,
                        output_text=getattr(response, "output_text", "") or "",
                        steps=list(getattr(response, "steps", None) or []),
                        interaction_id=getattr(response, "id", None) or None,
                    )
                    if log_attempt is not None:
                        log_attempt(
                            operation=operation,
                            model=model,
                            attempt=attempt_no,
                            response=result,
                            error=None,
                        )
                    self.model = model
                    return result
                except Exception as exc:
                    last_error = exc
                    if log_attempt is not None:
                        log_attempt(
                            operation=operation,
                            model=model,
                            attempt=attempt_no,
                            response=None,
                            error=exc,
                        )
                    if is_model_unavailable_error(exc):
                        # Dead model: never retry it; advance to the next candidate.
                        break
                    if is_transient_error(exc):
                        if attempt_no < self.max_retries:
                            await self._sleep(self.backoff_base * (2 ** (attempt_no - 1)))
                            continue
                        raise AIProviderError(
                            f"Gemini call to {model} failed after {attempt_no} attempts: {exc}"
                        ) from exc
                    raise AIProviderError(f"Gemini call to {model} failed: {exc}") from exc
        raise ModelUnavailableError(
            f"No supported Gemini model answered; last error with {used_model}: {last_error}"
        ) from last_error

    async def chat(
        self,
        *,
        input: Any,
        tools: list[dict[str, Any]],
        system_instruction: str = "",
        operation: str = "assistant_chat",
        log_attempt: Callable[..., None] | None = None,
    ) -> InteractionResult:
        payload: dict[str, Any] = {
            "input": input,
            "tools": tools,
            "store": False,
            "system_instruction": system_instruction or None,
        }
        return await self._run_with_fallback(
            operation=operation,
            attempt_callback=None,
            log_attempt=log_attempt,
            payload_factory=lambda: dict(payload),
        )

    async def generate(
        self,
        prompt: str,
        operation: str = "decompose_task",
        log_attempt: Callable[..., None] | None = None,
    ) -> str:
        """Structured JSON generation through the Interactions API (Planner path)."""

        result = await self._run_with_fallback(
            operation=operation,
            attempt_callback=None,
            log_attempt=log_attempt,
            payload_factory=lambda: {
                "input": prompt,
                "tools": [],
                "store": False,
                "system_instruction": (
                    "You are a planning engine. Return only a JSON object with no prose."
                ),
            },
        )
        if not result.output_text.strip():
            raise AIProviderError("Gemini returned an empty planning response")
        return result.output_text


def build_interactions_client(
    api_key: str | None,
    *,
    preferred_model: str | None = None,
    candidates: Sequence[str] | None = None,
) -> GeminiInteractionsClient:
    return GeminiInteractionsClient(
        api_key=api_key,
        preferred_model=preferred_model,
        candidates=candidates,
    )


async def list_available_models(api_key: str) -> list[str]:
    """Discover model names through the SDK, independent of any single model."""

    from google import genai
    from google.genai import types

    async with genai.Client(api_key=api_key).aio as client:
        pager = await client.aio.models.list(
            config=types.ListModelsConfig(page_size=100, filter="")
        )
        names: list[str] = []
        async for model in pager:
            name = getattr(model, "name", None) or ""
            name = name.removeprefix("models/")
            if name:
                names.append(name)
        return names


def supported_models_overlap(available: Sequence[str]) -> tuple[str, ...]:
    """Return currently supported Flash candidates in preference order."""

    available_set = set(available)
    return tuple(name for name in SUPPORTED_MODEL_CANDIDATES if name in available_set)


async def validate_gemini_api_key(api_key: str) -> tuple[str, str]:
    """Validate a key without depending on any model, then pick the first supported one.

    Returns ``(validated_model, provider)`` where ``provider`` is ``"api"`` (key is
    accepted by Gemini) or ``"models"`` (key plus model discovery succeeded).
    """

    available = await list_available_models(api_key)
    supported = supported_models_overlap(available)
    if supported:
        return supported[0], "api"
    # The key is valid even if the curated list changed; fall back to the default.
    return DEFAULT_GEMINI_MODEL, "api"


def get_ai_client(db: Session = Depends(get_db)) -> GeminiInteractionsClient:
    """FastAPI dependency using encrypted Dashboard settings before environment fallback."""

    return build_interactions_client(
        resolve_gemini_api_key(db),
        preferred_model=resolved_model_name(db, default_model_from_env()),
    )
