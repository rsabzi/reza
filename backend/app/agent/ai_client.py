"""Google Gemini Interactions API client with key rotation, model fallback, audit hooks.

Everything runtime-related uses the Interactions API (``client.aio.interactions.create``)
instead of the deprecated ``generateContent`` path. The model choice is configurable
through ``GEMINI_MODEL`` / the dashboard preference; if a chosen model answers with
404 / "no longer available", the client advances to the next supported candidate
instead of retrying the dead model.

Several API keys may be configured at once. Key-specific failures (429 rate limit,
exhausted quota, rejected credential) rotate to the next healthy key immediately so
the user's task keeps running; the last key that worked is tried first on the next
call. Key health lives in the process-wide :data:`SHARED_KEY_POOL`.
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
from ..services.secrets import resolve_gemini_api_keys
from .key_pool import SHARED_KEY_POOL, ApiKey

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


class GeminiInvalidKeyError(AIProviderError):
    """Google rejected the credential (400/401/403 or auth error)."""


class GeminiNetworkError(AIProviderError):
    """Google endpoints are unreachable (TLS/DNS/connect/timeout/server error)."""


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


def is_rate_limit_error(exc: Exception) -> bool:
    """429 / rate limit / quota errors are key-specific: rotate to another key."""

    code = getattr(exc, "code", None)
    if code == 429:
        return True
    text = f"{exc.__class__.__name__}: {exc}".lower()
    markers = (
        "429",
        "resource_exhausted",
        "resource exhausted",
        "rate limit",
        "rate_limit",
        "too many requests",
        "quota",
    )
    return any(marker in text for marker in markers)


def is_quota_exhausted_error(exc: Exception) -> bool:
    """Longer cooldown: the key burned through its quota, not a burst limit."""

    text = f"{exc.__class__.__name__}: {exc}".lower()
    return "quota" in text or "exhausted" in text or "exceeded" in text


def is_transient_error(exc: Exception) -> bool:
    """Timeout, rate limit, and provider 5xx errors are retryable."""

    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return True
    try:
        import httpx

        if isinstance(exc, httpx.TimeoutException):
            return True
        # TransportError covers ConnectError/ReadError/WriteError/CloseError,
        # ProtocolError, ProxyError, and UnsupportedProtocol.
        if isinstance(exc, httpx.TransportError):
            return True
    except ImportError:  # pragma: no cover - httpx is always installed
        pass
    # Low-level transport exceptions (httpcore/ssl/anyio) bubbling up unwrapped:
    # connection resets, TLS handshake failures, broken pipes, timeouts.
    module = getattr(exc.__class__, "__module__", "") or ""
    if module.split(".")[0] in {"httpcore", "ssl", "anyio"}:
        class_name = exc.__class__.__name__.lower()
        if any(
            marker in class_name
            for marker in ("connect", "read", "write", "timeout", "close", "reset", "ssl", "error")
        ):
            return True
    try:
        from google.genai import errors

        if isinstance(exc, errors.APIError) and (exc.code in {408, 429} or (exc.code or 0) >= 500):
            return True
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


class _KeyFailure(Exception):
    """Internal control flow: this key is unusable right now, try the next one."""

    def __init__(self, kind: str, exc: Exception) -> None:
        super().__init__(kind)
        self.kind = kind  # invalid | rate_limited | quota | provider | models
        self.exc = exc


def _normalize_keys(api_keys: Sequence[str | ApiKey] | None, api_key: str | None) -> list[ApiKey]:
    raw: list[str | ApiKey] = list(api_keys) if api_keys is not None else []
    if api_key:
        raw.append(api_key)
    unique: list[ApiKey] = []
    seen: set[str] = set()
    for item in raw:
        value = item.value if isinstance(item, ApiKey) else (item or "").strip()
        if value and value not in seen:
            seen.add(value)
            unique.append(ApiKey.of(value))
    return unique


class GeminiInteractionsClient:
    """Async Interactions API adapter with key rotation, model fallback, backoff."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        api_keys: Sequence[str | ApiKey] | None = None,
        preferred_model: str | None = None,
        candidates: Sequence[str] | None = None,
        max_retries: int = 3,
        backoff_base: float = 1.0,
        call_timeout: float = 60.0,
        sleep: Callable[[float], Awaitable[None]] | None = None,
        key_pool: Any | None = None,
    ) -> None:
        self._keys = _normalize_keys(api_keys, api_key)
        self.api_key = self._keys[0].value if self._keys else ""
        self.preferred_model = preferred_model or default_model_from_env()
        self.candidates = (
            list(candidates) if candidates else configured_model_candidates(self.preferred_model)
        )
        self.model = self.candidates[0] if self.candidates else self.preferred_model
        self.max_retries = max(1, min(max_retries, 5))
        self.backoff_base = max(0.0, backoff_base)
        self.call_timeout = call_timeout
        self._sleep = sleep or asyncio.sleep
        self._pool = key_pool if key_pool is not None else SHARED_KEY_POOL
        self._current_key: ApiKey | None = None

    def _require_key(self) -> None:
        if not self._keys:
            raise AIConfigurationError(
                "Gemini API key is not configured; add and validate it in Dashboard settings"
            )

    async def _create_interaction(self, model: str, **payload: Any) -> Any:
        """One low-level Interactions API call through the fetched SDK client."""

        self._require_key()
        from google import genai

        key = self._current_key or self._keys[0]
        async with genai.Client(api_key=key.value).aio as client:
            return await asyncio.wait_for(
                client.interactions.create(model=model, **payload),
                timeout=self.call_timeout,
            )

    async def _try_key(
        self,
        key: ApiKey,
        *,
        operation: str,
        attempt_callback: Callable[[str], None] | None,
        log_attempt: Callable[..., None] | None,
        payload_factory: Callable[[], dict[str, Any]],
    ) -> InteractionResult:
        """Run the model candidate chain with one key.

        Raises :class:`_KeyFailure` when the key itself (not the model) is the
        problem, or when this key's retries were exhausted, so the caller can
        rotate to the next key.
        """

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
                    self._current_key = key
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
                    self._pool.mark_success(key)
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
                    if is_invalid_key_error(exc):
                        raise _KeyFailure("invalid", exc) from exc
                    if is_rate_limit_error(exc):
                        # Rotating to a healthy key beats sleeping on a limited
                        # one; only backoff-retry when no alternative exists.
                        alternative = self._pool.has_ready_alternative(self._keys, key)
                        if not alternative and attempt_no < self.max_retries:
                            await self._sleep(self.backoff_base * (2 ** (attempt_no - 1)))
                            continue
                        kind = "quota" if is_quota_exhausted_error(exc) else "rate_limited"
                        raise _KeyFailure(kind, exc) from exc
                    if is_transient_error(exc):
                        if attempt_no < self.max_retries:
                            await self._sleep(self.backoff_base * (2 ** (attempt_no - 1)))
                            continue
                        raise _KeyFailure("provider", exc) from exc
                    raise _KeyFailure("provider", exc) from exc
        raise _KeyFailure(
            "models",
            ModelUnavailableError(
                f"No supported Gemini model answered with key {key.hint} "
                f"(last model {used_model}): {last_error}"
            ),
        ) from last_error

    async def _run_with_fallback(
        self,
        *,
        operation: str,
        attempt_callback: Callable[[str], None] | None,
        log_attempt: Callable[..., None] | None,
        payload_factory: Callable[[], dict[str, Any]],
    ) -> InteractionResult:
        """Rotate over keys, then model candidates; retry transient errors; log all."""

        self._require_key()
        failures: list[tuple[ApiKey, _KeyFailure]] = []
        last_error: Exception | None = None
        for key in self._pool.order_keys(self._keys):
            try:
                return await self._try_key(
                    key,
                    operation=operation,
                    attempt_callback=attempt_callback,
                    log_attempt=log_attempt,
                    payload_factory=payload_factory,
                )
            except _KeyFailure as failure:
                last_error = failure.exc
                failures.append((key, failure))
                if failure.kind == "invalid":
                    self._pool.mark_invalid(key)
                elif failure.kind == "quota":
                    self._pool.mark_quota_exhausted(key)
                elif failure.kind == "rate_limited":
                    self._pool.mark_rate_limited(key)
                # "provider"/"models" carry no cooldown: the next call may retry.

        summary = "; ".join(f"key {key.hint}: {failure.kind}" for key, failure in failures)
        kinds = {failure.kind for _, failure in failures}
        if kinds == {"invalid"}:
            raise GeminiInvalidKeyError(
                f"All configured Gemini API keys were rejected by Google ({summary})",
            ) from last_error
        if kinds == {"models"}:
            raise ModelUnavailableError(
                f"No supported Gemini model answered on any key ({summary})",
            ) from last_error
        raise AIProviderError(
            f"Gemini call failed on every configured API key ({summary}); last error: {last_error}"
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
    api_key: str | None = None,
    *,
    api_keys: Sequence[str | ApiKey] | None = None,
    preferred_model: str | None = None,
    candidates: Sequence[str] | None = None,
) -> GeminiInteractionsClient:
    return GeminiInteractionsClient(
        api_key=api_key,
        api_keys=api_keys,
        preferred_model=preferred_model,
        candidates=candidates,
    )


