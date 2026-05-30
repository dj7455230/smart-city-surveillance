"""
CrimeWatch AI — Alert Manager v2
Channels: Telegram, WhatsApp (Twilio), Email, WebSocket
Features: Multi-language alerts, evidence hashing, voice alerts
"""

import os
import smtplib
import asyncio
import hashlib
import httpx
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("crimewatch.alerts")

# ── Multi-language alert templates ───────────────────────────────────────────
ALERT_TEMPLATES = {
    "en": {
        "title":    "🚨 CRIME ALERT — CrimeWatch AI",
        "type":     "Type",
        "severity": "Severity",
        "conf":     "Confidence",
        "camera":   "Camera",
        "persons":  "Persons",
        "time":     "Time",
        "location": "Location",
        "map":      "View on Map",
        "plate":    "Plate",
        "criminal": "Criminal Match",
    },
    "hi": {
        "title":    "🚨 अपराध अलर्ट — CrimeWatch AI",
        "type":     "प्रकार",
        "severity": "गंभीरता",
        "conf":     "विश्वास",
        "camera":   "कैमरा",
        "persons":  "व्यक्ति",
        "time":     "समय",
        "location": "स्थान",
        "map":      "मानचित्र पर देखें",
        "plate":    "नंबर प्लेट",
        "criminal": "अपराधी पहचान",
    },
    "ta": {
        "title":    "🚨 குற்ற எச்சரிக்கை — CrimeWatch AI",
        "type":     "வகை",
        "severity": "தீவிரம்",
        "conf":     "நம்பகத்தன்மை",
        "camera":   "கேமரா",
        "persons":  "நபர்கள்",
        "time":     "நேரம்",
        "location": "இடம்",
        "map":      "வரைபடத்தில் காண்க",
        "plate":    "தகடு",
        "criminal": "குற்றவாளி பொருத்தம்",
    },
    "te": {
        "title":    "🚨 నేర హెచ్చరిక — CrimeWatch AI",
        "type":     "రకం",
        "severity": "తీవ్రత",
        "conf":     "విశ్వాసం",
        "camera":   "కెమెరా",
        "persons":  "వ్యక్తులు",
        "time":     "సమయం",
        "location": "స్థానం",
        "map":      "మ్యాప్‌లో చూడండి",
        "plate":    "నంబర్ ప్లేట్",
        "criminal": "నేరస్థుడు గుర్తింపు",
    },
}

SEVERITY_EMOJI = {
    "CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"
}

CRIME_TYPE_EMOJI = {
    "fight": "🥊", "weapon": "🔫", "accident": "🚗",
    "suspicious": "👁️", "riot": "🚨", "criminal": "🦹",
    "stolen_vehicle": "🚔", "loitering": "⏱️",
}


