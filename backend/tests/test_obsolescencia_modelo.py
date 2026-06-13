from datetime import date

from app import models


def test_producto_tiene_campos_ciclo_vida(db_session):
    p = models.Producto(part_number="X1", tipo="componente", descripcion="Demo",
                         fabricante="Keysight", pn_fabricante="ABC")
    p.estado_ciclo_vida = "nrnd"
    p.ciclo_vida_fecha = date(2026, 1, 1)
    p.ciclo_vida_url = "https://k.example/pcn"
    p.ciclo_vida_resumen = "NRND por PCN-123"
    p.ciclo_vida_verificado_en = date(2026, 6, 11)
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    assert p.estado_ciclo_vida == "nrnd"
    assert p.ciclo_vida_fecha == date(2026, 1, 1)
    assert p.ciclo_vida_verificado_en == date(2026, 6, 11)


def test_fabricante_tiene_url_obsolescencia(db_session):
    f = models.Fabricante(nombre="Keysight", url_obsolescencia="https://k.example/eol")
    db_session.add(f)
    db_session.commit()
    db_session.refresh(f)
    assert f.url_obsolescencia == "https://k.example/eol"


def test_noticia_obsolescencia_persiste(db_session):
    p = models.Producto(part_number="X2", tipo="componente", descripcion="Demo2",
                        fabricante="NI", pn_fabricante="DEF")
    db_session.add(p)
    db_session.commit()
    n = models.NoticiaObsolescencia(
        producto_id=p.id, fecha_deteccion=date(2026, 6, 11),
        estado_anterior="activo", estado_nuevo="obsoleto",
        fecha_evento=date(2026, 12, 31), url_fuente="https://ni.example/eol",
        resumen="Discontinuado", notificado=False)
    db_session.add(n)
    db_session.commit()
    db_session.refresh(n)
    assert n.id is not None
    assert n.estado_nuevo == "obsoleto"
    assert n.notificado is False


def test_producto_y_noticia_persisten_cita(db_session):
    p = models.Producto(part_number="X-CITA", tipo="componente", descripcion="Demo",
                         fabricante="Acme", pn_fabricante="ACM-1")
    p.ciclo_vida_cita = "Status: Obsolete (Last Time Buy 2025-12-31)"
    db_session.add(p); db_session.commit(); db_session.refresh(p)
    assert p.ciclo_vida_cita.startswith("Status: Obsolete")
    n = models.NoticiaObsolescencia(
        producto_id=p.id, fecha_deteccion=date(2026, 6, 13),
        estado_anterior="activo", estado_nuevo="obsoleto",
        cita="Discontinued per PCN-001", notificado=False)
    db_session.add(n); db_session.commit(); db_session.refresh(n)
    assert n.cita == "Discontinued per PCN-001"
