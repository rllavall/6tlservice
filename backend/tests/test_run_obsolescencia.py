from datetime import date

from app import models
import run_obsolescencia as runo


def _prod(db, pn, fab="Keysight", pnf="ABC"):
    p = models.Producto(part_number=pn, tipo="componente", descripcion=pn,
                        fabricante=fab, pn_fabricante=pnf)
    db.add(p); db.commit(); db.refresh(p)
    return p


def test_ejecutar_recorre_registra_y_notifica(db_session):
    p1 = _prod(db_session, "A")
    p2 = _prod(db_session, "B", pnf="DEF")

    veredictos = {
        "A": {"estado": "obsoleto", "url_fuente": "https://x", "resumen": "EOL",
              "fecha_evento": date(2026, 12, 31)},
        "B": {"estado": "activo", "url_fuente": None, "resumen": None, "fecha_evento": None},
    }

    def fake_consultar(producto, url_obsolescencia):
        return veredictos[producto.part_number]

    enviados = {}

    def fake_notificar(asunto, cuerpo):
        enviados["cuerpo"] = cuerpo
        return {"email": True, "telegram": None}

    r = runo.ejecutar(db_session, date(2026, 6, 11), limite=10,
                      consultar=fake_consultar, notificar_fn=fake_notificar)

    db_session.refresh(p1); db_session.refresh(p2)
    assert p1.estado_ciclo_vida == "obsoleto"
    assert p2.estado_ciclo_vida == "activo"
    assert r["enviado"] is True and r["total"] == 1          # solo A genera noticia
    assert "A" in enviados["cuerpo"]


def test_ejecutar_salta_veredicto_none(db_session):
    p = _prod(db_session, "A")

    def fake_consultar(producto, url_obsolescencia):
        return None

    r = runo.ejecutar(db_session, date(2026, 6, 11),
                      consultar=fake_consultar, notificar_fn=lambda a, c: {})
    db_session.refresh(p)
    assert p.estado_ciclo_vida is None
    assert r["enviado"] is False
