from __future__ import annotations

from app import geocoding


def test_geocode_parsea_lat_lon_de_la_respuesta():
    def fake_fetch(url):
        assert "Madrid" in url
        return [{"lat": "40.4168", "lon": "-3.7038", "display_name": "Madrid"}]

    assert geocoding.geocode("Madrid, España", fetch=fake_fetch) == (40.4168, -3.7038)


def test_geocode_sin_resultados_devuelve_none():
    assert geocoding.geocode("Atlantida perdida", fetch=lambda url: []) is None


def test_geocode_query_vacia_devuelve_none():
    llamado = []
    geocoding.geocode("  ", fetch=lambda url: llamado.append(url) or [])
    assert llamado == []  # no se llama al fetch con query vacía
    assert geocoding.geocode("", fetch=lambda url: 1 / 0) is None


def test_geocode_error_de_red_devuelve_none():
    def boom(url):
        raise OSError("sin red")

    assert geocoding.geocode("Madrid", fetch=boom) is None


def test_geocode_ubicacion_combina_partes_no_vacias():
    capturado = {}

    def fake_fetch(url):
        capturado["url"] = url
        return [{"lat": "1.0", "lon": "2.0"}]

    res = geocoding.geocode_ubicacion(
        direccion="C/ Mayor 1", ciudad="Madrid", provincia=None, pais="España", fetch=fake_fetch
    )
    assert res == (1.0, 2.0)
    assert "Mayor" in capturado["url"] and "Madrid" in capturado["url"]


def test_geocode_ubicacion_sin_datos_devuelve_none():
    assert geocoding.geocode_ubicacion(fetch=lambda url: 1 / 0) is None
