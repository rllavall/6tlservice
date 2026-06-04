from datetime import date


def test_modelo_avance_defaults(db_session):
    from app import models
    inc = models.Incidencia(
        codigo="RMA-7001", titulo="t", descripcion_problema="d",
        estado="abierta", fecha_apertura=date(2026, 6, 1),
    )
    db_session.add(inc); db_session.flush()
    av = models.AvanceIncidencia(incidencia_id=inc.id, fecha=date(2026, 6, 2), texto="Primer avance")
    db_session.add(av); db_session.flush()
    assert av.tipo == "avance"        # default
    assert av.autor is None
    assert av.texto == "Primer avance"
