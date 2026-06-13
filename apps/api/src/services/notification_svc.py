"""
TradeFlow AI — Notification Service (T-074)

Sends notifications via:
  1. Resend (email)
  2. WhatsApp Business API (optional, behind feature flag)

Called on:
  - REVIEW_READY → operator email
  - ACCEPTED / REJECTED → importer email + WhatsApp (if enabled)
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger("services.notification")

RESEND_API_URL = "https://api.resend.com/emails"


class NotificationService:
    def __init__(self, settings: Any) -> None:
        self._settings = settings

    async def notify_review_ready(
        self,
        batch_id: str,
        operator_email: str,
        crs_score: int,
        risk_level: str,
    ) -> None:
        """Notify operator that a batch is ready for review."""
        if not self._settings.RESEND_API_KEY:
            logger.info("RESEND_API_KEY not set — skipping email notification")
            return

        subject = f"[TradeFlow AI] Batch {batch_id[:8]}… ready for review"
        html = f"""
        <h2>Batch Ready for Review</h2>
        <p>A new import declaration batch is ready for your review.</p>
        <table>
            <tr><td><b>Batch ID</b></td><td>{batch_id}</td></tr>
            <tr><td><b>CRS Score</b></td><td>{crs_score}/100</td></tr>
            <tr><td><b>Risk Level</b></td><td>{risk_level}</td></tr>
        </table>
        <p><a href="https://app.tradeflow.ai/batches/{batch_id}">Review Now →</a></p>
        """
        await self._send_email(to=operator_email, subject=subject, html=html)

    async def notify_ceisa_result(
        self,
        batch_id: str,
        ceisa_status: str,
        aju_number: str,
        recipient_email: str,
        recipient_phone: str | None = None,
    ) -> None:
        """Notify importer of CEISA acceptance or rejection."""
        accepted = ceisa_status == "ACCEPTED"
        subject = (
            f"[TradeFlow AI] PIB {'Diterima' if accepted else 'Ditolak'} — AJU {aju_number}"
        )
        html = f"""
        <h2>{"✅ PIB Diterima" if accepted else "❌ PIB Ditolak"}</h2>
        <p>Status PIB Anda telah diperbarui:</p>
        <table>
            <tr><td><b>Batch ID</b></td><td>{batch_id}</td></tr>
            <tr><td><b>Nomor AJU</b></td><td>{aju_number}</td></tr>
            <tr><td><b>Status</b></td><td>{ceisa_status}</td></tr>
        </table>
        <p><a href="https://app.tradeflow.ai/batches/{batch_id}">Lihat Detail →</a></p>
        """
        await self._send_email(to=recipient_email, subject=subject, html=html)

        # WhatsApp (optional)
        if (
            self._settings.ENABLE_NOTIFICATIONS_WHATSAPP
            and recipient_phone
            and self._settings.WHATSAPP_TOKEN
        ):
            msg = (
                f"TradeFlow AI: PIB Anda {'*DITERIMA*' if accepted else '*DITOLAK*'} "
                f"oleh CEISA. Nomor AJU: {aju_number}. "
                f"Detail: https://app.tradeflow.ai/batches/{batch_id}"
            )
            await self._send_whatsapp(phone=recipient_phone, message=msg)

    async def _send_email(self, to: str, subject: str, html: str) -> None:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    RESEND_API_URL,
                    headers={
                        "Authorization": f"Bearer {self._settings.RESEND_API_KEY.get_secret_value()}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "from": self._settings.NOTIFICATION_EMAIL_FROM,
                        "to": [to],
                        "subject": subject,
                        "html": html,
                    },
                )
                resp.raise_for_status()
                logger.info(f"Email sent to {to}: {subject}")
        except Exception as e:
            logger.error(f"Email send failed: {e}")

    async def _send_whatsapp(self, phone: str, message: str) -> None:
        try:
            phone_id = self._settings.WHATSAPP_PHONE_NUMBER_ID
            token = self._settings.WHATSAPP_TOKEN.get_secret_value()
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"https://graph.facebook.com/v20.0/{phone_id}/messages",
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "messaging_product": "whatsapp",
                        "to": phone.replace("+", ""),
                        "type": "text",
                        "text": {"body": message},
                    },
                )
                resp.raise_for_status()
                logger.info(f"WhatsApp sent to {phone}")
        except Exception as e:
            logger.error(f"WhatsApp send failed: {e}")
