from datetime import date

from app import models, obsolescencia_banco


def _seed_banco(db):
    """Banco con 3 componentes: obsoleto, activo, sin verificar."""
    pe = models.Producto(part_number="IUTB-01", tipo="equipo", descripcion="iUTB")
    cli = models.Cliente(nombre="Indra")
    db.add_all([pe, cli]); db.flush()
    eq = models.Equipo(numero_serie="SN-TEST", producto_id=pe.id, cliente_id=cli.id,
                        estado="operativo")
    db.add(eq); db.flush()

    p_obs = models.Producto(part_number="P-OBS", tipo="componente", descripcion="Relé",
                            fabricante="Acme", pn_fabricante="ACM-9",
                            estado_ciclo_vida="obsoleto", ciclo_vida_url="http://acme/eol",
                            ciclo_vida_verificado_en=date(2026, 1, 1))
    p_act = models.Producto(part_number="P-ACT", tipo="componente", descripcion="Cable",
                            fabricante="Beta", pn_fabricante="BET-1",
                            estado_ciclo_vida="activo",
                            ciclo_vida_verificado_en=date(2026, 6, 1))
    p_nv = models.Producto(part_number="P-NV", tipo="componente", descripcion="Tornillo")
    db.add_all([p_obs, p_act, p_nv]); db.flush()
    db.add_all([
        models.Componente(numero_serie="C1", producto_id=p_obs.id, equipo_id=eq.id, posicion="3"),
        models.Componente(numero_serie="C2", producto_id=p_act.id, equipo_id=eq.id, posicion="1"),
        models.Componente(numero_serie="C3", producto_id=p_nv.id, equipo_id=eq.id, posicion="2"),
    ])
    db.commit()
    return eq.id


def test_informe_banco_ordena_por_severidad_y_resume(db_session):
    eq_id = _seed_banco(db_session)
    inf = obsolescencia_banco.informe_banco(db_session, eq_id, date(2026, 6, 12))

    assert inf["banco"]["numero_serie"] == "SN-TEST"
    assert inf["banco"]["cliente"] == "Indra"
    # el obsoleto va primero (mayor severidad)
    assert inf["componentes"][0]["part_number"] == "P-OBS"
    assert inf["componentes"][0]["severidad"] > 0
    assert inf["resumen"]["total"] == 3
    assert inf["resumen"]["en_riesgo"] == 1
    assert inf["resumen"]["sin_verificar"] == 1
    assert inf["resumen"]["conteos"]["obsoleto"] == 1
    assert inf["resumen"]["verificado_mas_antiguo"] == date(2026, 1, 1)
