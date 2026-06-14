import pytest

from app import escaneo_service, models


def _equipo_con_banco(db, *, fabricante=None, pn_fab="PN-A", regla=None, serie="S/N pendiente (1.1)"):
    fab = None
    if fabricante:
        fab = models.Fabricante(nombre=fabricante, regla_datamatrix=regla)
        db.add(fab); db.flush()
    p_eq = models.Producto(part_number="BANCO-1", tipo="equipo", descripcion="Banco")
    db.add(p_eq); db.flush()
    eq = models.Equipo(numero_serie="EQ-1", producto_id=p_eq.id)
    db.add(eq); db.flush()
    p_comp = models.Producto(part_number="COMP-1", tipo="componente", descripcion="Comp",
                             pn_fabricante=pn_fab, fabricante_id=fab.id if fab else None)
    db.add(p_comp); db.flush()
    comp = models.Componente(numero_serie=serie, producto_id=p_comp.id,
                             equipo_id=eq.id, posicion="1.1")
    db.add(comp); db.commit()
    return eq, comp, p_comp


def test_asignado_rellena_placeholder(db_session):
    eq, comp, _ = _equipo_con_banco(db_session, pn_fab="PN-A")
    r = escaneo_service.resolver_escaneo(db_session, eq.id, "240PN-A\x1d21SER-99")
    assert r["estado"] == "asignado"
    assert r["componente_id"] == comp.id
    db_session.refresh(comp)
    assert comp.numero_serie == "SER-99"


def test_ambiguo_no_escribe(db_session):
    eq, comp1, p1 = _equipo_con_banco(db_session, pn_fab="PN-A")
    comp2 = models.Componente(numero_serie="S/N pendiente (1.2)", producto_id=p1.id,
                              equipo_id=eq.id, posicion="1.2")
    db_session.add(comp2); db_session.commit()
    r = escaneo_service.resolver_escaneo(db_session, eq.id, "240PN-A\x1d21SER-99")
    assert r["estado"] == "ambiguo"
    assert len(r["candidatos"]) == 2
    db_session.refresh(comp1)
    assert comp1.numero_serie.startswith("S/N pendiente")


def test_ocupado_no_pisa_serial_real(db_session):
    eq, comp, _ = _equipo_con_banco(db_session, pn_fab="PN-A", serie="SERIAL-REAL")
    r = escaneo_service.resolver_escaneo(db_session, eq.id, "240PN-A\x1d21SER-99")
    assert r["estado"] == "ocupado"
    db_session.refresh(comp)
    assert comp.numero_serie == "SERIAL-REAL"


def test_sin_match_devuelve_placeholders(db_session):
    eq, comp, _ = _equipo_con_banco(db_session, pn_fab="PN-A")
    r = escaneo_service.resolver_escaneo(db_session, eq.id, "240PN-OTRO\x1d21SER-99")
    assert r["estado"] == "sin_match"
    assert any(c["componente_id"] == comp.id for c in r["candidatos"])


def test_sin_sn(db_session):
    eq, comp, _ = _equipo_con_banco(db_session, pn_fab="PN-A")
    r = escaneo_service.resolver_escaneo(db_session, eq.id, "240PN-A")
    assert r["estado"] == "sin_sn"


def test_duplicado(db_session):
    eq, comp, p = _equipo_con_banco(db_session, pn_fab="PN-A")
    otro = models.Componente(numero_serie="SER-99", producto_id=p.id, equipo_id=eq.id, posicion="1.2")
    db_session.add(otro); db_session.commit()
    r = escaneo_service.resolver_escaneo(db_session, eq.id, "240PN-A\x1d21SER-99")
    assert r["estado"] == "duplicado"
    db_session.refresh(comp)
    assert comp.numero_serie.startswith("S/N pendiente")


def test_usa_regla_del_fabricante(db_session):
    eq, comp, _ = _equipo_con_banco(
        db_session, fabricante="ACME", pn_fab="PNX",
        regla=r"^(?P<pn>[A-Z]+)\*(?P<sn>\d+)$")
    r = escaneo_service.resolver_escaneo(db_session, eq.id, "PNX*7777")
    assert r["estado"] == "asignado"
    db_session.refresh(comp)
    assert comp.numero_serie == "7777"


def test_equipo_inexistente(db_session):
    r = escaneo_service.resolver_escaneo(db_session, 9999, "240PN-A\x1d21SER-99")
    assert r["estado"] == "equipo_no_existe"
