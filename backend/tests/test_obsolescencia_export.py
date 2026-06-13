import io
import zipfile

from datetime import date

from app import obsolescencia_export


def _informe():
    return {
        "banco": {"equipo_id": 1, "numero_serie": "SN-XLS", "producto": "IUTB-01",
                  "descripcion": "iUTB", "cliente": "Indra", "estado": "operativo",
                  "contrato_nivel": None},
        "componentes": [
            {"componente_id": 1, "posicion": "3", "part_number": "P-OBS",
             "fabricante": "Acme", "pn_fabricante": "ACM-9", "descripcion": "Relé",
             "numero_serie": "C1", "categoria_componente": "instrumento",
             "estado_ciclo_vida": "obsoleto", "severidad": 4,
             "ciclo_vida_fecha": date(2026, 1, 1), "ciclo_vida_url": "http://acme/eol",
             "ciclo_vida_resumen": "EOL", "ciclo_vida_verificado_en": date(2026, 1, 1)},
            {"componente_id": 2, "posicion": "1", "part_number": "P-ACT",
             "fabricante": "Beta", "pn_fabricante": "BET-1", "descripcion": "Cable",
             "numero_serie": "C2", "categoria_componente": "wiring",
             "estado_ciclo_vida": "activo", "severidad": 0,
             "ciclo_vida_fecha": None, "ciclo_vida_url": None,
             "ciclo_vida_resumen": None, "ciclo_vida_verificado_en": date(2026, 6, 1)},
        ],
        "resumen": {"conteos": {"activo": 1, "nrnd": 0, "eol_anunciado": 0,
                                "ultima_compra": 0, "obsoleto": 1},
                    "en_riesgo": 1, "sin_verificar": 0, "total": 2,
                    "verificado_mas_antiguo": date(2026, 1, 1)},
    }


def test_a_xlsx_es_zip_y_contiene_la_serie():
    data = obsolescencia_export.a_xlsx(_informe())
    assert data[:4] == b"PK\x03\x04"            # cabecera ZIP (xlsx)
    z = zipfile.ZipFile(io.BytesIO(data))
    # openpyxl 3.1.5 escribe strings como inlineStr en el sheet XML (no sharedStrings)
    sheet = z.read("xl/worksheets/sheet1.xml").decode("utf-8")
    assert "SN-XLS" in sheet
    assert "P-OBS" in sheet


def test_a_pdf_tiene_cabecera_pdf():
    data = obsolescencia_export.a_pdf(_informe())
    assert data[:5] == b"%PDF-"
    assert len(data) > 1000


def test_a_xlsx_incluye_cita():
    inf = _informe()
    inf["componentes"][0]["ciclo_vida_cita"] = "Obsolete per PCN-001"
    inf["componentes"][1]["ciclo_vida_cita"] = None
    data = obsolescencia_export.a_xlsx(inf)
    sheet = zipfile.ZipFile(io.BytesIO(data)).read("xl/worksheets/sheet1.xml").decode("utf-8")
    assert "Cita" in sheet                       # encabezado
    assert "Obsolete per PCN-001" in sheet       # valor
