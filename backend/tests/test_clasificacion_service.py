import pytest

from app import models, auditoria
from app.clasificacion_service import clasificar_producto, clasificar_lote


@pytest.fixture
def _audit():
    auditoria.registrar_listeners()  # idempotente
    yield


def _prod(db, **kw):
    base = dict(part_number=kw.pop("pn", "P1"), tipo=kw.pop("tipo", "componente"),
                descripcion=kw.pop("descripcion", ""),
                categoria_componente=kw.pop("cat", None),
                fabricante=kw.pop("fab", None))
    p = models.Producto(**base, **kw)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def test_reglas_escriben_flags_y_origen(db_session, _audit):
    db_session.info["usuario_username"] = "tester"
    p = _prod(db_session, pn="DMM1", descripcion="DMM", cat="instrumento")
    res = clasificar_producto(db_session, p, usar_llm=False)
    assert p.afecta_a_medida is True
    assert p.clasificacion_origen == "agente"
    assert p.clasificacion_motivo
    assert res.estado == "clasificado"


def test_respeta_origen_manual(db_session, _audit):
    p = _prod(db_session, pn="X", descripcion="DMM", cat="instrumento")
    p.clasificacion_origen = "manual"
    p.afecta_a_medida = False
    db_session.commit()
    res = clasificar_producto(db_session, p, usar_llm=False)
    assert res.estado == "omitido_manual"
    assert p.afecta_a_medida is False  # no lo pisa


def test_ambiguo_usa_llm_cuando_disponible(db_session, _audit):
    p = _prod(db_session, pn="A", descripcion="Modulo auxiliar", cat="accesorios")
    fake = lambda *a, **k: {"afecta_a_medida": True, "bajo_coste": False, "razon": "LLM dice medida"}
    clasificar_producto(db_session, p, usar_llm=True, consultar=fake)
    assert p.afecta_a_medida is True
    assert "LLM" in p.clasificacion_motivo


def test_ambiguo_llm_invalido_cae_a_reglas(db_session, _audit):
    p = _prod(db_session, pn="A2", descripcion="Modulo auxiliar", cat="accesorios")
    fake = lambda *a, **k: None  # LLM no decide
    clasificar_producto(db_session, p, usar_llm=True, consultar=fake)
    assert p.afecta_a_medida is False and p.bajo_coste is False
    assert p.clasificacion_origen == "agente"


def test_lote_recorre_componentes_y_cuenta(db_session, _audit):
    _prod(db_session, pn="I1", descripcion="DMM", cat="instrumento")
    _prod(db_session, pn="W1", descripcion="Patch generico", cat="wiring")
    man = _prod(db_session, pn="M1", descripcion="DMM", cat="instrumento")
    man.clasificacion_origen = "manual"
    db_session.commit()
    fake = lambda *a, **k: {"afecta_a_medida": False, "bajo_coste": True, "razon": "x"}
    resumen = clasificar_lote(db_session, usar_llm=True, consultar=fake)
    assert resumen.procesados == 2  # I1 y W1, no el manual
    assert resumen.omitidos_manual == 1


def test_lote_dry_run_no_escribe(db_session, _audit):
    p = _prod(db_session, pn="I9", descripcion="DMM", cat="instrumento")
    clasificar_lote(db_session, usar_llm=False, dry_run=True)
    db_session.refresh(p)
    assert p.clasificacion_origen is None
