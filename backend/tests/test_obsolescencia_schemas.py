from datetime import date

import pytest
from pydantic import ValidationError

from app import schemas


def test_hallazgo_valida_estado():
    h = schemas.HallazgoObsolescencia(producto_id=1, estado="obsoleto",
                                      url="https://x", resumen="EOL")
    assert h.estado == "obsoleto"
    with pytest.raises(ValidationError):
        schemas.HallazgoObsolescencia(producto_id=1, estado="zzz")


def test_producto_out_expone_ciclo_vida():
    campos = schemas.ProductoOut.model_fields
    for c in ["estado_ciclo_vida", "ciclo_vida_fecha", "ciclo_vida_url",
              "ciclo_vida_resumen", "ciclo_vida_verificado_en"]:
        assert c in campos


def test_fabricante_schemas_tienen_url_obsolescencia():
    assert "url_obsolescencia" in schemas.FabricanteCreate.model_fields
    assert "url_obsolescencia" in schemas.FabricanteUpdate.model_fields
    assert "url_obsolescencia" in schemas.FabricanteOut.model_fields


def test_producto_a_revisar_out():
    o = schemas.ProductoARevisarOut(id=1, fabricante="NI", pn_fabricante="DEF",
                                    descripcion="x", estado_ciclo_vida=None,
                                    url_obsolescencia="https://ni/eol")
    assert o.pn_fabricante == "DEF"


def test_resumen_out():
    r = schemas.ObsolescenciaResumenOut(conteos={"activo": 2}, sin_verificar=5, noticias=[])
    assert r.sin_verificar == 5
