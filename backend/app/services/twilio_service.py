"""Twilio WhatsApp messaging service with multilingual alert formatting."""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class TwilioService:
    """Async Twilio client using httpx (no SDK dependency)."""

    def __init__(self, account_sid: str, auth_token: str, whatsapp_from: str) -> None:
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.whatsapp_from = whatsapp_from  # e.g. "whatsapp:+14155238886"
        self._api_url = (
            f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
        )

    # ------------------------------------------------------------------
    # Send
    # ------------------------------------------------------------------

    async def send_whatsapp(self, to: str, body: str) -> dict[str, Any]:
        """
        Send a WhatsApp message via the Twilio REST API.

        Args:
            to: Recipient in E.164 format (e.g. +919876543210).
            body: Message text.

        Returns:
            Dict with ``sid`` on success, or ``error`` key on failure.
        """
        form_data = {
            "From": self.whatsapp_from,
            "To": f"whatsapp:{to}",
            "Body": body,
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    self._api_url,
                    data=form_data,
                    auth=(self.account_sid, self.auth_token),
                )
                resp.raise_for_status()
                result = resp.json()
                logger.info("WhatsApp sent to %s — SID %s", to, result.get("sid"))
                return result
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Twilio HTTP %s sending to %s: %s",
                exc.response.status_code,
                to,
                exc.response.text,
            )
            return {"error": True, "status_code": exc.response.status_code, "detail": exc.response.text}
        except Exception:
            logger.exception("Failed to send WhatsApp to %s", to)
            return {"error": True, "detail": "unexpected_error"}

    # ------------------------------------------------------------------
    # Formatting — Daily Summary
    # ------------------------------------------------------------------

    def format_daily_summary(self, summary: dict[str, Any], language: str = "english") -> str:
        """
        Format a daily adherence summary for WhatsApp.

        Expected ``summary`` keys:
            patient_name, doses_taken, total_doses_today, slot_statuses (dict of slot→status),
            adherence_score_7d, dashboard_link (optional)
        """
        name = summary.get("patient_name", "Patient")
        taken = summary.get("doses_taken", 0)
        total = summary.get("total_doses_today", 0)
        slots: dict[str, str] = summary.get("slot_statuses", {})
        score = summary.get("adherence_score_7d", 0.0)
        link = summary.get("dashboard_link", "")

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

        # Default: English
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

    # ------------------------------------------------------------------
    # Formatting — Urgent Alert
    # ------------------------------------------------------------------

    def format_alert(
        self,
        alert_type: str,
        patient_name: str,
        details: str,
        language: str = "english",
    ) -> str:
        """Format an urgent alert message for WhatsApp, localised."""
        templates = _ALERT_TEMPLATES.get(language, _ALERT_TEMPLATES["english"])
        template = templates.get(alert_type, templates.get("generic", "Nalam Alert — {patient_name}: {details}"))
        return template.format(patient_name=patient_name, details=details)


# ---------------------------------------------------------------------------
# Hardcoded multilingual alert templates
# ---------------------------------------------------------------------------

_ALERT_TEMPLATES: dict[str, dict[str, str]] = {
    "english": {
        "side_effect": (
            "🚨 *Nalam Alert* — {patient_name} reported *{details}* after medication. "
            "Please consult your doctor today."
        ),
        "no_answer": (
            "⚠️ *Nalam Alert* — {patient_name} has not answered the last 2 calls. "
            "Please check on them. Last attempt: {details}"
        ),
        "low_adherence": (
            "⚠️ *Nalam Alert* — {patient_name}'s medication adherence dropped to *{details}%* this week. "
            "This needs attention."
        ),
        "stock_out": (
            "⚠️ *Nalam Alert* — {patient_name} says medication is finished. "
            "Please arrange a refill. Details: {details}"
        ),
        "missed_dose": (
            "⚠️ *Nalam Alert* — {patient_name} has missed 3 consecutive doses. "
            "Medication: {details}"
        ),
        "refill_due": (
            "💊 *Nalam Refill Alert* — {patient_name}'s {details} is running low. "
            "Please arrange a refill soon."
        ),
        "generic": "ℹ️ *Nalam Alert* — {patient_name}: {details}",
    },
    "hindi": {
        "side_effect": (
            "🚨 *Nalam Alert* — {patient_name} ne dawai ke baad *{details}* ki shikayat ki hai. "
            "Kripya aaj doctor se milein."
        ),
        "no_answer": (
            "⚠️ *Nalam Alert* — {patient_name} ne pichle 2 call ka jawab nahi diya. "
            "Kripya unhe check karein. Aakhiri call: {details}"
        ),
        "low_adherence": (
            "⚠️ *Nalam Alert* — {patient_name} ki dawai adherence is hafte *{details}%* reh gayi. "
            "Dhyan dena zaroori hai."
        ),
        "stock_out": (
            "⚠️ *Nalam Alert* — {patient_name} ki dawai khatam ho gayi hai. "
            "Kripya refill ka intezaam karein. Details: {details}"
        ),
        "missed_dose": (
            "⚠️ *Nalam Alert* — {patient_name} ne lagatar 3 dose miss kiye. "
            "Dawai: {details}"
        ),
        "refill_due": (
            "💊 *Nalam Refill Alert* — {patient_name} ki {details} khatam hone wali hai. "
            "Kripya refill ka intezaam karein."
        ),
        "generic": "ℹ️ *Nalam Alert* — {patient_name}: {details}",
    },
    "tamil": {
        "side_effect": (
            "🚨 *Nalam Alert* — {patient_name} marunthu eduthathukku piraghu *{details}* endru theruvithar. "
            "Inru doctor-ai santhikkavum."
        ),
        "no_answer": (
            "⚠️ *Nalam Alert* — {patient_name} kadantha 2 calls-ku pathil alikkavillai. "
            "Thayavu seithu avargalai paarkavum. Kadaisi muyarchi: {details}"
        ),
        "low_adherence": (
            "⚠️ *Nalam Alert* — {patient_name}-in marunthu adherence intha vaaram *{details}%* aaga kuriainthathu. "
            "Kavanikkavum."
        ),
        "stock_out": (
            "⚠️ *Nalam Alert* — {patient_name}-in marunthu mudintha viduthathaaga theruvikkiraar. "
            "Thayavu seithu refill seiyyavum. Details: {details}"
        ),
        "missed_dose": (
            "⚠️ *Nalam Alert* — {patient_name} thodarchiyaaga 3 doses edukkavillai. "
            "Marunthu: {details}"
        ),
        "refill_due": (
            "💊 *Nalam Refill Alert* — {patient_name}-in {details} mudivathai eduthal. "
            "Thayavu seithu refill seiyyavum."
        ),
        "generic": "ℹ️ *Nalam Alert* — {patient_name}: {details}",
    },
}
