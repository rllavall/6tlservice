from datetime import date

from app import models, seguridad


def _crear_usuario(client_db, username="ramon", password="secreto", activo=True):
    db = client_db
    u = models.Usuario(
        username=username, nombre="Ramón",
        password_hash=seguridad.hash_password(password),
        activo=activo, rol="admin", fecha_alta=date(2026, 6, 5),
    )
    db.add(u)
    db.commit()


def test_login_ok_devuelve_token_y_usuario(client, db_session):
    _crear_usuario(db_session)
    r = client.post("/api/auth/login", json={"username": "ramon", "password": "secreto"})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["token"]
    assert b["usuario"]["username"] == "ramon" and b["usuario"]["rol"] == "admin"
    assert "password_hash" not in b["usuario"]


def test_login_password_mala_401(client, db_session):
    _crear_usuario(db_session)
    r = client.post("/api/auth/login", json={"username": "ramon", "password": "mala"})
    assert r.status_code == 401


def test_login_inactivo_401(client, db_session):
    _crear_usuario(db_session, activo=False)
    r = client.post("/api/auth/login", json={"username": "ramon", "password": "secreto"})
    assert r.status_code == 401


def test_me_con_token_ok_sin_token_401(client_sin_auth, db_session):
    _crear_usuario(db_session)
    tok = client_sin_auth.post("/api/auth/login", json={"username": "ramon", "password": "secreto"}).json()["token"]
    r = client_sin_auth.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200 and r.json()["username"] == "ramon"
    assert client_sin_auth.get("/api/auth/me").status_code == 401


def test_logout_invalida_token(client_sin_auth, db_session):
    _crear_usuario(db_session)
    tok = client_sin_auth.post("/api/auth/login", json={"username": "ramon", "password": "secreto"}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    assert client_sin_auth.post("/api/auth/logout", headers=h).status_code == 204
    assert client_sin_auth.get("/api/auth/me", headers=h).status_code == 401
