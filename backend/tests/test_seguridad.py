from app import seguridad


def test_hash_distinto_por_salt():
    h1 = seguridad.hash_password("secreto")
    h2 = seguridad.hash_password("secreto")
    assert h1 != h2                      # salt aleatorio
    assert h1.startswith("pbkdf2_sha256$")


def test_verify_ok_y_ko():
    h = seguridad.hash_password("secreto")
    assert seguridad.verify_password("secreto", h) is True
    assert seguridad.verify_password("otra", h) is False


def test_verify_hash_malformado_devuelve_false():
    assert seguridad.verify_password("x", "no-es-un-hash") is False
    assert seguridad.verify_password("x", "") is False
    assert seguridad.verify_password("x", "pbkdf2_sha256$abc$def") is False  # faltan campos
