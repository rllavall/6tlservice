from datetime import date

from app import models
from app.deps import get_consultar_fabricante
from app.main import app


def _seed(db):
    pe = models.Producto(part_number="IUTB-01", tipo="equipo", descripcion="iUTB")
    cli = models.Cliente(nombre="Indra")
    db.add_all([pe, cli]); db.flush()
    eq = models.Equipo(numero_serie="SN-RT", producto_id=pe.id, cliente_id=cli.id,
                       estado="operativo")
    db.add(eq); db.flush()
    pc = models.Producto(part_number="P-ACT", tipo="componente", descripcion="Cable",
                         fabricante="Beta", pn_fabricante="BET-1", estado_ciclo_vida="activo")
    db.add(pc); db.flush()
    db.add(models.Componente(numero_serie="C1", producto_id=pc.id, equipo_id=eq.id, posicion="1"))
    db.commit()
    return eq.id


def test_get_report_200(client, db_session):
    eq_id = _seed(db_session)
    resp = client.get(f"/api/equipos/{eq_id}/obsolescencia")
    assert resp.status_code == 200
    body = resp.json()
    assert body["banco"]["numero_serie"] == "SN-RT"
    assert body["resumen"]["total"] == 1
    assert body["componentes"][0]["part_number"] == "P-ACT"


def test_get_report_404(client):
    assert client.get("/api/equipos/9999/obsolescencia").status_code == 404


def test_export_xlsx_headers(client, db_session):
    eq_id = _seed(db_session)
    resp = client.get(f"/api/equipos/{eq_id}/obsolescencia/export?formato=xlsx")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == \
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "attachment" in resp.headers["content-disposition"]
    assert "SN-RT" in resp.headers["content-disposition"]
    assert resp.content[:4] == b"PK\x03\x04"


def test_export_pdf_headers(client, db_session):
    eq_id = _seed(db_session)
    resp = client.get(f"/api/equipos/{eq_id}/obsolescencia/export?formato=pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:5] == b"%PDF-"


def test_export_formato_invalido_422(client, db_session):
    eq_id = _seed(db_session)
    assert client.get(f"/api/equipos/{eq_id}/obsolescencia/export?formato=csv").status_code == 422


def test_export_expone_content_disposition_cors(client, db_session):
    # En dev el front (otro origen) debe poder leer el filename del Content-Disposition.
    eq_id = _seed(db_session)
    resp = client.get(f"/api/equipos/{eq_id}/obsolescencia/export?formato=xlsx",
                      headers={"Origin": "http://localhost:8080"})
    assert resp.status_code == 200
    assert "Content-Disposition" in resp.headers.get("access-control-expose-headers", "")


def test_report_requiere_auth(client_sin_auth, db_session):
    eq_id = _seed(db_session)
    assert client_sin_auth.get(f"/api/equipos/{eq_id}/obsolescencia").status_code == 401


def test_refrescar_usa_consultar_inyectado(client, db_session):
    eq_id = _seed(db_session)

    def fake_consultar(producto, url, *, on_paso=None):
        if on_paso:
            on_paso({"descripcion": "🔎 Buscando"})
        return {"estado": "obsoleto", "fecha_evento": None,
                "url_fuente": "http://beta/eol", "resumen": "EOL",
                "tokens_total": 777, "estado_consulta": "ok"}

    app.dependency_overrides[get_consultar_fabricante] = lambda: fake_consultar
    try:
        resp = client.post(f"/api/equipos/{eq_id}/obsolescencia/refrescar?limite=5")
    finally:
        app.dependency_overrides.pop(get_consultar_fabricante, None)

    assert resp.status_code == 200
    assert resp.json()["componentes"][0]["estado_ciclo_vida"] == "obsoleto"
    p = db_session.query(models.Producto).filter_by(part_number="P-ACT").one()
    db_session.refresh(p)
    assert p.estado_ciclo_vida == "obsoleto"


def test_refrescar_iniciar_y_progreso(client, db_session, memory_engine, monkeypatch):
    from sqlalchemy.orm import sessionmaker
    from app import obsolescencia_jobs

    eq_id = _seed(db_session)  # 1 componente verificable (P-ACT, activo)
    Factory = sessionmaker(bind=memory_engine, autoflush=False, expire_on_commit=False)

    # consultar inyectado (sin red) + lanzar inline (sin hilo) usando el motor de test
    def _fake_consultar(p, url, *, on_paso=None):
        if on_paso:
            on_paso({"descripcion": "🔎 Buscando: «x»"})
        return {"estado": "obsoleto", "fecha_evento": None,
                "url_fuente": "http://b/eol", "resumen": "x",
                "tokens_total": 777, "estado_consulta": "ok"}

    app.dependency_overrides[get_consultar_fabricante] = lambda: _fake_consultar
    monkeypatch.setattr(
        obsolescencia_jobs, "lanzar",
        lambda job_id, equipo_id, **kw: obsolescencia_jobs.ejecutar(
            job_id, equipo_id, db_factory=Factory, **kw))
    try:
        r = client.post(f"/api/equipos/{eq_id}/obsolescencia/refrescar/iniciar?limite=5")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1 and body["job_id"]

        g = client.get(f"/api/equipos/{eq_id}/obsolescencia/refrescar/{body['job_id']}")
        assert g.status_code == 200
        prog = g.json()
        assert prog["estado"] == "terminado"
        assert prog["indice"] == 1
        assert prog["resultados"][0]["estado_nuevo"] == "obsoleto"
        assert prog["tokens_total"] == 777
        assert prog["resultados"][0]["tokens"] == 777
        assert prog["resultados"][0]["estado_consulta"] == "ok"
        assert prog["report"]["resumen"]["total"] == 1
    finally:
        app.dependency_overrides.pop(get_consultar_fabricante, None)


def test_refrescar_iniciar_equipo_inexistente_404(client):
    app.dependency_overrides[get_consultar_fabricante] = lambda: (
        lambda p, url, *, on_paso=None: {"estado": None, "tokens_total": 0,
                                         "estado_consulta": "sin_respuesta"})
    try:
        r = client.post("/api/equipos/9999/obsolescencia/refrescar/iniciar")
        assert r.status_code == 404
    finally:
        app.dependency_overrides.pop(get_consultar_fabricante, None)


def test_refrescar_progreso_job_desconocido_404(client):
    assert client.get("/api/equipos/1/obsolescencia/refrescar/nope").status_code == 404


def test_refrescar_progreso_requiere_auth(client_sin_auth):
    assert client_sin_auth.get("/api/equipos/1/obsolescencia/refrescar/x").status_code == 401