async def list_available_models(api_key: str) -> list[str]:
    """Discover model names through the SDK, independent of any single model."""

    from google import genai
    from google.genai import types

    # NOTE: `Client(...).aio` is already the AsyncClient; it has no `.aio` attr.
    async with genai.Client(api_key=api_key).aio as client:
        pager = await client.models.list(config=types.ListModelsConfig(page_size=100))
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


def is_invalid_key_error(exc: Exception) -> bool:
    """True when Google rejects the credential itself (not the model)."""

    try:
        from google.genai import errors

        if isinstance(exc, errors.APIError) and (exc.code or 0) in {400, 401, 403}:
            return True
    except ImportError:  # pragma: no cover
        pass
    text = f"{exc.__class__.__name__}: {exc}".lower()
    markers = (
        "api key",
        "invalid key",
        "unauthorized",
        "permission denied",
        "forbidden",
        "authentication",
        "invalid argument",
    )
    return any(marker in text for marker in markers)


async def _probe_first_available_model(api_key: str, candidates: Sequence[str]) -> str:
    """Fallback when `models.list` is not permitted: probe candidates via get()."""

    from google import genai

    async with genai.Client(api_key=api_key).aio as client:
        last_error: Exception | None = None
        for candidate in candidates:
            try:
                model = await client.models.get(model=candidate)
                name = getattr(model, "name", None) or candidate
                return name.removeprefix("models/") or candidate
            except Exception as exc:
                last_error = exc
                if is_invalid_key_error(exc) or is_transient_error(exc):
                    raise
        raise ModelUnavailableError(
            f"No supported Gemini model is reachable; last error: {last_error}"
        ) from last_error