class AlertManager:
    """
    Unified alert dispatcher — all channels, all languages.
    """

    def __init__(self):
        # Telegram
        self.telegram_token   = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")

        # WhatsApp (Twilio)
        self.twilio_sid       = os.getenv("TWILIO_ACCOUNT_SID", "")
        self.twilio_token     = os.getenv("TWILIO_AUTH_TOKEN", "")
        self.twilio_from      = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
        self.twilio_to        = os.getenv("TWILIO_WHATSAPP_TO", "")

        # Email
        self.smtp_host        = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port        = int(os.getenv("SMTP_PORT", 587))
        self.smtp_user        = os.getenv("SMTP_USER", "")
        self.smtp_pass        = os.getenv("SMTP_PASS", "")
        self.alert_email      = os.getenv("ALERT_EMAIL", "")

        # Language
        self.language         = os.getenv("ALERT_LANGUAGE", "en")
        self.lang             = ALERT_TEMPLATES.get(self.language, ALERT_TEMPLATES["en"])

        # WebSocket clients
        self._ws_clients: set = set()

        # Alert deduplication (avoid spam for same event)
        self._recent_alerts: dict = {}
        self._dedup_window_sec = 10

    # ── WebSocket management ──────────────────────────────────────────────────

    def register_ws_client(self, ws):
        self._ws_clients.add(ws)

    def unregister_ws_client(self, ws):
        self._ws_clients.discard(ws)

    async def broadcast_ws(self, message: dict):
        dead = set()
        for ws in self._ws_clients:
            try:
                await ws.send_json(message)
            except Exception:
                dead.add(ws)
        self._ws_clients -= dead

    # ── Deduplication ─────────────────────────────────────────────────────────

    def _is_duplicate(self, crime_type: str, camera_id: str) -> bool:
        key = f"{crime_type}:{camera_id}"
        now = datetime.utcnow().timestamp()
        if key in self._recent_alerts:
            if now - self._recent_alerts[key] < self._dedup_window_sec:
                return True
        self._recent_alerts[key] = now
        return False

    # ── Main dispatch ─────────────────────────────────────────────────────────

    async def dispatch(self, detection: dict, gps: Optional[dict] = None):
        """Fire all alert channels concurrently"""
        if not detection.get("is_alert"):
            return None

        camera_id = detection.get("camera_id", "CAM-01")
        crime_type = detection.get("crime_type", "unknown")

        if self._is_duplicate(crime_type, camera_id):
            logger.debug(f"[Alert] Duplicate suppressed: {crime_type}@{camera_id}")
            return None

        payload = self._build_payload(detection, gps)

        tasks = [
            self.broadcast_ws(payload),
            self._send_telegram(payload, detection.get("snapshot_path")),
            self._send_whatsapp(payload),
            self._send_email(payload, detection.get("snapshot_path")),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, r in enumerate(results):
            if isinstance(r, Exception):
                logger.warning(f"[Alert] Channel {i} failed: {r}")

        logger.info(f"[Alert] Dispatched: {crime_type} | {payload['severity']} | {payload['id']}")
        return payload

    def _build_payload(self, detection: dict, gps: Optional[dict]) -> dict:
        gps = gps or {"lat": 28.6139, "lng": 77.2090}
        maps_url = f"https://maps.google.com/?q={gps['lat']},{gps['lng']}"

        # Extract sub-engine info
        face_info = detection.get("face", {})
        anpr_info = detection.get("anpr", {})
        crowd_info = detection.get("crowd", {})

        criminal_names = [
            m["identity"] for m in face_info.get("criminal_matches", [])
        ]
        stolen_plates = [
            a.get("plate_text", "") for a in anpr_info.get("alerts", [])
        ]

        return {
            "type":           "CRIME_ALERT",
            "id":             f"ALT-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}",
            "timestamp":      datetime.utcnow().isoformat(),
            "crime_type":     detection["crime_type"],
            "severity":       detection["severity"],
            "confidence":     detection["confidence"],
            "camera_id":      detection.get("camera_id", "CAM-01"),
            "person_count":   detection.get("person_count", 0),
            "vehicle_count":  detection.get("vehicle_count", 0),
            "gps":            gps,
            "maps_url":       maps_url,
            "snapshot_path":  detection.get("snapshot_path", ""),
            "night_mode":     detection.get("night_mode", False),
            # Enhanced info
            "criminal_names": criminal_names,
            "stolen_plates":  stolen_plates,
            "crowd_risk":     crowd_info.get("riot_risk", 0.0),
            "crowd_count":    crowd_info.get("person_count", 0),
        }

    # ── Telegram ──────────────────────────────────────────────────────────────

    async def _send_telegram(self, payload: dict, snapshot_path: Optional[str] = None):
        if not self.telegram_token or not self.telegram_chat_id:
            return

        lang = self.lang
        sev_emoji = SEVERITY_EMOJI.get(payload["severity"], "⚪")
        crime_emoji = CRIME_TYPE_EMOJI.get(payload["crime_type"], "⚠️")

        lines = [
            f"{sev_emoji} *{lang['title']}*\n",
            f"{crime_emoji} *{lang['type']}:* {payload['crime_type'].upper().replace('_', ' ')}",
            f"⚡ *{lang['severity']}:* {payload['severity']}",
            f"🎯 *{lang['conf']}:* {payload['confidence']:.0%}",
            f"📷 *{lang['camera']}:* {payload['camera_id']}",
            f"👥 *{lang['persons']}:* {payload['person_count']}",
            f"🕐 *{lang['time']}:* {payload['timestamp'][:19].replace('T', ' ')} UTC",
            f"📍 *{lang['location']}:* {payload['gps']['lat']:.4f}, {payload['gps']['lng']:.4f}",
        ]

        # Extra info
        if payload.get("criminal_names"):
            lines.append(f"🦹 *{lang['criminal']}:* {', '.join(payload['criminal_names'])}")
        if payload.get("stolen_plates"):
            lines.append(f"🚔 *{lang['plate']}:* {', '.join(payload['stolen_plates'])}")
        if payload.get("crowd_risk", 0) > 0.5:
            lines.append(f"🚨 *Riot Risk:* {payload['crowd_risk']:.0%} ({payload['crowd_count']} persons)")
        if payload.get("night_mode"):
            lines.append("🌙 *Night Vision:* Active")
        if payload.get("maps_url"):
            lines.append(f"\n🗺 [{lang['map']}]({payload['maps_url']})")

        message = "\n".join(lines)
        base_url = f"https://api.telegram.org/bot{self.telegram_token}"

        async with httpx.AsyncClient(timeout=15) as client:
            await client.post(f"{base_url}/sendMessage", json={
                "chat_id": self.telegram_chat_id,
                "text": message,
                "parse_mode": "Markdown",
            })

            if snapshot_path and Path(snapshot_path).exists():
                with open(snapshot_path, "rb") as f:
                    await client.post(
                        f"{base_url}/sendPhoto",
                        data={"chat_id": self.telegram_chat_id, "caption": "📸 Evidence Snapshot"},
                        files={"photo": f},
                    )

            await client.post(f"{base_url}/sendLocation", json={
                "chat_id": self.telegram_chat_id,
                "latitude": payload["gps"]["lat"],
                "longitude": payload["gps"]["lng"],
            })

        logger.info(f"[Telegram] Sent: {payload['id']}")

    # ── WhatsApp (Twilio) ─────────────────────────────────────────────────────

    async def _send_whatsapp(self, payload: dict):
        if not self.twilio_sid or not self.twilio_to:
            logger.debug("[WhatsApp] Not configured, skipping")
            return

        sev_emoji = SEVERITY_EMOJI.get(payload["severity"], "⚪")
        crime_emoji = CRIME_TYPE_EMOJI.get(payload["crime_type"], "⚠️")

        message = (
            f"{sev_emoji} *CrimeWatch AI Alert*\n"
            f"{crime_emoji} {payload['crime_type'].upper().replace('_', ' ')}\n"
            f"Severity: {payload['severity']}\n"
            f"Camera: {payload['camera_id']}\n"
            f"Time: {payload['timestamp'][:19].replace('T', ' ')} UTC\n"
            f"Location: {payload['gps']['lat']:.4f}, {payload['gps']['lng']:.4f}\n"
        )
        if payload.get("criminal_names"):
            message += f"⚠️ Criminal: {', '.join(payload['criminal_names'])}\n"
        if payload.get("stolen_plates"):
            message += f"🚔 Stolen Plate: {', '.join(payload['stolen_plates'])}\n"
        if payload.get("maps_url"):
            message += f"📍 {payload['maps_url']}"

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._send_whatsapp_sync, message)

    def _send_whatsapp_sync(self, message: str):
        try:
            from twilio.rest import Client
            client = Client(self.twilio_sid, self.twilio_token)
            client.messages.create(
                from_=self.twilio_from,
                body=message,
                to=self.twilio_to,
            )
            logger.info("[WhatsApp] Alert sent ✓")
        except Exception as e:
            logger.warning(f"[WhatsApp] Failed: {e}")

    # ── Email ─────────────────────────────────────────────────────────────────

    async def _send_email(self, payload: dict, snapshot_path: Optional[str] = None):
        if not self.smtp_user or not self.alert_email:
            return
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._send_email_sync, payload, snapshot_path)

    def _send_email_sync(self, payload: dict, snapshot_path: Optional[str]):
        severity_color = {
            "CRITICAL": "#dc2626", "HIGH": "#ea580c",
            "MEDIUM": "#ca8a04", "LOW": "#16a34a"
        }.get(payload["severity"], "#6b7280")

        extra_rows = ""
        if payload.get("criminal_names"):
            extra_rows += f"<tr><td style='padding:8px;color:#94a3b8'>Criminal Match</td><td style='padding:8px;color:#f87171;font-weight:bold'>{', '.join(payload['criminal_names'])}</td></tr>"
        if payload.get("stolen_plates"):
            extra_rows += f"<tr><td style='padding:8px;color:#94a3b8'>Stolen Plate</td><td style='padding:8px;color:#f87171;font-weight:bold'>{', '.join(payload['stolen_plates'])}</td></tr>"
        if payload.get("crowd_risk", 0) > 0.5:
            extra_rows += f"<tr><td style='padding:8px;color:#94a3b8'>Riot Risk</td><td style='padding:8px;color:#f87171;font-weight:bold'>{payload['crowd_risk']:.0%} ({payload['crowd_count']} persons)</td></tr>"

        # Compute evidence hash
        evidence_hash = ""
        if snapshot_path and Path(snapshot_path).exists():
            with open(snapshot_path, "rb") as f:
                evidence_hash = hashlib.sha256(f.read()).hexdigest()

        html = f"""
        <html><body style="font-family:Arial,sans-serif;background:#0f172a;color:#e2e8f0;padding:20px">
        <div style="max-width:620px;margin:auto;background:#1e293b;border-radius:12px;overflow:hidden;border:1px solid #334155">
          <div style="background:{severity_color};padding:20px;text-align:center">
            <h1 style="color:white;margin:0;font-size:22px">🚨 CRIME ALERT — CrimeWatch AI</h1>
            <p style="color:rgba(255,255,255,0.85);margin:6px 0 0">{payload['severity']} SEVERITY · {payload['crime_type'].upper().replace('_',' ')}</p>
          </div>
          <div style="padding:24px">
            <table style="width:100%;border-collapse:collapse">
              <tr><td style="padding:8px;color:#94a3b8">Crime Type</td>
                  <td style="padding:8px;font-weight:bold;color:#f1f5f9">{payload['crime_type'].upper().replace('_',' ')}</td></tr>
              <tr><td style="padding:8px;color:#94a3b8">Confidence</td>
                  <td style="padding:8px;color:#f1f5f9">{payload['confidence']:.0%}</td></tr>
              <tr><td style="padding:8px;color:#94a3b8">Camera</td>
                  <td style="padding:8px;color:#f1f5f9">{payload['camera_id']}</td></tr>
              <tr><td style="padding:8px;color:#94a3b8">Persons Detected</td>
                  <td style="padding:8px;color:#f1f5f9">{payload['person_count']}</td></tr>
              <tr><td style="padding:8px;color:#94a3b8">Timestamp (UTC)</td>
                  <td style="padding:8px;color:#f1f5f9">{payload['timestamp'][:19].replace('T',' ')}</td></tr>
              <tr><td style="padding:8px;color:#94a3b8">GPS Coordinates</td>
                  <td style="padding:8px;color:#f1f5f9">{payload['gps']['lat']:.5f}, {payload['gps']['lng']:.5f}</td></tr>
              {extra_rows}
            </table>
            <div style="margin-top:20px;display:flex;gap:12px;flex-wrap:wrap">
              <a href="{payload.get('maps_url','#')}"
                 style="background:#3b82f6;color:white;padding:10px 20px;border-radius:8px;text-decoration:none;font-size:14px">
                📍 View on Map
              </a>
              <a href="http://localhost:3000/alerts"
                 style="background:#334155;color:#e2e8f0;padding:10px 20px;border-radius:8px;text-decoration:none;font-size:14px">
                🖥 Open Dashboard
              </a>
            </div>
            {f'<div style="margin-top:16px;padding:12px;background:#0f172a;border-radius:8px;font-size:11px;color:#475569;font-family:monospace">Evidence SHA-256: {evidence_hash}</div>' if evidence_hash else ''}
          </div>
          <div style="background:#0f172a;padding:12px;text-align:center;font-size:11px;color:#475569">
            CrimeWatch AI · Alert ID: {payload['id']} · Automated System
          </div>
        </div>
        </body></html>
        """

        msg = MIMEMultipart("related")
        msg["Subject"] = f"🚨 [{payload['severity']}] {payload['crime_type'].upper().replace('_',' ')} — CrimeWatch AI"
        msg["From"] = self.smtp_user
        msg["To"] = self.alert_email
        msg.attach(MIMEText(html, "html"))

        if snapshot_path and Path(snapshot_path).exists():
            with open(snapshot_path, "rb") as f:
                img = MIMEImage(f.read(), name="evidence.jpg")
                img.add_header("Content-Disposition", "attachment", filename="evidence.jpg")
                msg.attach(img)

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_pass)
                server.send_message(msg)
            logger.info(f"[Email] Sent to {self.alert_email}")
        except Exception as e:
            logger.warning(f"[Email] Failed: {e}")
