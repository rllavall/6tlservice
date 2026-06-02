import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app


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
    """TestClient whose get_db dependency uses the in-memory engine."""
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