async def validate_gemini_api_key(api_key: str) -> tuple[str, str]:
    """Validate a key without depending on any model, then pick the first supported one.

    Returns ``(validated_model, provider)`` where ``provider`` is ``"api"`` (key is
    accepted via model discovery) or ``"models"`` (key validated via a model probe).

    Raises ``GeminiNetworkError`` when Google is unreachable from this server and
    ``GeminiInvalidKeyError`` when Google rejects the credential itself, so callers
    can distinguish "bad key" from "no connectivity".
    """

    try:
        available = await list_available_models(api_key)
    except Exception as exc:
        if is_transient_error(exc):
            raise GeminiNetworkError(
                "Google Gemini endpoints are unreachable from this server "
                "(network/TLS/proxy); check connectivity"
            ) from exc
        if is_invalid_key_error(exc):
            raise GeminiInvalidKeyError("Google rejected the Gemini API key") from exc
        # `models.list` failed for another reason (e.g. discovery not permitted for
        # this key); fall back to probing the curated candidates directly.
        try:
            model = await _probe_first_available_model(api_key, SUPPORTED_MODEL_CANDIDATES)
        except Exception as probe_exc:
            if is_transient_error(probe_exc):
                raise GeminiNetworkError(
                    "Google Gemini endpoints are unreachable from this server"
                ) from probe_exc
            if is_invalid_key_error(probe_exc):
                raise GeminiInvalidKeyError("Google rejected the Gemini API key") from probe_exc
            raise
        return model, "models"
    supported = supported_models_overlap(available)
    if supported:
        return supported[0], "api"
    # The key is valid even if the curated list changed; fall back to the default.
    return DEFAULT_GEMINI_MODEL, "api"


def get_ai_client(db: Session = Depends(get_db)) -> GeminiInteractionsClient:
    """FastAPI dependency using encrypted Dashboard settings before environment fallback."""

    return build_interactions_client(
        api_keys=resolve_gemini_api_keys(db),
        preferred_model=resolved_model_name(db, default_model_from_env()),
    )
