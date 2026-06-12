from datetime import date

from sqlalchemy.orm import sessionmaker

from app import models, obsolescencia_jobs


def _seed_verificable(db):
    """Equipo con 1 componente verificable (fabricante+pn, estado activo)."""
    pe = models.Producto(part_number="EQ-1", tipo="equipo", descripcion="Banco")
    db.add(pe); db.flush()
    eq = models.Equipo(numero_serie="SNJ", producto_id=pe.id, estado="operativo")
    db.add(eq); db.flush()
    pc = models.Producto(part_number="P-ACT", tipo="componente", descripcion="Cable",
                         fabricante="Beta", pn_fabricante="BET-1", estado_ciclo_vida="activo")
    db.add(pc); db.flush()
    db.add(models.Componente(numero_serie="C1", producto_id=pc.id, equipo_id=eq.id, posicion="1"))
    db.commit()
    return eq.id


def test_ejecutar_job_termina_con_progreso_y_report(memory_engine, db_session):
    eq_id = _seed_verificable(db_session)
    Factory = sessionmaker(bind=memory_engine, autoflush=False, expire_on_commit=False)

    def fake(p, url):
        return {"estado": "obsoleto", "fecha_evento": None,
                "url_fuente": "http://b/eol", "resumen": "x"}

    job_id = obsolescencia_jobs.crear_job(eq_id, 1)
    obsolescencia_jobs.ejecutar(job_id, eq_id, limite=5, consultar=fake, db_factory=Factory)

    snap = obsolescencia_jobs.snapshot(job_id)
    assert snap["estado"] == "terminado"
    assert snap["indice"] == 1
    assert snap["total"] == 1
    assert snap["actual"] is None
    assert len(snap["resultados"]) == 1
    assert snap["resultados"][0]["part_number"] == "P-ACT"
    assert snap["resultados"][0]["estado_nuevo"] == "obsoleto"
    assert snap["resultados"][0]["cambio"] is True
    assert snap["report"]["resumen"]["total"] == 1


def test_snapshot_job_desconocido_es_none():
    assert obsolescencia_jobs.snapshot("noexiste") is None


def test_ejecutar_job_error_si_equipo_inexistente(memory_engine):
    Factory = sessionmaker(bind=memory_engine, autoflush=False, expire_on_commit=False)
    job_id = obsolescencia_jobs.crear_job(9999, 0)
    obsolescencia_jobs.ejecutar(job_id, 9999, limite=5,
                                consultar=lambda p, u: None, db_factory=Factory)
    snap = obsolescencia_jobs.snapshot(job_id)
    assert snap["estado"] == "error"
    assert snap["error"]
