from __future__ import annotations


def test_digest_dry_run_no_envia(client):
    out = client.post("/api/notificaciones/digest?dry_run=true").json()
    assert out["enviado"] is False
    assert out["canales"] is None
    assert isinstance(out["cuerpo"], str)
    assert set(out["resumen"].keys()) == {
        "preventivos_vencidos", "preventivos_proximos", "contratos_por_caducar",
        "sla_en_riesgo", "sla_incumplidas"}


def test_digest_envia_sin_canales(client, monkeypatch):
    for var in ("SMTP_HOST", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        monkeypatch.delenv(var, raising=False)
    out = client.post("/api/notificaciones/digest").json()
    assert out["enviado"] is True
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
