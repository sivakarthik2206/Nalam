"""Contract-safe Twilio WhatsApp client and alert message formatting."""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Mapping
from typing import Final

import httpx

logger = logging.getLogger(__name__)

_E164_RE: Final[re.Pattern[str]] = re.compile(r"^\+[1-9]\d{7,14}$")
_MAX_ATTEMPTS: Final[int] = 3
_MAX_RETRY_AFTER_SECONDS: Final[float] = 30.0


class TwilioServiceError(RuntimeError):
    """A Twilio delivery failure with retry classification."""

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


def _redact_address(address: str) -> str:
    if len(address) <= 4:
        return "<redacted>"
    return f"***{address[-4:]}"


def _normalise_e164(address: str, *, field_name: str) -> str:
    value = address.strip()
    if value.lower().startswith("whatsapp:"):
        value = value[9:]
    if not _E164_RE.fullmatch(value):
        raise ValueError(f"{field_name} must be an E.164 phone number")
    return value


class TwilioService:
    """Async Twilio REST client without an SDK dependency."""

    def __init__(self, account_sid: str, auth_token: str, whatsapp_from: str) -> None:
        self.account_sid = account_sid.strip()
        self.auth_token = auth_token.strip()
        self.whatsapp_from = whatsapp_from.strip()
        self._api_url = (
            f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
        )

    async def send_whatsapp(self, to: str, body: str) -> dict[str, object]:
        """Send a WhatsApp message and return only provider-confirmed results.

        Transport errors, rate limits, and 5xx responses are retried with a
        bounded backoff. Permanent configuration/validation errors are returned
        as explicit failures. No error response is represented as a message SID.
        """
        try:
            if not self.account_sid or not self.auth_token:
                raise TwilioServiceError(
                    "Twilio credentials are not configured",
                    retryable=False,
                )
            recipient = _normalise_e164(to, field_name="to")
            sender = _normalise_e164(self.whatsapp_from, field_name="TWILIO_WHATSAPP_FROM")
            clean_body = body.strip()
            if not clean_body:
                raise TwilioServiceError("WhatsApp message body is empty", retryable=False)
            if len(clean_body) > 1600:
                raise TwilioServiceError("WhatsApp message body exceeds 1600 characters", retryable=False)

            form_data = {
                "From": f"whatsapp:{sender}",
                "To": f"whatsapp:{recipient}",
                "Body": clean_body,
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                for attempt in range(1, _MAX_ATTEMPTS + 1):
                    try:
                        response = await client.post(
                            self._api_url,
                            data=form_data,
                            auth=(self.account_sid, self.auth_token),
                        )
                    except httpx.TimeoutException:
                        if attempt == _MAX_ATTEMPTS:
                            raise TwilioServiceError("Twilio request timed out", retryable=True)
                        await asyncio.sleep(float(attempt))
                        continue
                    except httpx.RequestError as exc:
                        if attempt == _MAX_ATTEMPTS:
                            logger.error("Twilio network failure: %s", type(exc).__name__)
                            raise TwilioServiceError("Twilio network request failed", retryable=True)
                        await asyncio.sleep(float(attempt))
                        continue

                    if response.is_error:
                        retryable = response.status_code == 429 or response.status_code >= 500
                        if retryable and attempt < _MAX_ATTEMPTS:
                            retry_after = response.headers.get("Retry-After")
                            try:
                                delay = min(float(retry_after or attempt), _MAX_RETRY_AFTER_SECONDS)
                            except ValueError:
                                delay = float(attempt)
                            await asyncio.sleep(delay)
                            continue
                        raise TwilioServiceError(
                            f"Twilio message request failed with HTTP {response.status_code}",
                            retryable=retryable,
                            status_code=response.status_code,
                        )

                    raw_result = response.json()
                    if not isinstance(raw_result, dict):
                        raise TwilioServiceError(
                            "Twilio response was not a JSON object",
                            retryable=False,
                        )
                    result: dict[str, object] = dict(raw_result)
                    sid = result.get("sid")
                    if not isinstance(sid, str) or not sid.strip():
                        raise TwilioServiceError(
                            "Twilio response did not contain a message SID",
                            retryable=False,
                        )
                    logger.info(
                        "WhatsApp message accepted sid=%s recipient=%s",
                        sid,
                        _redact_address(recipient),
                    )
                    return result

            raise TwilioServiceError("Twilio delivery attempt exhausted", retryable=True)
        except ValueError as exc:
            error = TwilioServiceError(str(exc), retryable=False)
            logger.warning("WhatsApp delivery rejected before provider request: %s", error)
            return {"error": True, "detail": str(error), "retryable": False}
        except TwilioServiceError as exc:
            logger.error("WhatsApp delivery failed: %s retryable=%s", exc, exc.retryable)
            result: dict[str, object] = {
                "error": True,
                "detail": str(exc),
                "retryable": exc.retryable,
            }
            if exc.status_code is not None:
                result["status_code"] = exc.status_code
            return result
        except (httpx.DecodingError, ValueError):
            logger.error("Twilio returned an invalid response")
            return {"error": True, "detail": "invalid_provider_response", "retryable": False}
        except Exception:
            logger.exception("Unexpected WhatsApp delivery failure")
            return {"error": True, "detail": "unexpected_provider_failure", "retryable": False}

    def format_daily_summary(
        self,
        summary: Mapping[str, object],
        language: str = "english",
    ) -> str:
        """Format a family summary; existing language aliases remain compatible."""
        name = str(summary.get("patient_name", "Patient"))
        taken = summary.get("doses_taken", 0)
        total = summary.get("total_doses_today", 0)
        raw_slots = summary.get("slot_statuses", {})
        slots: Mapping[str, object] = raw_slots if isinstance(raw_slots, Mapping) else {}
        score = summary.get("adherence_score_7d", 0.0)
        link = str(summary.get("dashboard_link", ""))
        missed = summary.get("doses_missed", 0)

        if language == "hindi":
            lines = [
                "🩺 *Nalam Report*",
                "",
                f"{name} ne aaj {taken}/{total} dawai li.",
                f"Miss hua: {missed} baar",
                "",
            ]
            slot_labels = {"morning": "Subah", "afternoon": "Dopahar", "evening": "Shaam", "night": "Raat"}
            for slot, status in slots.items():
                label = slot_labels.get(slot, slot.capitalize())
                emoji = "✅" if status == "taken" else ("❌" if status == "not_taken" else "⏳")
                lines.append(f"{label}: {emoji}")
            lines += ["", f"7 din ka score: *{score}%*"]
            if link:
                lines.append(f"\nDetails: {link}")
            return "\n".join(lines)

        if language == "tamil":
            lines = [
                "🩺 *Nalam Report*",
                "",
                f"{name} inru {taken}/{total} marunthu eduthar.",
                f"Miss aana: {missed} muray",
                "",
            ]
            slot_labels = {"morning": "Kaalai", "afternoon": "Madhiyam", "evening": "Maalai", "night": "Iravu"}
            for slot, status in slots.items():
                label = slot_labels.get(slot, slot.capitalize())
                emoji = "✅" if status == "taken" else ("❌" if status == "not_taken" else "⏳")
                lines.append(f"{label}: {emoji}")
            lines += ["", f"7 naal score: *{score}%*"]
            if link:
                lines.append(f"\nDetails: {link}")
            return "\n".join(lines)

        lines = [
            "🩺 *Nalam Daily Report*",
            "",
            f"{name} took {taken}/{total} doses today.",
            f"Missed today: {missed}",
            "",
        ]
        slot_labels = {"morning": "Morning", "afternoon": "Afternoon", "evening": "Evening", "night": "Night"}
        for slot, status in slots.items():
            label = slot_labels.get(slot, slot.capitalize())
            emoji = "✅" if status == "taken" else ("❌" if status == "not_taken" else "⏳")
            lines.append(f"{label}: {emoji}")
        lines += ["", f"7-day adherence: *{score}%*"]
        if link:
            lines.append(f"\nView details: {link}")
        return "\n".join(lines)

    def format_alert(
        self,
        alert_type: str,
        patient_name: str,
        details: str,
        language: str = "english",
    ) -> str:
        """Format a bounded alert without interpolating untrusted templates."""
        templates = _ALERT_TEMPLATES.get(language, _ALERT_TEMPLATES["english"])
        template = templates.get(alert_type, templates["generic"])
        return template.format(
            patient_name=patient_name[:255],
            details=details[:1000],
        )


_ALERT_TEMPLATES: dict[str, dict[str, str]] = {
    "english": {
        "side_effect": "🚨 *Nalam Alert* — {patient_name} reported *{details}* after medication. Please consult your doctor today.",
        "no_answer": "⚠️ *Nalam Alert* — {patient_name} has not answered the last 2 calls. Please check on them. Last attempt: {details}",
        "low_adherence": "⚠️ *Nalam Alert* — {patient_name}'s medication adherence dropped to *{details}%* this week. This needs attention.",
        "stock_out": "⚠️ *Nalam Alert* — {patient_name} says medication is finished. Please arrange a refill. Details: {details}",
        "missed_dose": "⚠️ *Nalam Alert* — {patient_name} has missed 3 consecutive doses. Medication: {details}",
        "refill_due": "💊 *Nalam Refill Alert* — {patient_name}'s {details} is running low. Please arrange a refill soon.",
        "generic": "ℹ️ *Nalam Alert* — {patient_name}: {details}",
    },
    "hindi": {
        "side_effect": "🚨 *Nalam Alert* — {patient_name} ne dawai ke baad *{details}* ki shikayat ki hai. Kripya aaj doctor se milein.",
        "no_answer": "⚠️ *Nalam Alert* — {patient_name} ne pichle 2 call ka jawab nahi diya. Kripya unhe check karein. Aakhiri call: {details}",
        "low_adherence": "⚠️ *Nalam Alert* — {patient_name} ki dawai adherence is hafte *{details}%* reh gayi. Dhyan dena zaroori hai.",
        "stock_out": "⚠️ *Nalam Alert* — {patient_name} ki dawai khatam ho gayi hai. Kripya refill ka intezaam karein. Details: {details}",
        "missed_dose": "⚠️ *Nalam Alert* — {patient_name} ne lagatar 3 dose miss kiye. Dawai: {details}",
        "refill_due": "💊 *Nalam Refill Alert* — {patient_name} ki {details} khatam hone wali hai. Kripya refill ka intezaam karein.",
        "generic": "ℹ️ *Nalam Alert* — {patient_name}: {details}",
    },
    "tamil": {
        "side_effect": "🚨 *Nalam எச்சரிக்கை* — {patient_name} மருந்துக்குப் பிறகு *{details}* என்று தெரிவித்தார். இன்று மருத்துவரை அணுகவும்.",
        "no_answer": "⚠️ *Nalam எச்சரிக்கை* — {patient_name} கடந்த 2 அழைப்புகளுக்கு பதிலளிக்கவில்லை. தயவுசெய்து அவரைப் பார்க்கவும். கடைசி முயற்சி: {details}",
        "low_adherence": "⚠️ *Nalam எச்சரிக்கை* — {patient_name}-ன் மருந்து எடுத்துக்கொள்ளும் விகிதம் இந்த வாரம் *{details}%* ஆக உள்ளது. கவனம் தேவை.",
        "stock_out": "⚠️ *Nalam எச்சரிக்கை* — {patient_name}-ன் மருந்து தீர்ந்துவிட்டதாகத் தெரிவித்தார். தயவுசெய்து மீண்டும் வாங்கவும். விவரம்: {details}",
        "missed_dose": "⚠️ *Nalam எச்சரிக்கை* — {patient_name} தொடர்ந்து 3 மருந்து அளவுகளைத் தவறவிட்டார். மருந்து: {details}",
        "refill_due": "💊 *Nalam மீண்டும் வாங்கும் நினைவூட்டல்* — {patient_name}-ன் {details} குறைந்து வருகிறது. விரைவில் மீண்டும் வாங்கவும்.",
        "generic": "ℹ️ *Nalam எச்சரிக்கை* — {patient_name}: {details}",
    },
}
