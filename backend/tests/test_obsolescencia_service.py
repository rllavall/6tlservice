from datetime import date, timedelta

from app import models, obsolescencia_service as svc


def _prod(db, pn, fab="Keysight", pnf="ABC", **kw):
    p = models.Producto(part_number=pn, tipo="componente", descripcion=pn,
                        fabricante=fab, pn_fabricante=pnf, **kw)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def test_productos_a_revisar_solo_con_fabricante_y_pn(db_session):
    _prod(db_session, "A")                                   # con fab+pn -> sí
    p2 = models.Producto(part_number="B", tipo="componente", descripcion="B")
    db_session.add(p2); db_session.commit()                  # sin fab/pn -> no
    res = svc.productos_a_revisar(db_session, date(2026, 6, 11))
    pns = {p.part_number for p in res}
    assert pns == {"A"}


def test_productos_a_revisar_respeta_dias(db_session):
    p = _prod(db_session, "A")
    p.ciclo_vida_verificado_en = date(2026, 6, 11)           # verificado hoy
    db_session.commit()
    # con dias=7 y hoy=2026-06-15 todavía no toca (verificado hace 4 días)
    assert svc.productos_a_revisar(db_session, date(2026, 6, 15), dias=7) == []
    # hoy=2026-06-20 (9 días después) sí toca
    assert len(svc.productos_a_revisar(db_session, date(2026, 6, 20), dias=7)) == 1


def test_productos_a_revisar_limite(db_session):
    for i in range(5):
        _prod(db_session, f"P{i}", pnf=f"PN{i}")
    res = svc.productos_a_revisar(db_session, date(2026, 6, 11), limite=2)
    assert len(res) == 2


def test_registrar_hallazgo_crea_noticia_si_empeora(db_session):
    p = _prod(db_session, "A")
    r = svc.registrar_hallazgo(db_session, p.id, "obsoleto", hoy=date(2026, 6, 11),
                               fecha_evento=date(2026, 12, 31), url="https://x", resumen="EOL")
    assert r["registrado"] is True and r["cambio"] is True
    db_session.refresh(p)
    assert p.estado_ciclo_vida == "obsoleto"
    assert p.ciclo_vida_verificado_en == date(2026, 6, 11)
    assert db_session.query(models.NoticiaObsolescencia).count() == 1


def test_registrar_hallazgo_activo_no_crea_noticia(db_session):
    p = _prod(db_session, "A")
    r = svc.registrar_hallazgo(db_session, p.id, "activo", hoy=date(2026, 6, 11))
    assert r["cambio"] is False
    db_session.refresh(p)
    assert p.estado_ciclo_vida == "activo"
    assert p.ciclo_vida_verificado_en == date(2026, 6, 11)
    assert db_session.query(models.NoticiaObsolescencia).count() == 0


def test_registrar_hallazgo_sin_url_se_descarta(db_session):
    p = _prod(db_session, "A")
    r = svc.registrar_hallazgo(db_session, p.id, "obsoleto", hoy=date(2026, 6, 11), url=None)
    assert r["registrado"] is False and r["motivo"] == "sin_url"
    db_session.refresh(p)
    assert p.estado_ciclo_vida is None          # no se tocó
    assert db_session.query(models.NoticiaObsolescencia).count() == 0


def test_registrar_hallazgo_mismo_estado_no_duplica(db_session):
    p = _prod(db_session, "A")
    svc.registrar_hallazgo(db_session, p.id, "nrnd", hoy=date(2026, 6, 11), url="https://x")
    r2 = svc.registrar_hallazgo(db_session, p.id, "nrnd", hoy=date(2026, 6, 18), url="https://x")
    assert r2["cambio"] is False
    assert db_session.query(models.NoticiaObsolescencia).count() == 1
    db_session.refresh(p)
    assert p.ciclo_vida_verificado_en == date(2026, 6, 18)   # sí actualiza verificado


def test_resumen_obsolescencia(db_session):
    p1 = _prod(db_session, "A"); p2 = _prod(db_session, "B", pnf="B")
    svc.registrar_hallazgo(db_session, p1.id, "obsoleto", hoy=date(2026, 6, 11), url="https://x")
    svc.registrar_hallazgo(db_session, p2.id, "activo", hoy=date(2026, 6, 11))
    r = svc.resumen_obsolescencia(db_session)
    assert r["conteos"]["obsoleto"] == 1
    assert r["conteos"]["activo"] == 1
    assert len(r["noticias"]) == 1


def test_enviar_informe_envia_solo_no_notificadas_y_marca(db_session):
    p = _prod(db_session, "A")
    svc.registrar_hallazgo(db_session, p.id, "obsoleto", hoy=date(2026, 6, 11), url="https://x")
    capturado = {}

    def fake_notificar(asunto, cuerpo):
        capturado["asunto"] = asunto
        capturado["cuerpo"] = cuerpo
        return {"email": True, "telegram": True}

    r = svc.enviar_informe(db_session, date(2026, 6, 11), notificar_fn=fake_notificar)
    assert r["enviado"] is True and r["total"] == 1
    assert "A" in capturado["cuerpo"] and "obsoleto" in capturado["cuerpo"]
    # marcada como notificada
    assert db_session.query(models.NoticiaObsolescencia).filter_by(notificado=True).count() == 1
    # segunda llamada: nada que enviar
    r2 = svc.enviar_informe(db_session, date(2026, 6, 12), notificar_fn=fake_notificar)
    assert r2["enviado"] is False and r2["total"] == 0


def test_enviar_informe_no_envia_si_vacio(db_session):
    llamado = {"n": 0}

    def fake_notificar(asunto, cuerpo):
        llamado["n"] += 1
        return {}

    r = svc.enviar_informe(db_session, date(2026, 6, 11), notificar_fn=fake_notificar)
    assert r["enviado"] is False
    assert llamado["n"] == 0


def test_registrar_hallazgo_guarda_cita_en_producto_y_noticia(db_session):
    p = _prod(db_session, "A")
    svc.registrar_hallazgo(db_session, p.id, "obsoleto", hoy=date(2026, 6, 13),
                           url="https://x", resumen="EOL", cita="Status: Obsolete")
    db_session.refresh(p)
    assert p.ciclo_vida_cita == "Status: Obsolete"
    n = db_session.query(models.NoticiaObsolescencia).filter_by(producto_id=p.id).one()
    assert n.cita == "Status: Obsolete"


def test_marcar_revisado_sella_fecha_sin_tocar_estado(db_session):
    p = _prod(db_session, "A", estado_ciclo_vida="nrnd",
              ciclo_vida_url="https://prev", ciclo_vida_cita="cita previa")
    ok = svc.marcar_revisado(db_session, p.id, date(2026, 6, 13))
    assert ok is True
    db_session.refresh(p)
    assert p.ciclo_vida_verificado_en == date(2026, 6, 13)
    assert p.estado_ciclo_vida == "nrnd"          # intacto
    assert p.ciclo_vida_url == "https://prev"     # intacto
    assert p.ciclo_vida_cita == "cita previa"     # intacta
    assert svc.marcar_revisado(db_session, 9999, date(2026, 6, 13)) is False
