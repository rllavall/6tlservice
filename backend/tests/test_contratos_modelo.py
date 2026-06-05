from datetime import date

from app import models


def _producto(db):
    p = models.Producto(part_number="6TL-EQ", tipo="equipo", descripcion="Banco")
    db.add(p); db.flush()
    return p


def test_contrato_estado_y_nivel_detalle(db_session):
    c = models.ContratoMantenimiento(
        codigo="CTR-0001", cliente_id=None, nivel="gold",
        fecha_inicio=date(2020, 1, 1), fecha_fin=date(2100, 1, 1),
    )
    db_session.add(c); db_session.flush()
    assert c.estado == "vigente"
    assert c.vigente is True
    assert c.nivel_detalle["soporte"] == "24/7"


def test_equipo_bajo_contrato_derivado(db_session):
    p = _producto(db_session)
    vig = models.ContratoMantenimiento(
        codigo="CTR-0002", nivel="bronze",
        fecha_inicio=date(2020, 1, 1), fecha_fin=date(2100, 1, 1),
    )
    venc = models.ContratoMantenimiento(
        codigo="CTR-0003", nivel="bronze",
        fecha_inicio=date(2020, 1, 1), fecha_fin=date(2021, 1, 1),
    )
    db_session.add_all([vig, venc]); db_session.flush()

    e_sin = models.Equipo(numero_serie="SN1", producto_id=p.id)
    e_vig = models.Equipo(numero_serie="SN2", producto_id=p.id, contrato_id=vig.id)
    e_venc = models.Equipo(numero_serie="SN3", producto_id=p.id, contrato_id=venc.id)
    db_session.add_all([e_sin, e_vig, e_venc]); db_session.flush()

    assert e_sin.bajo_contrato is False
    assert e_vig.bajo_contrato is True
    assert e_venc.bajo_contrato is False   # contrato vencido no cuenta
