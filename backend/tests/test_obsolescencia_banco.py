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


def test_productos_de_equipo_solo_verificables_no_verificados_primero(db_session):
    eq_id = _seed_banco(db_session)
    prods = obsolescencia_banco.productos_de_equipo(db_session, eq_id)
    pns = [p.part_number for p in prods]
    # P-NV no tiene fabricante/pn -> excluido; P-ACT está verificado, P-OBS también
    assert "P-NV" not in pns
    assert set(pns) == {"P-OBS", "P-ACT"}


def test_refrescar_banco_registra_estado_crea_noticia_y_respeta_limite(db_session):
    eq_id = _seed_banco(db_session)

    def fake_consultar(producto, url):
        # empeora P-ACT (activo -> obsoleto); el resto sin cambio concluyente
        if producto.part_number == "P-ACT":
            return {"estado": "obsoleto", "fecha_evento": None,
                    "url_fuente": "http://beta/eol", "resumen": "EOL"}
        return None

    inf = obsolescencia_banco.refrescar_banco(
        db_session, eq_id, date(2026, 6, 12), limite=10, consultar=fake_consultar)

    # P-ACT quedó obsoleto y generó noticia (empeora)
    p_act = db_session.query(models.Producto).filter_by(part_number="P-ACT").one()
    assert p_act.estado_ciclo_vida == "obsoleto"
    noticias = db_session.query(models.NoticiaObsolescencia).filter_by(producto_id=p_act.id).all()
    assert len(noticias) == 1
    assert inf["resumen"]["total"] == 3


def test_refrescar_banco_respeta_limite(db_session):
    eq_id = _seed_banco(db_session)
    llamados = []

    def fake_consultar(producto, url):
        llamados.append(producto.part_number)
        return None

    obsolescencia_banco.refrescar_banco(
        db_session, eq_id, date(2026, 6, 12), limite=1, consultar=fake_consultar)
    assert len(llamados) == 1


def test_refrescar_banco_emite_progreso(db_session):
    eq_id = _seed_banco(db_session)

    def fake(p, url):
        if p.part_number == "P-ACT":
            return {"estado": "obsoleto", "fecha_evento": None,
                    "url_fuente": "http://b/eol", "resumen": "x"}
        return None

    ev = []
    obsolescencia_banco.refrescar_banco(
        db_session, eq_id, date(2026, 6, 12), limite=10,
        consultar=fake, on_progreso=ev.append)

    # P-OBS (verificado 2026-01-01) va antes que P-ACT (2026-06-01)
    pares = [(e["tipo"], e["producto"].part_number) for e in ev]
    assert ("actual", "P-OBS") in pares and ("resultado", "P-OBS") in pares
    assert ("actual", "P-ACT") in pares and ("resultado", "P-ACT") in pares
    # 'actual' precede a su 'resultado' para P-ACT
    ia = next(i for i, e in enumerate(ev)
              if e["tipo"] == "actual" and e["producto"].part_number == "P-ACT")
    ir = next(i for i, e in enumerate(ev)
              if e["tipo"] == "resultado" and e["producto"].part_number == "P-ACT")
    assert ia < ir
    r_act = next(e for e in ev if e["tipo"] == "resultado" and e["producto"].part_number == "P-ACT")
    assert r_act["estado_anterior"] == "activo"
    assert r_act["estado_nuevo"] == "obsoleto"
    assert r_act["cambio"] is True
    r_obs = next(e for e in ev if e["tipo"] == "resultado" and e["producto"].part_number == "P-OBS")
    assert r_obs["cambio"] is False  # fake devolvió None para P-OBS
