"""Derivación pura criticidad + nivel de trazabilidad. Sin BD (duck-typing)."""
from types import SimpleNamespace

import pytest

from app import criticidad


def _p(**kw):
    base = dict(categoria_componente=None, afecta_a_medida=False,
               bajo_coste=False, nivel_trazabilidad_override=None)
    base.update(kw)
    return SimpleNamespace(**base)


# --- criticidad ---

def test_afecta_a_medida_es_alta_y_serie_aunque_sea_bajo_coste():
    p = _p(afecta_a_medida=True, bajo_coste=True, categoria_componente="wiring")
    assert criticidad.criticidad(p) == "alta"
    assert criticidad.nivel_trazabilidad(p) == "serie"


@pytest.mark.parametrize("cat", ["instrumento", "mass_interconnect"])
def test_instrumento_y_mass_interconnect_son_alta_serie(cat):
    p = _p(categoria_componente=cat)
    assert criticidad.criticidad(p) == "alta"
    assert criticidad.nivel_trazabilidad(p) == "serie"


@pytest.mark.parametrize("cat", ["software", "fixture_adaptador"])
def test_software_y_fixture_son_alta_version(cat):
    p = _p(categoria_componente=cat)
    assert criticidad.criticidad(p) == "alta"
    assert criticidad.nivel_trazabilidad(p) == "version"


@pytest.mark.parametrize("cat", ["wiring", "accesorios"])
def test_bajo_coste_es_baja_no_trazado(cat):
    p = _p(categoria_componente=cat, bajo_coste=True)
    assert criticidad.criticidad(p) == "baja"
    assert criticidad.nivel_trazabilidad(p) == "no_trazado"


def test_resto_es_media_serie():
    p = _p(categoria_componente=None)
    assert criticidad.criticidad(p) == "media"
    assert criticidad.nivel_trazabilidad(p) == "serie"


# --- override ---

def test_override_gana_sobre_la_cascada_en_el_nivel():
    p = _p(categoria_componente="instrumento", nivel_trazabilidad_override="no_trazado")
    assert criticidad.nivel_trazabilidad(p) == "no_trazado"


def test_override_no_cambia_la_criticidad():
    p = _p(categoria_componente="instrumento", nivel_trazabilidad_override="no_trazado")
    assert criticidad.criticidad(p) == "alta"


def test_override_vacio_se_ignora():
    p = _p(categoria_componente="wiring", bajo_coste=True, nivel_trazabilidad_override="")
    assert criticidad.nivel_trazabilidad(p) == "no_trazado"


# --- constantes coherentes ---

def test_constantes():
    assert criticidad.NIVELES == ("serie", "version", "no_trazado")
    assert set(criticidad.CRITICIDADES) == {"alta", "media", "baja"}
