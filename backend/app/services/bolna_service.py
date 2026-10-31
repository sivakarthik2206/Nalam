"""Contract-safe client for Bolna outbound calls and execution lookups."""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Mapping
from typing import Final

import httpx

logger = logging.getLogger(__name__)

_E164_RE: Final[re.Pattern[str]] = re.compile(r"^\+[1-9]\d{7,14}$")
_DEFAULT_TIMEOUT_SECONDS: Final[float] = 30.0
_MAX_BATCH_DELAY_SECONDS: Final[float] = 1.0


class BolnaServiceError(RuntimeError):
    """A provider or protocol failure that must remain visible to callers."""

    def __init__(
        self,
        message: str,
        *,
        retryable: bool,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code


def _redact_phone(phone: str) -> str:
    """Keep logs useful without recording a complete patient phone number."""
    if len(phone) <= 4:
        return "<redacted>"
    return f"***{phone[-4:]}"


def _validate_e164(phone: str) -> str:
    normalised = phone.strip()
    if not _E164_RE.fullmatch(normalised):
        raise ValueError("recipient_phone must be an E.164 phone number")
    return normalised


class BolnaService:
    """Async client for Bolna's documented REST API."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.bolna.ai",
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.api_key = api_key.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if not self.api_key:
            raise BolnaServiceError(
                "BOLNA_API_KEY is not configured",
                retryable=False,
            )
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                timeout=self.timeout_seconds,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    @staticmethod
    def _error_result(error: BolnaServiceError) -> dict[str, object]:
        result: dict[str, object] = {
            "error": True,
            "detail": str(error),
            "retryable": error.retryable,
        }
        if error.status_code is not None:
            result["status_code"] = error.status_code
        return result

    async def trigger_call(
        self,
        agent_id: str,
        recipient_phone: str,
        user_data: Mapping[str, object],
    ) -> dict[str, object]:
        """Place one real outbound call through ``POST /call``.

        Nalam is Tamil-only. Rejecting a non-Tamil request here protects all
        callers, including legacy/demo routes that still expose a language
        field, from accidentally starting a Hindi or English call.
        """
        try:
            clean_agent_id = agent_id.strip()
            if not clean_agent_id:
                raise BolnaServiceError("Tamil Bolna agent ID is not configured", retryable=False)

            language = str(user_data.get("language", "")).strip().lower()
            if language != "tamil":
                raise BolnaServiceError(
                    "Nalam voice calls require language=tamil",
                    retryable=False,
                )

            clean_phone = _validate_e164(recipient_phone)
            client = await self._get_client()
            payload = {
                "agent_id": clean_agent_id,
                "recipient_phone_number": clean_phone,
                "user_data": dict(user_data),
            }
            response = await client.post("/call", json=payload)
            if response.is_error:
                retryable = response.status_code == 429 or response.status_code >= 500
                raise BolnaServiceError(
                    f"Bolna call request failed with HTTP {response.status_code}",
                    retryable=retryable,
                    status_code=response.status_code,
                )

            raw_data = response.json()
            if not isinstance(raw_data, dict):
                raise BolnaServiceError(
                    "Bolna call response was not a JSON object",
                    retryable=False,
                )

            data: dict[str, object] = dict(raw_data)
            execution_id = data.get("execution_id") or data.get("call_id")
            if not isinstance(execution_id, str) or not execution_id.strip():
                raise BolnaServiceError(
                    "Bolna call response did not contain execution_id",
                    retryable=False,
                )

            data.setdefault("execution_id", execution_id)
            data.setdefault("call_id", execution_id)
            logger.info(
                "Bolna call queued execution_id=%s recipient=%s",
                execution_id,
                _redact_phone(clean_phone),
            )
            return data
        except ValueError as exc:
            error = BolnaServiceError(str(exc), retryable=False)
            logger.warning("Bolna call rejected before provider request: %s", error)
            return self._error_result(error)
        except BolnaServiceError as exc:
            logger.error("Bolna call failed: %s retryable=%s", exc, exc.retryable)
            return self._error_result(exc)
        except httpx.TimeoutException:
            error = BolnaServiceError("Bolna request timed out", retryable=True)
            logger.error("Bolna call timed out")
            return self._error_result(error)
        except httpx.RequestError as exc:
            error = BolnaServiceError("Bolna network request failed", retryable=True)
            logger.error("Bolna network request failed: %s", type(exc).__name__)
            return self._error_result(error)
        except (httpx.DecodingError, ValueError):
            error = BolnaServiceError("Bolna returned an invalid response", retryable=False)
            logger.error("Bolna response could not be decoded")
            return self._error_result(error)
        except Exception:
            logger.exception("Unexpected Bolna call failure")
            return self._error_result(
                BolnaServiceError("Unexpected Bolna integration failure", retryable=False)
            )

    async def trigger_batch_calls(
        self,
        calls: list[Mapping[str, object]],
    ) -> list[dict[str, object]]:
        """Trigger calls sequentially to respect provider rate limits."""
        results: list[dict[str, object]] = []
        for index, call in enumerate(calls):
            agent_id = call.get("agent_id")
            phone = call.get("phone")
            user_data = call.get("user_data")
            if not isinstance(agent_id, str) or not isinstance(phone, str) or not isinstance(user_data, Mapping):
                results.append({"error": True, "detail": "invalid_batch_call_contract"})
            else:
                results.append(
                    await self.trigger_call(
                        agent_id=agent_id,
                        recipient_phone=phone,
                        user_data=user_data,
                    )
                )
            if index < len(calls) - 1:
                await asyncio.sleep(_MAX_BATCH_DELAY_SECONDS)
        return results

    async def get_call_details(self, execution_id: str) -> dict[str, object]:
        """Fetch a Bolna execution using the documented executions endpoint."""
        try:
            if not execution_id.strip():
                raise ValueError("execution_id is required")
            client = await self._get_client()
            response = await client.get(f"/executions/{execution_id.strip()}")
            if response.is_error:
                retryable = response.status_code == 429 or response.status_code >= 500
                raise BolnaServiceError(
                    f"Bolna execution lookup failed with HTTP {response.status_code}",
                    retryable=retryable,
                    status_code=response.status_code,
                )
            raw_data = response.json()
            if not isinstance(raw_data, dict):
                raise BolnaServiceError(
                    "Bolna execution response was not a JSON object",
                    retryable=False,
                )
            return dict(raw_data)
        except (ValueError, BolnaServiceError) as exc:
            error = exc if isinstance(exc, BolnaServiceError) else BolnaServiceError(str(exc), retryable=False)
            logger.error("Bolna execution lookup failed: %s", error)
            return self._error_result(error)
        except httpx.TimeoutException:
            logger.error("Bolna execution lookup timed out")
            return self._error_result(BolnaServiceError("Bolna request timed out", retryable=True))
        except httpx.RequestError as exc:
            logger.error("Bolna execution lookup network failure: %s", type(exc).__name__)
            return self._error_result(BolnaServiceError("Bolna network request failed", retryable=True))
        except (httpx.DecodingError, ValueError):
            return self._error_result(BolnaServiceError("Bolna returned an invalid response", retryable=False))
        except Exception:
            logger.exception("Unexpected Bolna execution lookup failure")
            return self._error_result(
                BolnaServiceError("Unexpected Bolna integration failure", retryable=False)
            )
