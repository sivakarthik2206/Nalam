"""Utility helpers for language detection and mapping."""

from app.config import settings


BOLNA_AGENT_MAP: dict[str, str] = {
    "hindi": settings.BOLNA_AGENT_ID_HINDI,
    "tamil": settings.BOLNA_AGENT_ID_TAMIL,
    "english": settings.BOLNA_AGENT_ID_ENGLISH,
}


def get_bolna_agent_id(language: str) -> str | None:
    """Return the Bolna agent ID for a given language, or None if unsupported."""
    return BOLNA_AGENT_MAP.get(language)


GREETING_MAP: dict[str, str] = {
    "hindi": "नमस्ते",
    "tamil": "வணக்கம்",
    "english": "Hello",
}


def get_greeting(language: str) -> str:
    return GREETING_MAP.get(language, "Hello")
