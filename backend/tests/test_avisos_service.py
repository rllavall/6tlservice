from datetime import date

from app import avisos_service
from app import models


def _producto(db):
    p = models.Producto(part_number="6TL-AV", tipo="equipo", descripcion="Banco")
    db.add(p); db.flush()
    return p


def _contrato(db, codigo, nivel="bronze", inicio=date(2020, 1, 1), fin=date(2100, 1, 1)):
    c = models.ContratoMantenimiento(codigo=codigo, nivel=nivel, fecha_inicio=inicio, fecha_fin=fin)
    db.add(c); db.flush()
    return c


def test_equipo_nunca_revisado_vencido_aparece(db_session):
    p = _producto(db_session)
    con = _contrato(db_session, "CTR-0001", nivel="bronze", inicio=date(2020, 1, 1))
    eq = models.Equipo(numero_serie="V1", producto_id=p.id, contrato_id=con.id)
    db_session.add(eq); db_session.flush()
    out = avisos_service.construir_avisos(db_session, date(2026, 6, 5))
    ids = [a["equipo"].id for a in out["preventivos"]]
    assert eq.id in ids
    aviso = next(a for a in out["preventivos"] if a["equipo"].id == eq.id)
    assert aviso["bucket"] == "vencido"
    assert aviso["dias_restantes"] < 0
    assert aviso["ultima_fecha"] is None


def test_equipo_sin_contrato_vigente_excluido(db_session):
    p = _producto(db_session)
    venc = _contrato(db_session, "CTR-VENC", inicio=date(2020, 1, 1), fin=date(2021, 1, 1))
    eq = models.Equipo(numero_serie="X1", producto_id=p.id, contrato_id=venc.id)
    db_session.add(eq); db_session.flush()
    out = avisos_service.construir_avisos(db_session, date(2026, 6, 5))
    assert all(a["equipo"].id != eq.id for a in out["preventivos"])


def test_equipo_al_dia_no_aparece(db_session):
    p = _producto(db_session)
    con = _contrato(db_session, "CTR-AL", nivel="gold")
    eq = models.Equipo(numero_serie="A1", producto_id=p.id, contrato_id=con.id)
    db_session.add(eq); db_session.flush()
    db_session.add(models.AccionPreventiva(
        equipo_id=eq.id, fecha=date(2026, 6, 1), tipo="on_site", veredicto="ok",
        proxima_fecha=date(2026, 12, 1)))
    db_session.flush()
    out = avisos_service.construir_avisos(db_session, date(2026, 6, 5))
    assert all(a["equipo"].id != eq.id for a in out["preventivos"])


def test_orden_y_resumen_y_contrato_por_caducar(db_session):
    p = _producto(db_session)
    con = _contrato(db_session, "CTR-CAD", nivel="bronze", inicio=date(2020, 1, 1), fin=date(2026, 7, 1))
    eq = models.Equipo(numero_serie="C1", producto_id=p.id, contrato_id=con.id)
    db_session.add(eq); db_session.flush()
    out = avisos_service.construir_avisos(db_session, date(2026, 6, 5))
    assert any(c["contrato"].id == con.id for c in out["contratos_por_caducar"])
    r = out["resumen"]
    assert r["preventivos_vencidos"] >= 1
    assert r["contratos_por_caducar"] >= 1
    dr = [a["dias_restantes"] for a in out["preventivos"]]
    assert dr == sorted(dr)
