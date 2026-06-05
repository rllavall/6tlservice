"""
Verifica que el expediente de una incidencia expone en vivo la cobertura
de contrato del equipo asociado: bajo_contrato=True y contrato.codigo correcto.

No requiere cambios en producción: la cobertura fluye automáticamente a través
de EquipoOut (bajo_contrato + contrato: ContratoResumen) embebido en IncidenciaFicha.
"""


def test_expediente_incidencia_muestra_bajo_contrato(client):
    prod = client.post("/api/productos", json={
        "part_number": "6TL-EQI", "tipo": "equipo", "descripcion": "Banco"}).json()
    con = client.post("/api/contratos", json={
        "nivel": "silver", "fecha_inicio": "2020-01-01", "fecha_fin": "2100-01-01"}).json()
    eq = client.post("/api/equipos", json={
        "numero_serie": "I1", "producto_id": prod["id"]}).json()
    client.post(f"/api/contratos/{con['id']}/equipos", json={"equipo_id": eq["id"]})
    inc = client.post("/api/incidencias", json={
        "tipo": "soporte_tecnico", "equipo_id": eq["id"],
        "titulo": "fallo", "descripcion_problema": "x", "prioridad": "media",
        "fecha_apertura": "2026-06-05"}).json()

    ficha = client.get(f"/api/incidencias/{inc['id']}").json()
    assert ficha["equipo"]["bajo_contrato"] is True
    assert ficha["equipo"]["contrato"]["codigo"] == con["codigo"]
