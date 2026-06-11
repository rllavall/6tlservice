from datetime import date

from app import models, seguridad


def test_endpoint_interno_sin_token_da_401(client_sin_auth):
    # client_sin_auth NO sobreescribe get_current_user -> exige token de verdad
    assert client_sin_auth.get("/api/equipos").status_code == 401


def test_endpoint_interno_con_token_ok(client_sin_auth, db_session):
    db_session.add(models.Usuario(
        username="ramon", nombre="R", password_hash=seguridad.hash_password("s"),
        activo=True, rol="admin", fecha_alta=date(2026, 6, 5),
    ))
    db_session.commit()
    tok = client_sin_auth.post("/api/auth/login", json={"username": "ramon", "password": "s"}).json()["token"]
    r = client_sin_auth.get("/api/equipos", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200


def test_health_y_login_son_publicos(client_sin_auth):
    assert client_sin_auth.get("/api/health").status_code == 200
    # login con credenciales inexistentes responde 401 (no 'no autenticado' por falta de token)
    assert client_sin_auth.post("/api/auth/login", json={"username": "x", "password": "y"}).status_code == 401


def test_client_con_override_no_exige_token(client):
    # el fixture `client` (override activo) deja pasar sin token -> compat de los tests previos
    assert client.get("/api/equipos").status_code == 200


def test_fabricantes_sin_token_da_401(client_sin_auth):
    assert client_sin_auth.get("/api/fabricantes").status_code == 401
    assert client_sin_auth.post("/api/fabricantes", json={"nombre": "Test"}).status_code == 401
    assert client_sin_auth.get("/api/fabricantes/1").status_code == 401
    assert client_sin_auth.put("/api/fabricantes/1", json={"nombre": "Test"}).status_code == 401
    assert client_sin_auth.delete("/api/fabricantes/1").status_code == 401


def test_garantia_fabricante_sin_token_da_401(client_sin_auth):
    assert client_sin_auth.get("/api/garantias/pendientes").status_code == 401
    assert client_sin_auth.get("/api/componentes/1/garantia").status_code == 401
    assert client_sin_auth.post("/api/componentes/1/garantia/activar", json={}).status_code == 401
    assert client_sin_auth.post(
        "/api/componentes/1/garantia/confirmar", json={"fecha_activacion": "2026-06-05"}
    ).status_code == 401


def test_patch_componente_sin_token_da_401(client_sin_auth):
    assert client_sin_auth.patch("/api/componentes/1", json={"numero_serie": "X"}).status_code == 401


def test_derivaciones_sin_token_da_401(client_sin_auth):
    assert client_sin_auth.get("/api/incidencias/1/derivaciones").status_code == 401
    assert client_sin_auth.post(
        "/api/incidencias/1/derivaciones", json={"tipo": "interna_departamento"}
    ).status_code == 401
    assert client_sin_auth.patch("/api/derivaciones/1", json={"estado": "enviada"}).status_code == 401
