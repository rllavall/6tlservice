# tests/test_fabricantes_schemas.py
from datetime import date

from app import schemas


def test_fabricante_create_defaults():
    f = schemas.FabricanteCreate(nombre="National")
    assert f.requiere_activacion_web is False


def test_garantia_out_incluye_derivados():
    out = schemas.GarantiaFabricanteOut(
        id=1, componente_id=1, fabricante_id=2, estado="activada",
        fecha_solicitud=date(2026, 6, 1), fecha_activacion=date(2026, 6, 5),
        meses_garantia=24, referencia_fabricante="NI-1", responsable="Galarzo",
        fecha_fin=date(2028, 6, 5), estado_cobertura="vigente",
    )
    assert out.estado_cobertura == "vigente"


def test_derivacion_create_y_update():
    c = schemas.DerivacionCreate(tipo="interna_departamento", departamento="Producción")
    assert c.departamento == "Producción"
    u = schemas.DerivacionUpdate(estado="enviada")
    assert u.estado == "enviada"
