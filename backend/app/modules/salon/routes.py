"""Salon module API routes."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...database import get_db
from ...memory.embedder import EmbeddingError
from .models import Salon, SalonInteraction
from .schemas import (
    BulkSalonImport,
    DailySalonPlanItem,
    InteractionCreate,
    InteractionRead,
    SalonCreate,
    SalonRead,
    SalonUpdate,
)
from .service import daily_salon_plan, log_interaction

router = APIRouter(prefix="/salons", tags=["salon module"])


def _duplicate_phone_detail() -> str:
    return "A salon with this phone already exists"


@router.post("/import")
def bulk_import_salons(payload: BulkSalonImport, db: Session = Depends(get_db)) -> JSONResponse:
    created: list[Salon] = []
    errors: list[dict] = []
    seen_phones: set[str] = set()
    for index, raw_row in enumerate(payload.salons):
        try:
            row = SalonCreate.model_validate(raw_row)
        except ValidationError as exc:
            safe_errors = [
                {"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]}
                for error in exc.errors(include_url=False)
            ]
            errors.append({"index": index, "row": raw_row, "errors": safe_errors})
            continue
        duplicate = row.phone in seen_phones or db.scalar(
            select(Salon.id).where(Salon.phone == row.phone)
        )
        if duplicate:
            errors.append(
                {
                    "index": index,
                    "row": raw_row,
                    "errors": [{"msg": _duplicate_phone_detail()}],
                }
            )
            continue
        salon = Salon(**row.model_dump())
        db.add(salon)
        db.flush()
        created.append(salon)
        seen_phones.add(row.phone)
    db.commit()
    body = {
        "created_count": len(created),
        "error_count": len(errors),
        "created": [SalonRead.model_validate(item).model_dump(mode="json") for item in created],
        "errors": errors,
    }
    return JSONResponse(status_code=207 if errors else 201, content=body)


@router.get("/daily-plan", response_model=list[DailySalonPlanItem])
def get_daily_plan(
    as_of: datetime | None = None,
    cadence_days: int | None = Query(default=None, ge=1, le=365),
    db: Session = Depends(get_db),
) -> list[dict]:
    return daily_salon_plan(db, as_of=as_of, cadence_days=cadence_days)


@router.post("", response_model=SalonRead, status_code=status.HTTP_201_CREATED)
def create_salon(payload: SalonCreate, db: Session = Depends(get_db)) -> Salon:
    salon = Salon(**payload.model_dump())
    db.add(salon)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=_duplicate_phone_detail()) from exc
    db.refresh(salon)
    return salon


@router.get("", response_model=list[SalonRead])
def list_salons(
    salon_status: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
) -> list[Salon]:
    statement = select(Salon).order_by(Salon.created_at.desc(), Salon.id.desc())
    if salon_status:
        statement = statement.where(Salon.status == salon_status)
    return list(db.scalars(statement))


@router.get("/{salon_id}", response_model=SalonRead)
def get_salon(salon_id: int, db: Session = Depends(get_db)) -> Salon:
    salon = db.get(Salon, salon_id)
    if salon is None:
        raise HTTPException(status_code=404, detail="Salon not found")
    return salon


@router.patch("/{salon_id}", response_model=SalonRead)
def update_salon(salon_id: int, payload: SalonUpdate, db: Session = Depends(get_db)) -> Salon:
    salon = db.get(Salon, salon_id)
    if salon is None:
        raise HTTPException(status_code=404, detail="Salon not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(salon, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=_duplicate_phone_detail()) from exc
    db.refresh(salon)
    return salon


@router.delete("/{salon_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_salon(salon_id: int, db: Session = Depends(get_db)) -> Response:
    salon = db.get(Salon, salon_id)
    if salon is None:
        raise HTTPException(status_code=404, detail="Salon not found")
    db.delete(salon)
    db.commit()
    return Response(status_code=204)


@router.post(
    "/{salon_id}/interactions",
    response_model=InteractionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_interaction(
    salon_id: int, payload: InteractionCreate, db: Session = Depends(get_db)
) -> SalonInteraction:
    salon = db.get(Salon, salon_id)
    if salon is None:
        raise HTTPException(status_code=404, detail="Salon not found")
    try:
        return log_interaction(db, salon=salon, **payload.model_dump())
    except (EmbeddingError, ValueError) as exc:
        db.rollback()
        raise HTTPException(
            status_code=502, detail=f"Could not persist interaction memory: {exc}"
        ) from exc


@router.get("/{salon_id}/interactions", response_model=list[InteractionRead])
def list_interactions(salon_id: int, db: Session = Depends(get_db)) -> list[SalonInteraction]:
    if db.get(Salon, salon_id) is None:
        raise HTTPException(status_code=404, detail="Salon not found")
    return list(
        db.scalars(
            select(SalonInteraction)
            .where(SalonInteraction.salon_id == salon_id)
            .order_by(SalonInteraction.occurred_at.desc())
        )
    )
