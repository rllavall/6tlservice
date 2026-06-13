"""Tests del parser stream-json y del runner con timeout de consultar_fabricante."""
import json
from datetime import date

import run_obsolescencia as ro


class _Producto:
    fabricante = "Beta"
    pn_fabricante = "BET-1"
    descripcion = "Cable"
    fabricante_id = None


def _linea_assistant(name, inp):
    return json.dumps({"type": "assistant",
                       "message": {"content": [{"type": "tool_use", "name": name, "input": inp}]}})


def _linea_result(texto, usage):
    return json.dumps({"type": "result", "subtype": "success", "result": texto, "usage": usage})


def test_descripcion_paso_websearch_y_webfetch():
    assert ro._descripcion_paso("WebSearch", {"query": "MAX3232 EOL"}) == "🔎 Buscando: «MAX3232 EOL»"
    assert ro._descripcion_paso("WebFetch", {"url": "https://www.digikey.com/x"}) == "🌐 Leyendo www.digikey.com"
    assert ro._descripcion_paso("ToolSearch", {"query": "select:WebSearch"}) is None


def test_tokens_de_usage_solo_input_output_excluye_cache():
    u = {"input_tokens": 10, "output_tokens": 5,
         "cache_creation_input_tokens": 2, "cache_read_input_tokens": 100}
    # se excluye la caché (cache_creation/cache_read): solo input + output
    assert ro._tokens_de_usage(u) == 15
    assert ro._tokens_de_usage({}) == 0


def test_procesar_stream_emite_pasos_y_saca_tokens_y_texto():
    lineas = [
        '{"type":"system","subtype":"init"}',
        '{"type":"system","subtype":"hook_started"}',
        _linea_assistant("ToolSearch", {"query": "select:WebSearch"}),
        _linea_assistant("WebSearch", {"query": "MAX3232 lifecycle"}),
        _linea_assistant("WebFetch", {"url": "https://www.ti.com/product/MAX3232"}),
        _linea_result('Respuesta: {"estado":"obsoleto","fecha_evento":"2025-01-01","url_fuente":"http://ti","resumen":"EOL"}',
                      {"input_tokens": 4000, "output_tokens": 100,
                       "cache_creation_input_tokens": 0, "cache_read_input_tokens": 20000}),
    ]
    pasos = []
    texto, tokens, hubo = ro._procesar_stream(iter(lineas), on_paso=lambda ev: pasos.append(ev["descripcion"]))
    assert hubo is True
    assert tokens == 4100  # input+output (4000+100); excluye cache_read (20000)
    assert "obsoleto" in texto
    assert pasos == ["🔎 Buscando: «MAX3232 lifecycle»", "🌐 Leyendo www.ti.com"]


def test_parsear_estado_extrae_dict_o_none():
    d = ro._parsear_estado('bla {"estado":"eol_anunciado","fecha_evento":"2025-06-01"} fin')
    assert d["estado"] == "eol_anunciado"
    assert d["fecha_evento"] == date(2025, 6, 1)
    assert ro._parsear_estado("sin json aqui") is None
    assert ro._parsear_estado('{"resumen":"x"}') is None


class _FakeProc:
    def __init__(self, lineas):
        self.stdout = iter(lineas)
        self.killed = False
    def kill(self):
        self.killed = True
    def wait(self, timeout=None):
        return 0


class _TimerInmediato:
    def __init__(self, _seg, fn):
        self._fn = fn
    def start(self):
        self._fn()
    def cancel(self):
        pass


class _TimerNulo:
    def __init__(self, _seg, fn):
        pass
    def start(self):
        pass
    def cancel(self):
        pass


def test_consultar_fabricante_ok_devuelve_estado_y_tokens():
    lineas = [
        _linea_assistant("WebSearch", {"query": "BET-1 EOL"}),
        _linea_result('{"estado":"nrnd","fecha_evento":null,"url_fuente":"http://b","resumen":"r"}',
                      {"input_tokens": 1000, "output_tokens": 50}),
    ]
    pasos = []
    v = ro.consultar_fabricante(_Producto(), "http://beta", on_paso=lambda ev: pasos.append(ev["descripcion"]),
                                _popen=lambda: _FakeProc(lineas), _timer_factory=_TimerNulo)
    assert v["estado"] == "nrnd"
    assert v["estado_consulta"] == "ok"
    assert v["tokens_total"] == 1050
    assert pasos == ["🔎 Buscando: «BET-1 EOL»"]


def test_consultar_fabricante_sin_estado_es_sin_respuesta():
    lineas = [_linea_result("no encontré nada concluyente", {"input_tokens": 500, "output_tokens": 10})]
    v = ro.consultar_fabricante(_Producto(), None, _popen=lambda: _FakeProc(lineas), _timer_factory=_TimerNulo)
    assert v["estado"] is None
    assert v["estado_consulta"] == "sin_respuesta"
    assert v["tokens_total"] == 510


def test_consultar_fabricante_timeout_marca_timeout_y_mata_proceso():
    proc = _FakeProc([])
    v = ro.consultar_fabricante(_Producto(), None, _popen=lambda: proc, _timer_factory=_TimerInmediato)
    assert v["estado_consulta"] == "timeout"
    assert v["estado"] is None
    assert proc.killed is True


def test_normalizar_url_quita_esquema_www_barra_y_query():
    assert ro._normalizar_url("https://www.TI.com/product/MAX3232/") == "ti.com/product/max3232"
    assert ro._normalizar_url("http://ti.com/product/MAX3232?x=1") == "ti.com/product/max3232"
    assert ro._normalizar_url(None) == ""


def test_url_verificada_compara_contra_visitadas():
    visitadas = ["https://www.ti.com/product/MAX3232", "https://digikey.com/x"]
    assert ro._url_verificada("http://ti.com/product/max3232/", visitadas) is True
    assert ro._url_verificada("https://mouser.com/otra", visitadas) is False
    assert ro._url_verificada(None, visitadas) is False
    assert ro._url_verificada("https://ti.com/x", []) is False
