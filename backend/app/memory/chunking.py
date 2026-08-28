"""Deterministic paragraph/word chunking for playbooks."""

from __future__ import annotations


def _split_long_text(text: str, max_chars: int) -> list[str]:
    words = text.split()
    chunks: list[str] = []
    current: list[str] = []
    length = 0
    for word in words:
        extra = len(word) + (1 if current else 0)
        if current and length + extra > max_chars:
            chunks.append(" ".join(current))
            current = [word]
            length = len(word)
        else:
            current.append(word)
            length += extra
    if current:
        chunks.append(" ".join(current))
    return chunks


def chunk_playbook(content: str, *, max_chars: int = 800) -> list[str]:
    if max_chars < 100:
        raise ValueError("max_chars must be at least 100")
    normalized = content.strip()
    if not normalized:
        raise ValueError("Playbook content must not be blank")
    paragraphs = [paragraph.strip() for paragraph in normalized.split("\n\n") if paragraph.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        pieces = (
            [paragraph] if len(paragraph) <= max_chars else _split_long_text(paragraph, max_chars)
        )
        for piece in pieces:
            candidate = f"{current}\n\n{piece}" if current else piece
            if current and len(candidate) > max_chars:
                chunks.append(current)
                current = piece
            else:
                current = candidate
    if current:
        chunks.append(current)
    return chunks
