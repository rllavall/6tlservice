from __future__ import annotations

import argparse
import getpass
import sys
from datetime import date

from sqlalchemy.orm import Session

from app import models, seguridad
from app.db import SessionLocal


class UsuarioYaExiste(Exception):
    pass


def crear_usuario(db: Session, username: str, password: str, *, nombre: str | None = None,
                  rol: str = "admin") -> models.Usuario:
    if db.query(models.Usuario).filter(models.Usuario.username == username).first() is not None:
        raise UsuarioYaExiste(f"El usuario '{username}' ya existe")
    u = models.Usuario(
        username=username, nombre=nombre or username,
        password_hash=seguridad.hash_password(password),
        activo=True, rol=rol, fecha_alta=date.today(),
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Crea un usuario en la BD de 6TL Postventa.")
    parser.add_argument("username")
    parser.add_argument("--nombre", default=None)
    parser.add_argument("--rol", default="admin")
    args = parser.parse_args(argv)

    password = getpass.getpass("Contraseña: ")
    if not password:
        print("Contraseña vacía; abortado.", file=sys.stderr)
        return 2
    db = SessionLocal()
    try:
        u = crear_usuario(db, args.username, password, nombre=args.nombre, rol=args.rol)
    except UsuarioYaExiste as e:
        print(str(e), file=sys.stderr)
        return 1
    finally:
        db.close()
    print(f"Usuario '{u.username}' creado (id={u.id}, rol={u.rol}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
