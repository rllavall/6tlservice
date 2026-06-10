from datetime import date

import pytest

from app import garantia_fabricante_service as svc
from app import models


def _componente_con_fabricante(db):
    fab = models.Fabricante(nombre="National", email_service="svc@ni.com")
    db.add(fab)
    db.flush()
    prod = models.Producto(part_number="PN-DMM", tipo="componente", descripcion="DMM",
                          fabricante_id=fab.id, meses_garantia_default=24)
    db.add(prod)
    db.flush()
    comp = models.Componente(numero_serie="SN-1", producto_id=prod.id)
    db.add(comp)
    db.flush()
    return comp, fab


def test_activar_crea_registro_pendiente(db_session):
    comp, fab = _componente_con_fabricante(db_session)
    g = svc.activar(db_session, comp, meses_garantia=24, responsable="Galarzo",
                    hoy=date(2026, 6, 1))
    assert g.estado == "pendiente_activacion"
    assert g.fecha_solicitud == date(2026, 6, 1)
    assert g.fabricante_id == fab.id
    assert g.responsable == "Galarzo"


def test_activar_dos_veces_reusa_el_registro(db_session):
    comp, _ = _componente_con_fabricante(db_session)
    g1 = svc.activar(db_session, comp, meses_garantia=24, hoy=date(2026, 6, 1))
    g2 = svc.activar(db_session, comp, meses_garantia=12, hoy=date(2026, 6, 2))
    assert g1.id == g2.id  # 1:1 con el componente
    assert g2.meses_garantia == 12


def test_confirmar_activa_y_fija_inicio(db_session):
    comp, _ = _componente_con_fabricante(db_session)
    g = svc.activar(db_session, comp, meses_garantia=24, hoy=date(2026, 6, 1))
    svc.confirmar(db_session, g, fecha_activacion=date(2026, 6, 5), referencia="NI-998")
    assert g.estado == "activada"
    assert g.fecha_activacion == date(2026, 6, 5)
    assert g.referencia_fabricante == "NI-998"


def test_confirmar_sobre_no_pendiente_lanza(db_session):
    comp, _ = _componente_con_fabricante(db_session)
    g = svc.activar(db_session, comp, meses_garantia=24, hoy=date(2026, 6, 1))
    svc.confirmar(db_session, g, fecha_activacion=date(2026, 6, 5))
    with pytest.raises(svc.GarantiaError):
        svc.confirmar(db_session, g, fecha_activacion=date(2026, 6, 9))
