from __future__ import annotations

import hashlib
import hmac
import secrets

_ALG = "pbkdf2_sha256"
ITERACIONES = 200_000


def hash_password(password: str, *, iteraciones: int = ITERACIONES) -> str:
    """Devuelve un hash autocontenido `pbkdf2_sha256$<iter>$<salt_hex>$<hash_hex>`."""
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iteraciones)
    return f"{_ALG}${iteraciones}${salt.hex()}${dk.hex()}"


def verify_password(password: str, almacenado: str) -> bool:
    """Compara `password` contra el hash almacenado. False ante formato inválido (no lanza)."""
    try:
        alg, iter_str, salt_hex, hash_hex = almacenado.split("$")
        if alg != _ALG:
            return False
        iteraciones = int(iter_str)
        salt = bytes.fromhex(salt_hex)
        esperado = bytes.fromhex(hash_hex)
    except (ValueError, AttributeError):
        return False
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iteraciones)
    return hmac.compare_digest(dk, esperado)
