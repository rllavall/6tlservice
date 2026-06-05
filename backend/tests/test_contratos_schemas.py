from datetime import date

from app import models
from app.schemas import ContratoOut, EquipoOut


def test_contrato_out_incluye_estado_y_detalle(db_session):
    c = models.ContratoMantenimiento(
        codigo="CTR-0001", nivel="gold",
        fecha_inicio=date(2020, 1, 1), fecha_fin=date(2100, 1, 1),
    )
    db_session.add(c); db_session.flush()
    out = ContratoOut.model_validate(c)
    assert out.estado == "vigente"
    assert out.vigente is True
    assert out.nivel_detalle["soporte"] == "24/7"


def test_equipo_out_expone_bajo_contrato_y_resumen(db_session):
    p = models.Producto(part_number="6TL-EQ", tipo="equipo", descripcion="Banco")
    con = models.ContratoMantenimiento(
        codigo="CTR-0002", nivel="bronze",
        fecha_inicio=date(2020, 1, 1), fecha_fin=date(2100, 1, 1),
    )
    db_session.add_all([p, con]); db_session.flush()
    eq = models.Equipo(numero_serie="SN1", producto_id=p.id, contrato_id=con.id)
    db_session.add(eq); db_session.flush()
    out = EquipoOut.model_validate(eq)
    assert out.bajo_contrato is True
    assert out.contrato.codigo == "CTR-0002"
    assert out.contrato.estado == "vigente"
