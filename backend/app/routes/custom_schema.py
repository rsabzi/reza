"""Management API for custom tables and report views (admin/dashboard path)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from ..custom_schema import (
    CustomSchemaError,
    create_custom_table,
    drop_custom_object,
    list_custom_schema,
    prepare_report_view,
    query_custom_object,
)
from ..database import get_db

router = APIRouter(prefix="/custom-schema", tags=["custom schema"])

ColumnType = Literal["text", "integer", "real", "boolean", "date", "datetime"]
ViewSource = Literal[
    "tasks",
    "salons",
    "salon_interactions",
    "personal_projects",
    "memory_entries",
    "outbound_messages",
    "contact_endpoints",
    "steps",
    "agent_action_runs",
    "tools",
]
AggregateFunction = Literal["count", "sum", "avg", "min", "max"]


class ColumnSpec(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    type: ColumnType
    primary_key: bool = False
    nullable: bool | None = None

    @field_validator("name")
    @classmethod
    def name_valid(cls, value: str) -> str:
        import re

        if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", value.strip().lower()):
            raise ValueError("column name must match [a-z][a-z0-9_]{0,63}")
        return value.strip().lower()


class CustomTableCreate(BaseModel):
    table_name: str = Field(min_length=1, max_length=64)
    columns: list[ColumnSpec] = Field(min_length=1, max_length=30)
    purpose: str | None = Field(default=None, max_length=1000)
    replace: bool = False


class FilterSpec(BaseModel):
    column: str = Field(min_length=1, max_length=64)
    value: Any

    @field_validator("column")
    @classmethod
    def column_valid(cls, value: str) -> str:
        import re

        if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", value.strip().lower()):
            raise ValueError("filter column must match [a-z][a-z0-9_]{0,63}")
        return value.strip().lower()


class AggregateSpec(BaseModel):
    function: AggregateFunction
    column: str = Field(min_length=1, max_length=64)
    group_by: list[str] = Field(default_factory=list, max_length=3)


class CustomViewCreate(BaseModel):
    view_name: str = Field(min_length=1, max_length=64)
    source: ViewSource
    columns: list[str] = Field(min_length=1, max_length=30)
    filters: list[FilterSpec] = Field(default_factory=list, max_length=10)
    aggregate: AggregateSpec | None = None
    order_by: str | None = Field(default=None, max_length=64)
    limit: int | None = Field(default=None, ge=1, le=1000)
    purpose: str | None = Field(default=None, max_length=1000)
    replace: bool = False


class SchemaItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    columns: Any
    purpose: str | None
    created_at: datetime
    updated_at: datetime


class SchemaListResponse(BaseModel):
    tables: list[dict[str, Any]]
    views: list[dict[str, Any]]


@router.get("", response_model=SchemaListResponse)
def get_custom_schema(db: Session = Depends(get_db)) -> dict[str, Any]:
    return list_custom_schema(db)


@router.post("/tables", status_code=status.HTTP_201_CREATED)
def create_table_endpoint(
    payload: CustomTableCreate, db: Session = Depends(get_db)
) -> dict[str, Any]:
    try:
        result = create_custom_table(
            db,
            table_name=payload.table_name,
            columns=[item.model_dump(exclude_none=True) for item in payload.columns],
            purpose=payload.purpose,
            replace=payload.replace,
        )
    except CustomSchemaError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return result


@router.post("/views", status_code=status.HTTP_201_CREATED)
def create_view_endpoint(
    payload: CustomViewCreate, db: Session = Depends(get_db)
) -> dict[str, Any]:
    try:
        result = prepare_report_view(
            db,
            view_name=payload.view_name,
            source=payload.source,
            columns=payload.columns,
            filters=[item.model_dump() for item in payload.filters],
            aggregate=payload.aggregate.model_dump() if payload.aggregate else None,
            order_by=payload.order_by,
            limit=payload.limit,
            purpose=payload.purpose,
            replace=payload.replace,
        )
    except CustomSchemaError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return result


@router.get("/{kind}/{name}/rows")
def read_schema_rows(
    kind: Literal["custom_table", "custom_view"],
    name: str,
    limit: int = Query(default=50, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        rows = query_custom_object(db, kind=kind, name=name, limit=limit)
    except CustomSchemaError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"kind": kind, "name": name, "count": len(rows), "rows": rows}


@router.delete("/{kind}/{name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schema_object(
    kind: Literal["custom_table", "custom_view"],
    name: str,
    db: Session = Depends(get_db),
) -> Response:
    try:
        drop_custom_object(db, kind=kind, name=name)
    except CustomSchemaError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
