from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage

log = logging.getLogger(__name__)


def _config() -> dict:
    try:
        port = int(os.environ.get("SMTP_PORT", "587"))
    except ValueError:
        port = 587
    return {
        "host": os.environ.get("SMTP_HOST"),
        "port": port,
        "user": os.environ.get("SMTP_USER"),
        "password": os.environ.get("SMTP_PASSWORD"),
        "from": os.environ.get("SMTP_FROM", "support@6tlengineering.com"),
        "to": os.environ.get("SOPORTE_EMAIL_TO", "support@6tlengineering.com"),
    }


def construir_mensaje(solicitud, cfg: dict) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = f"Nueva solicitud de soporte {solicitud.codigo}"
    msg["From"] = cfg["from"]
    msg["To"] = cfg["to"]
    empresa = f" ({solicitud.empresa})" if solicitud.empresa else ""
    cuerpo = (
        f"Nueva solicitud de soporte {solicitud.codigo}\n\n"
        f"Contacto: {solicitud.nombre_contacto}{empresa}\n"
        f"Email: {solicitud.email_contacto}\n"
        f"Teléfono: {solicitud.telefono_contacto or '-'}\n"
        f"Equipo (texto): SN={solicitud.numero_serie_texto or '-'} / "
        f"PN={solicitud.part_number_texto or '-'}\n\n"
        f"Título: {solicitud.titulo}\n\n"
        f"{solicitud.descripcion_problema}\n"
    )
    msg.set_content(cuerpo)
    return msg


def _enviar_smtp(msg: EmailMessage, cfg: dict) -> None:
    with smtplib.SMTP(cfg["host"], cfg["port"]) as s:
        s.starttls()
        if cfg["user"]:
            s.login(cfg["user"], cfg["password"])
        s.send_message(msg)


def enviar_aviso_solicitud(solicitud, transporte=None) -> bool:
    """Envía el aviso de una nueva solicitud. Best-effort: nunca relanza.

    `transporte` es un callable `(msg, cfg) -> None` (inyectable para tests);
    por defecto usa SMTP real. Devuelve True si se envió, False si no.
    """
    cfg = _config()
    if not cfg["host"]:
        log.info("SMTP no configurado; no se envía aviso de %s", solicitud.codigo)
        return False
    enviar = transporte or _enviar_smtp
    try:
        enviar(construir_mensaje(solicitud, cfg), cfg)
        return True
    except Exception:
        log.exception("Fallo enviando aviso de solicitud %s", solicitud.codigo)
        return False
