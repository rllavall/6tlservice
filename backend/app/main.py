from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import Base, engine

# Import models so Base.metadata is populated before create_all.
from app import models  # noqa: F401  (registered in Task 1)

Base.metadata.create_all(engine)

app = FastAPI(title="6TL Postventa", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.routers import ubicaciones
app.include_router(ubicaciones.router)

from app.routers import productos
app.include_router(productos.router)

from app.routers import equipos
app.include_router(equipos.router)

from app.routers import componentes
app.include_router(componentes.router)

from app.routers import movimientos
app.include_router(movimientos.router)

from app.routers import configuracion
app.include_router(configuracion.router)

from app.routers import busqueda
app.include_router(busqueda.router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
