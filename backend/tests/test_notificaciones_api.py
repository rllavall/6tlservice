from __future__ import annotations

from datetime import date

from app import models


def _seed_aviso(db):
    """Crea un equipo con contrato vigente + incidencia antigua -> total del digest > 0."""
    p = models.Producto(part_number="6TL-API", tipo="equipo", descripcion="Banco")
    db.add(p); db.flush()
    con = models.ContratoMantenimiento(codigo="CTR-API", nivel="bronze",
        fecha_inicio=date(2020, 1, 1), fecha_fin=date(2100, 1, 1))
    db.add(con); db.flush()
    eq = models.Equipo(numero_serie="API1", producto_id=p.id, contrato_id=con.id)
    db.add(eq); db.flush()
    inc = models.Incidencia(codigo="RMA-API", tipo="rma", estado="abierta", equipo_id=eq.id,
        titulo="t", descripcion_problema="d", prioridad="media", fecha_apertura=date(2020, 1, 1))
    db.add(inc); db.commit()


def test_digest_dry_run_no_envia(client):
    out = client.post("/api/notificaciones/digest?dry_run=true").json()
    assert out["enviado"] is False
    assert out["canales"] is None
    assert isinstance(out["cuerpo"], str)
    assert set(out["resumen"].keys()) == {
        "preventivos_vencidos", "preventivos_proximos", "contratos_por_caducar",
        "sla_en_riesgo", "sla_incumplidas"}


def test_digest_envia_sin_canales(client, db_session, monkeypatch):
    for var in ("SMTP_HOST", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        monkeypatch.delenv(var, raising=False)
    _seed_aviso(db_session)  # hay avisos -> sí envía (aunque sin canales configurados)
    out = client.post("/api/notificaciones/digest").json()
    assert out["enviado"] is True
    assert out["canales"] == {"email": None, "telegram": None}


def test_digest_no_envia_si_vacio(client):
    # BD sin avisos -> total 0 -> no se envía nada
    out = client.post("/api/notificaciones/digest").json()
    assert out["total"] == 0
    assert out["enviado"] is False
    assert out["canales"] == {"email": None, "telegram": None}


def test_digest_protegido_401(client_sin_auth):
    assert client_sin_auth.post("/api/notificaciones/digest").status_code == 401


def test_transicion_incidencia_sigue_funcionando(client):
    prod = client.post("/api/productos", json={
        "part_number": "6TL-TN", "tipo": "equipo", "descripcion": "B"}).json()
    eq = client.post("/api/equipos", json={"numero_serie": "TN1", "producto_id": prod["id"]}).json()
    inc = client.post("/api/incidencias", json={
        "tipo": "soporte_tecnico", "equipo_id": eq["id"], "titulo": "x",
        "descripcion_problema": "y", "prioridad": "media", "fecha_apertura": "2026-06-01"}).json()
    r = client.post(f"/api/incidencias/{inc['id']}/transicion", json={"nuevo_estado": "diagnostico"})
    assert r.status_code == 200
    assert r.json()["estado"] == "diagnostico"


def test_transicion_no_dispara_notificacion(client, monkeypatch):
    """Una transición de incidencia NO debe enviar notificación (evita floods por
    operaciones masivas/seed). Las notificaciones quedan solo en el digest diario."""
    from app import notificaciones_service
    llamadas = {"n": 0}
    monkeypatch.setattr(notificaciones_service, "notificar_incidencia",
                        lambda *a, **k: llamadas.__setitem__("n", llamadas["n"] + 1))
    prod = client.post("/api/productos", json={
        "part_number": "6TL-NN", "tipo": "equipo", "descripcion": "B"}).json()
    eq = client.post("/api/equipos", json={"numero_serie": "NN1", "producto_id": prod["id"]}).json()
    inc = client.post("/api/incidencias", json={
        "tipo": "soporte_tecnico", "equipo_id": eq["id"], "titulo": "x",
        "descripcion_problema": "y", "prioridad": "media", "fecha_apertura": "2026-06-01"}).json()
    r = client.post(f"/api/incidencias/{inc['id']}/transicion", json={"nuevo_estado": "diagnostico"})
    assert r.status_code == 200
    assert llamadas["n"] == 0
