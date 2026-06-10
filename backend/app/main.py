from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Carga backend/.env en os.environ antes de leer cualquier configuración
# (SMTP, Telegram, auth). El entorno real siempre gana sobre el fichero.
from app.env_file import load_env_file
load_env_file()

from app.deps import get_current_user

from app.db import Base, engine

# Import models so Base.metadata is populated before create_all.
from app import models  # noqa: F401  (registered in Task 1)

Base.metadata.create_all(engine)

# Rellena columnas nuevas en tablas preexistentes (create_all no las añade).
from app.migrations import add_missing_columns

add_missing_columns(engine)

from app.auditoria import registrar_listeners
registrar_listeners()

from app.db import SessionLocal
from app.ayuda_seed import sembrar_ayuda

with SessionLocal() as _db:
    sembrar_ayuda(_db)

app = FastAPI(title="6TL Postventa", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.routers import clientes
app.include_router(clientes.router, dependencies=[Depends(get_current_user)])

from app.routers import ubicaciones
app.include_router(ubicaciones.router, dependencies=[Depends(get_current_user)])

from app.routers import productos
app.include_router(productos.router, dependencies=[Depends(get_current_user)])

from app.routers import equipos
app.include_router(equipos.router, dependencies=[Depends(get_current_user)])

from app.routers import componentes
app.include_router(componentes.router, dependencies=[Depends(get_current_user)])

from app.routers import movimientos
app.include_router(movimientos.router, dependencies=[Depends(get_current_user)])

from app.routers import configuracion
app.include_router(configuracion.router, dependencies=[Depends(get_current_user)])

from app.routers import busqueda
app.include_router(busqueda.router, dependencies=[Depends(get_current_user)])

from app.routers import incidencias
app.include_router(incidencias.router, dependencies=[Depends(get_current_user)])

from app.routers import mapa
app.include_router(mapa.router, dependencies=[Depends(get_current_user)])

from app.routers import analitica
app.include_router(analitica.router, dependencies=[Depends(get_current_user)])

from app.routers import avances
app.include_router(avances.router, dependencies=[Depends(get_current_user)])

from app.routers import auditoria
app.include_router(auditoria.router, dependencies=[Depends(get_current_user)])

from app.routers import ayuda
app.include_router(ayuda.router, dependencies=[Depends(get_current_user)])

from app.routers import contratos
app.include_router(contratos.router, dependencies=[Depends(get_current_user)])

from app.routers import preventivo
app.include_router(preventivo.router, dependencies=[Depends(get_current_user)])

from app.routers import avisos
app.include_router(avisos.router, dependencies=[Depends(get_current_user)])

from app.routers import sla
app.include_router(sla.router, dependencies=[Depends(get_current_user)])

from app.routers import notificaciones
app.include_router(notificaciones.router, dependencies=[Depends(get_current_user)])

from app.routers import fabricantes
app.include_router(fabricantes.router, dependencies=[Depends(get_current_user)])

from app.routers import garantia_fabricante
app.include_router(garantia_fabricante.router, dependencies=[Depends(get_current_user)])

from app.routers import derivaciones
app.include_router(derivaciones.router, dependencies=[Depends(get_current_user)])

from app.routers import auth
app.include_router(auth.router)

from app.routers import solicitudes
app.include_router(solicitudes.router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
