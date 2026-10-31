"""Utility helpers for language detection and mapping."""

from app.config import settings


BOLNA_AGENT_MAP: dict[str, str] = {"tamil": settings.BOLNA_AGENT_ID_TAMIL}


def get_bolna_agent_id(language: str) -> str | None:
    """Return the Bolna agent ID for a given language, or None if unsupported."""
    return BOLNA_AGENT_MAP.get(language.strip().lower()) or None


GREETING_MAP: dict[str, str] = {"tamil": "வணக்கம்"}


def get_greeting(language: str) -> str:
    return GREETING_MAP.get(language.strip().lower(), "வணக்கம்")
