from datetime import date

from app import models


def test_fabricante_se_crea(db_session):
    f = models.Fabricante(nombre="National Instruments", email_service="svc@ni.com",
                          requiere_activacion_web=True)
    db_session.add(f)
    db_session.commit()
    assert f.id is not None
    assert f.requiere_activacion_web is True


def test_producto_enlaza_fabricante(db_session):
    f = models.Fabricante(nombre="Keysight")
    db_session.add(f)
    db_session.commit()
    p = models.Producto(part_number="PN-1", tipo="componente", descripcion="DMM",
                        fabricante_id=f.id)
    db_session.add(p)
    db_session.commit()
    assert p.fabricante_id == f.id


def test_garantia_fabricante_y_derivacion_se_crean(db_session):
    g = models.GarantiaFabricante(componente_id=1, estado="pendiente_activacion",
                                  fecha_solicitud=date(2026, 6, 1), meses_garantia=24)
    d = models.Derivacion(incidencia_id=1, tipo="externa_fabricante",
                          tu_referencia="RMA-0001", estado="pendiente",
                          fecha_creacion=date(2026, 6, 1))
    db_session.add_all([g, d])
    db_session.commit()
    assert g.id is not None and d.id is not None
    assert g.estado == "pendiente_activacion"
    assert d.estado == "pendiente"
