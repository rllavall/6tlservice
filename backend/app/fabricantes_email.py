"""Emails best-effort para activación de garantía y RMA hacia fabricante.
Nunca relanzan. El transporte `(msg, cfg) -> None` es inyectable para tests."""
from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage

from app import fabricantes as fab

log = logging.getLogger(__name__)


def _config() -> dict:
    return {
        "from": os.environ.get("SMTP_FROM", "support@6tlengineering.com"),
        "to": os.environ.get("FABRICANTES_EMAIL_TO", "support@6tlengineering.com"),
        "host": os.environ.get("SMTP_HOST"),
        "port": int(os.environ.get("SMTP_PORT", "587") or "587"),
        "user": os.environ.get("SMTP_USER"),
        "password": os.environ.get("SMTP_PASSWORD"),
    }


def _enviar_smtp(msg: EmailMessage, cfg: dict) -> None:
    with smtplib.SMTP(cfg["host"], cfg["port"]) as s:
        s.starttls()
        if cfg["user"]:
            s.login(cfg["user"], cfg["password"])
        s.send_message(msg)


def construir_email_activacion(componente, fabricante, cfg: dict) -> EmailMessage:
    msg = EmailMessage()
    nombre = getattr(fabricante, "nombre", "fabricante")
    serie = getattr(componente, "numero_serie", "-")
    destino_fab = fab.destino_activacion(fabricante) or "-"
    msg["Subject"] = f"Activación de garantía {nombre} — SN {serie}"
    msg["From"] = cfg["from"]
    msg["To"] = cfg["to"]
    cuerpo = (
        f"Solicitud de activación de garantía.\n\n"
        f"Fabricante: {nombre}\n"
        f"Número de serie: {serie}\n"
        f"Email del fabricante: {destino_fab}\n"
        f"Requiere activación web: {'sí' if fab.requiere_web(fabricante) else 'no'}\n\n"
        f"Activa la garantía con el fabricante y registra la fecha y la referencia "
        f"en la ficha del componente.\n"
    )
    msg.set_content(cuerpo)
    return msg


def construir_email_rma(derivacion, fabricante, cfg: dict) -> EmailMessage:
    msg = EmailMessage()
    nombre = getattr(fabricante, "nombre", "fabricante")
    tu_ref = getattr(derivacion, "tu_referencia", "-")
    ref_ext = getattr(derivacion, "referencia_externa", None) or "(pendiente)"
    destino_fab = fab.destino_rma(fabricante) or "-"
    msg["Subject"] = f"RMA {tu_ref} hacia {nombre}"
    msg["From"] = cfg["from"]
    msg["To"] = cfg["to"]
    cuerpo = (
        f"Apertura de RMA hacia fabricante.\n\n"
        f"Fabricante: {nombre}\n"
        f"Referencia interna (nuestra): {tu_ref}\n"
        f"Referencia del fabricante: {ref_ext}\n"
        f"Email del fabricante: {destino_fab}\n"
    )
    msg.set_content(cuerpo)
    return msg


def _enviar(construir, *args, transporte=None) -> bool:
    cfg = _config()
    enviar = transporte or _enviar_smtp
    if transporte is None and not cfg["host"]:
        log.info("SMTP no configurado; no se envía email de fabricante")
        return False
    try:
        enviar(construir(*args, cfg), cfg)
        return True
    except Exception:
        log.exception("Fallo enviando email de fabricante")
        return False


def enviar_activacion(componente, fabricante, transporte=None) -> bool:
    return _enviar(construir_email_activacion, componente, fabricante, transporte=transporte)


def enviar_rma(derivacion, fabricante, transporte=None) -> bool:
    return _enviar(construir_email_rma, derivacion, fabricante, transporte=transporte)
