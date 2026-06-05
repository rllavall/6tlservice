from __future__ import annotations

import json
from datetime import date, datetime

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from app import models

_EXCLUIDAS = {models.AuditoriaLog, models.Sesion}
_CAMPOS_SENSIBLES = {"password_hash", "token"}


def _serializar(valor):
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    if valor is None or isinstance(valor, (str, int, float, bool)):
        return valor
    return str(valor)


def _columnas(obj) -> list[str]:
    return [c.key for c in inspect(obj).mapper.column_attrs]


def _valores_actuales(obj) -> dict:
    out = {}
    for col in _columnas(obj):
        out[col] = "***" if col in _CAMPOS_SENSIBLES else _serializar(getattr(obj, col))
    return out


def _diff_edicion(obj) -> dict:
    estado = inspect(obj)
    cambios = {}
    for col in _columnas(obj):
        hist = estado.attrs[col].history
        if not hist.has_changes():
            continue
        if col in _CAMPOS_SENSIBLES:
            cambios[col] = ["***", "***"]
        else:
            antes = hist.deleted[0] if hist.deleted else None
            despues = hist.added[0] if hist.added else None
            cambios[col] = [_serializar(antes), _serializar(despues)]
    return cambios


def _usuario(session: Session):
    return (
        session.info.get("usuario_id"),
        session.info.get("usuario_username") or "sistema",
    )


def _registrar(session: Session) -> None:
    pendientes = session.info.setdefault("_audit", [])
    uid, uname = _usuario(session)
    ahora = datetime.now()

    for obj in session.new:
        if type(obj) in _EXCLUIDAS:
            continue
        pendientes.append({"obj": obj, "entidad": obj.__tablename__, "accion": "alta",
                           "cambios": {k: [None, v] for k, v in _valores_actuales(obj).items()},
                           "uid": uid, "uname": uname, "ahora": ahora, "entidad_id": None})

    for obj in session.dirty:
        if type(obj) in _EXCLUIDAS or not session.is_modified(obj, include_collections=False):
            continue
        diff = _diff_edicion(obj)
        if not diff:
            continue
        ident = inspect(obj).identity
        pendientes.append({"obj": obj, "entidad": obj.__tablename__, "accion": "edicion",
                           "cambios": diff, "uid": uid, "uname": uname, "ahora": ahora,
                           "entidad_id": ident[0] if ident else None})

    for obj in session.deleted:
        if type(obj) in _EXCLUIDAS:
            continue
        ident = inspect(obj).identity
        pendientes.append({"obj": None, "entidad": obj.__tablename__, "accion": "borrado",
                           "cambios": _valores_actuales(obj), "uid": uid, "uname": uname,
                           "ahora": ahora, "entidad_id": ident[0] if ident else None})


def _pk_valor(obj) -> object:
    """Lee el valor del primer campo PK del objeto directamente (funciona en after_flush)."""
    pk_keys = [c.key for c in inspect(obj).mapper.primary_key]
    if pk_keys:
        return getattr(obj, pk_keys[0], None)
    return None


def _emitir(session: Session) -> None:
    pendientes = session.info.pop("_audit", [])
    if not pendientes:
        return
    filas = []
    for p in pendientes:
        entidad_id = p.get("entidad_id")
        if entidad_id is None and p["obj"] is not None:
            entidad_id = _pk_valor(p["obj"])
        filas.append({
            "fecha_hora": p["ahora"], "usuario_id": p["uid"], "usuario_username": p["uname"],
            "entidad": p["entidad"], "entidad_id": entidad_id, "accion": p["accion"],
            "cambios": json.dumps(p["cambios"], ensure_ascii=False),
        })
    session.execute(models.AuditoriaLog.__table__.insert(), filas)


_ENGANCHADO = False


def registrar_listeners() -> None:
    """Engancha los listeners de auditoría a la clase Session (idempotente vía flag de módulo)."""
    global _ENGANCHADO
    if _ENGANCHADO:
        return
    event.listen(Session, "before_flush", lambda s, fc, i: _registrar(s))
    event.listen(Session, "after_flush", lambda s, fc: _emitir(s))
    _ENGANCHADO = True
