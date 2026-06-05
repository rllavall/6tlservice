from datetime import date

from app import models


def test_accion_preventiva_se_guarda(db_session):
    p = models.Producto(part_number="6TL-EQP", tipo="equipo", descripcion="Banco")
    db_session.add(p); db_session.flush()
    eq = models.Equipo(numero_serie="SN1", producto_id=p.id)
    db_session.add(eq); db_session.flush()
    a = models.AccionPreventiva(
        equipo_id=eq.id, fecha=date(2026, 6, 5), tecnico="Cim",
        tipo="on_site", veredicto="ok",
    )
    db_session.add(a); db_session.flush()
    assert a.id is not None
    assert a.contrato_id is None and a.incidencia_id is None and a.informe is None
