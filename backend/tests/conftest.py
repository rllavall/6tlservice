import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.deps import get_current_user
from app.main import app
from app import models


@pytest.fixture
def memory_engine():
    eng = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db_session(memory_engine):
    SessionTest = sessionmaker(bind=memory_engine, autoflush=False, expire_on_commit=False)
    with SessionTest() as s:
        yield s


@pytest.fixture
def client(memory_engine):
    """TestClient cuyo get_db usa el motor en memoria y con auth simulada (usuario de prueba)."""
    SessionTest = sessionmaker(bind=memory_engine, autoflush=False, expire_on_commit=False)

    def _override_get_db():
        db = SessionTest()
        try:
            yield db
        finally:
            db.close()

    def _override_current_user(db=Depends(get_db)):
        usuario = db.get(models.Usuario, 1)
        db.info["usuario_id"] = usuario.id if usuario else None
        db.info["usuario_username"] = usuario.username if usuario else "test"
        return usuario

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_current_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def client_sin_auth(memory_engine):
    """TestClient con auth REAL (sin override de get_current_user) para tests de protección."""
    SessionTest = sessionmaker(bind=memory_engine, autoflush=False, expire_on_commit=False)

    def _override_get_db():
        db = SessionTest()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
