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
