"""Process-wide Gemini API key pool: rotation pointer and health cooldowns.

The assistant can be configured with several Google API keys. When one key is
rate-limited (429), runs out of quota, or is rejected outright, the runtime
rotates to the next healthy key instead of failing the user's task. The pool
tracks:

- which key last succeeded (the "active" key — tried first on the next call);
- per-key cooldowns so a failing key is skipped for a short while.

State is intentionally in-memory: cooldowns are short-lived operational state
and after a restart keys are simply re-probed in slot order (a dead key rotates
away again on its first failure). Raw key values are never logged or exposed;
human identity is the redacted hint (last four characters).
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass

RATE_LIMIT_COOLDOWN_SECONDS = 60.0
QUOTA_COOLDOWN_SECONDS = 300.0
INVALID_KEY_COOLDOWN_SECONDS = 900.0


def key_hint(value: str) -> str:
    """Redacted, log-safe identity of a raw API key."""

    if not value:
        return "••••"
    return f"••••{value[-4:]}" if len(value) >= 4 else f"••{value}"


@dataclass(slots=True, frozen=True)
class ApiKey:
    """One usable credential plus its redacted hint."""

    value: str
    hint: str

    @classmethod
    def of(cls, value: str) -> ApiKey:
        return cls(value=value, hint=key_hint(value))


@dataclass(slots=True)
class KeyHealth:
    cooldown_until: float = 0.0
    last_error: str | None = None
    failures: int = 0


@dataclass(slots=True)
class KeyPoolSnapshotItem:
    hint: str
    active: bool
    cooling_seconds: float
    last_error: str | None


class KeyPool:
    """Tracks the active key and cooling-down keys for one server process."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._health: dict[str, KeyHealth] = {}
        self._active: str | None = None

    # -- ordering -----------------------------------------------------------

    def _cooling(self, value: str) -> bool:
        health = self._health.get(value)
        return health is not None and health.cooldown_until > self._clock()

    def cooling_seconds(self, value: str) -> float:
        health = self._health.get(value)
        if health is None:
            return 0.0
        return max(0.0, health.cooldown_until - self._clock())

    def order_keys(self, keys: Sequence[ApiKey]) -> list[ApiKey]:
        """Active key first, then other ready keys, cooling keys last.

        Never drops a key: when every key is cooling down they are returned
        soonest-expiry first so a single-key installation keeps retrying.
        """

        unique: list[ApiKey] = []
        seen: set[str] = set()
        for key in keys:
            if key.value and key.value not in seen:
                seen.add(key.value)
                unique.append(key)
        ready = [key for key in unique if not self._cooling(key.value)]
        cooling = sorted(
            (key for key in unique if self._cooling(key.value)),
            key=lambda key: self._health[key.value].cooldown_until,
        )
        ordered = [*ready, *cooling]
        if self._active in seen:
            active = next((key for key in ordered if key.value == self._active), None)
            if active is not None:
                ordered.remove(active)
                ordered.insert(0, active)
        return ordered

    def has_ready_alternative(self, keys: Sequence[ApiKey], current: ApiKey) -> bool:
        return any(key.value != current.value and not self._cooling(key.value) for key in keys)

    # -- state transitions ---------------------------------------------------

    def mark_success(self, key: ApiKey) -> None:
        self._health.pop(key.value, None)
        self._active = key.value

    def _mark_failure(self, key: ApiKey, seconds: float, reason: str) -> None:
        health = self._health.get(key.value) or KeyHealth()
        health.cooldown_until = max(health.cooldown_until, self._clock() + seconds)
        health.last_error = reason
        health.failures += 1
        self._health[key.value] = health
        if self._active == key.value:
            self._active = None

    def mark_rate_limited(self, key: ApiKey, seconds: float = RATE_LIMIT_COOLDOWN_SECONDS) -> None:
        self._mark_failure(key, seconds, "rate_limited")

    def mark_quota_exhausted(self, key: ApiKey, seconds: float = QUOTA_COOLDOWN_SECONDS) -> None:
        self._mark_failure(key, seconds, "quota_exhausted")

    def mark_invalid(self, key: ApiKey, seconds: float = INVALID_KEY_COOLDOWN_SECONDS) -> None:
        self._mark_failure(key, seconds, "invalid_key")

    def forget(self, value: str) -> None:
        """Clear state for a key that was re-saved or removed by the user."""

        self._health.pop(value, None)
        if self._active == value:
            self._active = None

    def reset(self) -> None:
        self._health.clear()
        self._active = None

    # -- reporting -----------------------------------------------------------

    @property
    def active(self) -> str | None:
        return self._active

    def last_error(self, value: str) -> str | None:
        health = self._health.get(value)
        return health.last_error if health is not None else None

    def snapshot(self, keys: Sequence[ApiKey]) -> list[KeyPoolSnapshotItem]:
        items: list[KeyPoolSnapshotItem] = []
        for key in keys:
            items.append(
                KeyPoolSnapshotItem(
                    hint=key.hint,
                    active=self._active == key.value,
                    cooling_seconds=self.cooling_seconds(key.value),
                    last_error=self.last_error(key.value),
                )
            )
        return items


SHARED_KEY_POOL = KeyPool()
