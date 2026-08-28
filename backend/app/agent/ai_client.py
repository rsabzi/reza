"""Google Gemini reasoning client."""

from __future__ import annotations

from typing import Protocol

from fastapi import Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.secrets import resolve_gemini_api_key

AI_MODEL = "gemini-2.5-flash"


class AIClient(Protocol):
    async def generate(self, prompt: str) -> str:
        """Return a JSON-formatted planning response."""


class AIConfigurationError(RuntimeError):
    pass


class GeminiAIClient:
    """Async Google Gen AI adapter with a server-side-only credential."""

    model = AI_MODEL

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key

    async def generate(self, prompt: str) -> str:
        if not self.api_key:
            raise AIConfigurationError(
                "Gemini API key is not configured; add and validate it in Dashboard settings"
            )
        from google import genai
        from google.genai import types

        async with genai.Client(api_key=self.api_key).aio as client:
            response = await client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )
        if not response.text:
            raise RuntimeError("Gemini returned an empty response")
        return response.text


def get_ai_client(db: Session = Depends(get_db)) -> GeminiAIClient:
    """FastAPI dependency using encrypted Dashboard settings before environment fallback."""

    return GeminiAIClient(api_key=resolve_gemini_api_key(db))
