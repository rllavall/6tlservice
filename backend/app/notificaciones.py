"""Canales de notificación best-effort (email / Telegram). Sin dependencias externas.
Canal sin configurar (faltan variables de entorno) -> devuelve None (no-op). Nunca relanza."""
from __future__ import annotations

import json
import logging
import os
import urllib.request
from email.message import EmailMessage
from typing import Optional

from app import email_notify

log = logging.getLogger(__name__)


def _destinatarios_email() -> list[str]:
    raw = os.environ.get("NOTIF_EMAIL_TO") or email_notify._config().get("to")
    return [e.strip() for e in raw.split(",") if e.strip()] if raw else []


def enviar_email(asunto: str, cuerpo: str, *, transporte=None) -> Optional[bool]:
    cfg = email_notify._config()
    destinatarios = _destinatarios_email()
    if not cfg["host"] or not destinatarios:
        return None
    msg = EmailMessage()
    msg["Subject"] = asunto
    msg["From"] = cfg["from"]
    msg["To"] = ", ".join(destinatarios)
    msg.set_content(cuerpo)
    enviar = transporte or email_notify._enviar_smtp
    try:
        enviar(msg, cfg)
        return True
    except Exception:
        log.exception("Fallo enviando email de notificación")
        return False


def _http_post_telegram(token: str, chat_id: str, texto: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = json.dumps({"chat_id": chat_id, "text": texto}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=10).read()


def enviar_telegram(texto: str, *, http_post=None) -> Optional[bool]:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return None
    poster = http_post or _http_post_telegram
    try:
        poster(token, chat_id, texto)
        return True
    except Exception:
        log.exception("Fallo enviando Telegram")
        return False


def notificar(asunto: str, cuerpo: str, *, email_fn=enviar_email, telegram_fn=enviar_telegram) -> dict:
    """Dispara todos los canales configurados. Devuelve {canal: True|False|None}."""
    return {
        "email": email_fn(asunto, cuerpo),
        "telegram": telegram_fn(f"{asunto}\n\n{cuerpo}"),
    }
