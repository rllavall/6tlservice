from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.schemas import AyudaOut, AyudaUpsert

router = APIRouter(prefix="/api/ayuda", tags=["ayuda"])


def _por_clave(db: Session, clave: str) -> Optional[models.AyudaTopico]:
    return db.query(models.AyudaTopico).filter(models.AyudaTopico.clave == clave).first()


@router.get("", response_model=list[AyudaOut])
def listar(pantalla: Optional[str] = None, db: Session = Depends(get_db)) -> list[models.AyudaTopico]:
    q = db.query(models.AyudaTopico)
    if pantalla is not None:
        q = q.filter(models.AyudaTopico.pantalla == pantalla)
    return q.order_by(models.AyudaTopico.clave).all()


@router.get("/{clave}", response_model=AyudaOut)
def obtener(clave: str, db: Session = Depends(get_db)) -> models.AyudaTopico:
    t = _por_clave(db, clave)
    if t is None:
        raise HTTPException(404, "Tópico de ayuda no encontrado")
    return t


@router.put("/{clave}", response_model=AyudaOut)
def upsert(clave: str, payload: AyudaUpsert, db: Session = Depends(get_db)) -> models.AyudaTopico:
    t = _por_clave(db, clave)
    if t is None:
        t = models.AyudaTopico(clave=clave)
        db.add(t)
    t.titulo = payload.titulo
    t.texto = payload.texto
    t.pantalla = payload.pantalla
    db.commit()
    db.refresh(t)
    return t


@router.delete("/{clave}", status_code=204)
def borrar(clave: str, db: Session = Depends(get_db)) -> None:
    t = _por_clave(db, clave)
    if t is None:
        raise HTTPException(404, "Tópico de ayuda no encontrado")
    db.delete(t)
    db.commit()
