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


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
