"""Bolna AI voice-call integration service."""

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class BolnaService:
    """Async client for the Bolna AI voice-call API."""

    def __init__(self, api_key: str, base_url: str = "https://api.bolna.ai") -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ------------------------------------------------------------------
    # API Methods
    # ------------------------------------------------------------------

    async def trigger_call(
        self,
        agent_id: str,
        recipient_phone: str,
        user_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Trigger a single outbound call via Bolna.

        ``user_data`` should contain:
            patient_name, medication_name, dosage, meal_relation,
            language, time_slot, patient_id, medication_id
        """
        client = await self._get_client()
        payload = {
            "agent_id": agent_id,
            "recipient_phone_number": recipient_phone,
            "user_data": user_data,
        }
        try:
            resp = await client.post("/call", json=payload)
            resp.raise_for_status()
            data = resp.json()
            logger.info(
                "Bolna call triggered → call_id=%s phone=%s agent=%s",
                data.get("call_id"),
                recipient_phone,
                agent_id,
            )
            return data
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Bolna API HTTP %s for phone %s: %s",
                exc.response.status_code,
                recipient_phone,
                exc.response.text,
            )
            return {"error": True, "status_code": exc.response.status_code, "detail": exc.response.text}
        except Exception:
            logger.exception("Bolna call trigger failed for phone %s", recipient_phone)
            return {"error": True, "detail": "unexpected_error"}

    async def trigger_batch_calls(self, calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Trigger multiple calls sequentially with a 1-second delay between each.

        Each ``call`` dict must contain: agent_id, phone, user_data.
        """
        results: list[dict[str, Any]] = []
        for idx, call in enumerate(calls):
            try:
                result = await self.trigger_call(
                    agent_id=call["agent_id"],
                    recipient_phone=call["phone"],
                    user_data=call["user_data"],
                )
                results.append(result)
            except Exception:
                logger.exception("Batch call %d/%d failed for %s", idx + 1, len(calls), call.get("phone"))
                results.append({"error": True, "phone": call.get("phone"), "detail": "batch_call_error"})
            # Small delay to avoid rate-limiting
            if idx < len(calls) - 1:
                await asyncio.sleep(1.0)
        return results

    async def get_call_details(self, call_id: str) -> dict[str, Any]:
        """Fetch details for a completed or in-progress call."""
        client = await self._get_client()
        try:
            resp = await client.get(f"/call/{call_id}")
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error("Bolna get_call_details %s → HTTP %s", call_id, exc.response.status_code)
            return {"error": True, "status_code": exc.response.status_code}
        except Exception:
            logger.exception("Failed to fetch call details for %s", call_id)
            return {"error": True, "detail": "unexpected_error"}
