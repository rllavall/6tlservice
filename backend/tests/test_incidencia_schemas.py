import pytest
from pydantic import ValidationError

from app.schemas import IncidenciaCreate, TransicionPayload


def test_incidencia_create_requires_al_menos_un_sujeto():
    with pytest.raises(ValidationError):
        IncidenciaCreate(titulo="x", descripcion_problema="y", fecha_apertura="2026-06-01")


def test_incidencia_create_ok_con_equipo():
    m = IncidenciaCreate(
        equipo_id=1, titulo="x", descripcion_problema="y", fecha_apertura="2026-06-01"
    )
    assert m.equipo_id == 1
    assert m.prioridad == "media"


def test_incidencia_create_ok_con_componente():
    m = IncidenciaCreate(
        componente_id=3, titulo="x", descripcion_problema="y", fecha_apertura="2026-06-01"
    )
    assert m.componente_id == 3


def test_transicion_payload_valida_estado():
    ok = TransicionPayload(nuevo_estado="diagnostico")
    assert ok.fecha is None
    with pytest.raises(ValidationError):
        TransicionPayload(nuevo_estado="inventado")
