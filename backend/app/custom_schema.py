"""Limited, code-generated custom tables and report views.

No raw SQL is accepted from the agent or API. Table/view names, column names,
types, source tables, filters, aggregates and ordering all come from strict
allowlists and are assembled with SQLAlchemy, so user input only ever flows into
bound/literal values — never into DDL structure.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    MetaData,
    Table,
    Text,
    func,
    inspect,
    select,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.types import TypeEngine

from .database import Base, SessionLocal
from .models import CustomTableDefinition, CustomViewDefinition

TABLE_NAME_RE = re.compile(r"^custom_[a-z][a-z0-9_]{2,48}$")
VIEW_NAME_RE = re.compile(r"^report_[a-z][a-z0-9_]{2,48}$")
COLUMN_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")

RESERVED_WORDS = {
    "select",
    "from",
    "where",
    "table",
    "view",
    "order",
    "group",
    "limit",
    "join",
    "drop",
    "alter",
    "insert",
    "update",
    "delete",
    "create",
    "index",
}

ALLOWED_COLUMN_TYPES = {"text", "integer", "real", "boolean", "date", "datetime"}
MAX_COLUMNS = 30
MAX_FILTERS = 10
MAX_LIMIT = 1000
MAX_VALUE_LENGTH = 500

# Source tables a report view may read, with the exact columns exposed.
ALLOWED_SOURCE_COLUMNS: dict[str, set[str]] = {
    "tasks": {
        "id",
        "title",
        "description",
        "status",
        "module_name",
        "parent_task_id",
        "recurrence_rule",
        "scheduled_time",
        "last_scheduled_at",
        "created_at",
        "updated_at",
    },
    "salons": {
        "id",
        "name",
        "phone",
        "city",
        "address",
        "status",
        "notes",
        "tags",
        "last_contact_at",
        "created_at",
        "updated_at",
    },
    "salon_interactions": {
        "id",
        "salon_id",
        "channel",
        "direction",
        "content",
        "outcome",
        "occurred_at",
        "next_follow_up_at",
        "created_at",
    },
    "personal_projects": {
        "id",
        "title",
        "client_name",
        "description",
        "status",
        "due_date",
        "budget",
        "next_action",
        "external_url",
        "created_at",
        "updated_at",
    },
    "memory_entries": {
        "id",
        "content",
        "source",
        "source_id",
        "module_name",
        "created_at",
    },
    "outbound_messages": {
        "id",
        "owner_type",
        "owner_id",
        "channel",
        "content",
        "status",
        "provider_message_id",
        "sent_at",
        "created_at",
        "updated_at",
    },
    "contact_endpoints": {
        "id",
        "owner_type",
        "owner_id",
        "channel",
        "address",
        "label",
        "enabled",
        "created_at",
        "updated_at",
    },
    "steps": {
        "id",
        "task_id",
        "title",
        "position",
        "status",
        "tool_name",
        "requires_approval",
        "approved_at",
        "created_at",
        "updated_at",
    },
    "agent_action_runs": {
        "id",
        "conversation_id",
        "message_id",
        "provider_call_id",
        "action_name",
        "status",
        "started_at",
        "finished_at",
        "created_at",
    },
    "tools": {"id", "name", "description", "requires_approval", "enabled"},
}

AGGREGATE_FUNCTIONS = {"count", "sum", "avg", "min", "max"}


class CustomSchemaError(ValueError):
    """Validation failure with a safe, user-facing message."""


def _validate_name(name: str, pattern: re.Pattern[str], label: str) -> str:
    normalized = (name or "").strip().lower()
    if not pattern.fullmatch(normalized):
        raise CustomSchemaError(
            f"{label} must match '{pattern.pattern}' and start with "
            f"{'custom_' if label == 'Table' else 'report_'}"
        )
    if normalized in RESERVED_WORDS:
        raise CustomSchemaError(f"{label} name '{normalized}' is reserved")
    return normalized


def _validate_column_name(name: str) -> str:
    normalized = (name or "").strip().lower()
    if not COLUMN_NAME_RE.fullmatch(normalized) or normalized in RESERVED_WORDS:
        raise CustomSchemaError(f"Invalid column name '{name}'")
    return normalized


def _column_type(type_name: str) -> TypeEngine[Any]:
    mapping: dict[str, TypeEngine[Any]] = {
        "text": Text(),
        "integer": Integer(),
        "real": Float(),
        "boolean": Boolean(),
        "date": Date(),
        "datetime": DateTime(timezone=True),
    }
    try:
        return mapping[type_name.lower()]
    except KeyError as exc:
        raise CustomSchemaError(
            f"Unsupported column type '{type_name}'; allowed: {', '.join(sorted(ALLOWED_COLUMN_TYPES))}"
        ) from exc


def _validate_columns(columns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not columns:
        raise CustomSchemaError("At least one column is required")
    if len(columns) > MAX_COLUMNS:
        raise CustomSchemaError(f"At most {MAX_COLUMNS} columns are allowed")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    primary_keys = 0
    for raw in columns:
        if not isinstance(raw, dict):
            raise CustomSchemaError("Each column must be an object")
        name = _validate_column_name(str(raw.get("name") or ""))
        if name in seen:
            raise CustomSchemaError(f"Duplicate column '{name}'")
        seen.add(name)
        type_name = str(raw.get("type") or "").lower()
        if type_name not in ALLOWED_COLUMN_TYPES:
            raise CustomSchemaError(
                f"Unsupported column type '{type_name}'; allowed: {', '.join(sorted(ALLOWED_COLUMN_TYPES))}"
            )
        primary_key = bool(raw.get("primary_key", False))
        if primary_key:
            primary_keys += 1
            if primary_keys > 1:
                raise CustomSchemaError("At most one primary key column is allowed")
        nullable = bool(raw.get("nullable", True))
        if primary_key:
            nullable = False
        normalized.append(
            {
                "name": name,
                "type": type_name,
                "primary_key": primary_key,
                "nullable": nullable,
            }
        )
    return normalized


def _source_table(source: str) -> tuple[str, Table]:
    key = (source or "").strip().lower()
    if key not in ALLOWED_SOURCE_COLUMNS:
        raise CustomSchemaError(
            f"Unsupported source '{source}'; allowed: {', '.join(sorted(ALLOWED_SOURCE_COLUMNS))}"
        )
    table = Base.metadata.tables.get(key)
    if table is None:
        raise CustomSchemaError(f"Source table '{key}' is not available in this database")
    return key, table


def _coerce_filter_value(column: Column[Any], value: Any) -> Any:
    if isinstance(value, (dict, list)):
        raise CustomSchemaError("Filter values must be scalar")
    if isinstance(value, str) and len(value) > MAX_VALUE_LENGTH:
        raise CustomSchemaError("Filter value is too long")
    col_type = column.type
    if isinstance(col_type, DateTime):
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError as exc:
            raise CustomSchemaError("Invalid datetime filter value; use ISO 8601") from exc
    if isinstance(col_type, Date):
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        try:
            return date.fromisoformat(str(value))
        except ValueError as exc:
            raise CustomSchemaError("Invalid date filter value; use YYYY-MM-DD") from exc
    if isinstance(col_type, Boolean):
        if not isinstance(value, bool):
            raise CustomSchemaError("Boolean filter value required")
        return value
    if isinstance(col_type, Integer) and not isinstance(value, bool):
        if not isinstance(value, int):
            raise CustomSchemaError("Integer filter value required")
        return value
    if isinstance(col_type, Float):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise CustomSchemaError("Numeric filter value required")
        return value
    if not isinstance(value, (str, bool)) and value is not None:
        raise CustomSchemaError("Text filter value must be a string")
    return value


def _build_view_statement(view: dict[str, Any]) -> tuple[str, Any]:
    source_key, table = _source_table(view.get("source") or "")
    allowed = ALLOWED_SOURCE_COLUMNS[source_key]
    requested_columns = view.get("columns") or []
    if not requested_columns or not isinstance(requested_columns, list):
        raise CustomSchemaError("At least one column is required")
    if len(requested_columns) > MAX_COLUMNS:
        raise CustomSchemaError(f"At most {MAX_COLUMNS} columns are allowed")

    columns: list[Any] = []
    for raw in requested_columns:
        name = _validate_column_name(str(raw))
        if name not in allowed:
            raise CustomSchemaError(f"Column '{name}' is not exposed for source '{source_key}'")
        columns.append(table.c[name])

    filters = view.get("filters") or []
    if not isinstance(filters, list) or len(filters) > MAX_FILTERS:
        raise CustomSchemaError(f"At most {MAX_FILTERS} filters are allowed")
    where_clauses: list[Any] = []
    for raw_filter in filters:
        if not isinstance(raw_filter, dict):
            raise CustomSchemaError("Each filter must be an object")
        column_name = _validate_column_name(str(raw_filter.get("column") or ""))
        if column_name not in allowed:
            raise CustomSchemaError(
                f"Filter column '{column_name}' is not exposed for source '{source_key}'"
            )
        where_clauses.append(
            table.c[column_name]
            == _coerce_filter_value(table.c[column_name], raw_filter.get("value"))
        )

    aggregate = view.get("aggregate")
    order_by_raw = view.get("order_by")
    limit_raw = view.get("limit")

    statement: Any
    if aggregate:
        if not isinstance(aggregate, dict):
            raise CustomSchemaError("aggregate must be an object")
        function = str(aggregate.get("function") or "").lower()
        if function not in AGGREGATE_FUNCTIONS:
            raise CustomSchemaError(
                f"Unsupported aggregate '{function}'; allowed: {', '.join(sorted(AGGREGATE_FUNCTIONS))}"
            )
        column_name = str(aggregate.get("column") or "").strip()
        group_by_raw = aggregate.get("group_by") or []
        if not isinstance(group_by_raw, list) or len(group_by_raw) > 3:
            raise CustomSchemaError("At most 3 group_by columns are allowed")
        if function == "count" and column_name == "*":
            agg_expr = func.count()
        else:
            agg_column = _validate_column_name(column_name)
            if agg_column not in allowed:
                raise CustomSchemaError(
                    f"Aggregate column '{agg_column}' is not exposed for source '{source_key}'"
                )
            agg_expr = getattr(func, function)(table.c[agg_column])
        group_by_columns: list[Any] = []
        select_exprs: list[Any] = []
        for group_raw in group_by_raw:
            group_name = _validate_column_name(str(group_raw))
            if group_name not in allowed:
                raise CustomSchemaError(
                    f"Group column '{group_name}' is not exposed for source '{source_key}'"
                )
            group_by_columns.append(table.c[group_name])
            select_exprs.append(table.c[group_name].label(group_name))
        select_exprs.append(agg_expr.label(f"{function}_{column_name.replace('*', 'all')}"))
        statement = select(*select_exprs).select_from(table)
        if group_by_columns:
            statement = statement.group_by(*group_by_columns)
        if order_by_raw:
            raise CustomSchemaError("order_by is not supported with aggregate queries")
    else:
        statement = select(*columns)
        if order_by_raw:
            order_name = _validate_column_name(str(order_by_raw))
            if order_name not in allowed:
                raise CustomSchemaError(
                    f"Order column '{order_name}' is not exposed for source '{source_key}'"
                )
            statement = statement.order_by(table.c[order_name])
    if where_clauses:
        statement = statement.where(*where_clauses)
    if limit_raw is not None:
        limit = int(limit_raw)
        if not 1 <= limit <= MAX_LIMIT:
            raise CustomSchemaError(f"limit must be between 1 and {MAX_LIMIT}")
        statement = statement.limit(limit)
    return source_key, statement


def prevalidate_request(action_name: str, arguments: dict[str, Any]) -> None:
    """Fail fast before any approval step / DDL when arguments violate the allowlist."""

    if action_name == "create_custom_table":
        _validate_name(str(arguments.get("table_name") or ""), TABLE_NAME_RE, "Table")
        _validate_columns(arguments.get("columns") or [])
        return
    if action_name == "prepare_report_view":
        view_spec = {
            "source": arguments.get("source"),
            "columns": arguments.get("columns"),
            "filters": arguments.get("filters") or [],
            "aggregate": arguments.get("aggregate"),
            "order_by": arguments.get("order_by"),
            "limit": arguments.get("limit"),
        }
        _validate_name(str(arguments.get("view_name") or ""), VIEW_NAME_RE, "View")
        _build_view_statement(view_spec)
        return


def create_custom_table(
    db: Session,
    *,
    table_name: str,
    columns: list[dict[str, Any]],
    purpose: str | None = None,
    replace: bool = False,
) -> dict[str, Any]:
    """Create an allowlisted custom table and persist its definition."""

    normalized_name = _validate_name(table_name, TABLE_NAME_RE, "Table")
    normalized_columns = _validate_columns(columns)
    engine = db.get_bind()
    exists = inspect(engine).has_table(normalized_name)
    if exists and not replace:
        raise CustomSchemaError(
            f"Table '{normalized_name}' already exists; set replace=true to recreate it"
        )
    if exists and replace:
        with engine.begin() as connection:
            connection.exec_driver_sql(f'DROP TABLE IF EXISTS "{normalized_name}"')
        db.query(CustomTableDefinition).filter_by(table_name=normalized_name).delete()
        db.flush()

    definitions = [
        Column(
            item["name"],
            _column_type(item["type"]),
            primary_key=item["primary_key"],
            nullable=item["nullable"],
        )
        for item in normalized_columns
    ]
    table = Table(normalized_name, MetaData(), *definitions)
    table.create(bind=engine, checkfirst=False)

    definition = db.scalar(
        select(CustomTableDefinition).where(CustomTableDefinition.table_name == normalized_name)
    )
    if definition is None:
        definition = CustomTableDefinition(
            table_name=normalized_name,
            columns=normalized_columns,
            purpose=(purpose or "").strip()[:1000] or None,
        )
        db.add(definition)
    else:
        definition.columns = normalized_columns
        definition.purpose = (purpose or "").strip()[:1000] or None
    db.commit()
    db.refresh(definition)
    return {
        "type": "custom_table",
        "name": normalized_name,
        "id": definition.id,
        "columns": normalized_columns,
        "purpose": definition.purpose,
    }


def prepare_report_view(
    db: Session,
    *,
    view_name: str,
    source: str,
    columns: list[str],
    filters: list[dict[str, Any]] | None = None,
    aggregate: dict[str, Any] | None = None,
    order_by: str | None = None,
    limit: int | None = None,
    purpose: str | None = None,
    replace: bool = False,
) -> dict[str, Any]:
    """Create a read-only allowlisted view over existing tables."""

    normalized_name = _validate_name(view_name, VIEW_NAME_RE, "View")
    view_spec: dict[str, Any] = {
        "source": source,
        "columns": columns,
        "filters": filters or [],
        "aggregate": aggregate,
        "order_by": order_by,
        "limit": limit,
    }
    source_key, statement = _build_view_statement(view_spec)
    engine = db.get_bind()
    inspector = inspect(engine)
    exists = normalized_name in inspector.get_view_names()
    if exists and not replace:
        raise CustomSchemaError(
            f"View '{normalized_name}' already exists; set replace=true to recreate it"
        )
    sql_text = str(
        statement.compile(dialect=engine.dialect, compile_kwargs={"literal_binds": True})
    )
    with engine.begin() as connection:
        if exists and replace:
            connection.exec_driver_sql(f'DROP VIEW IF EXISTS "{normalized_name}"')
        connection.exec_driver_sql(f'CREATE VIEW IF NOT EXISTS "{normalized_name}" AS {sql_text}')

    definition = db.scalar(
        select(CustomViewDefinition).where(CustomViewDefinition.view_name == normalized_name)
    )
    if definition is None:
        definition = CustomViewDefinition(
            view_name=normalized_name,
            source=source_key,
            columns=[_validate_column_name(str(item)) for item in columns],
            filters=filters or [],
            aggregate=aggregate,
            order_by=order_by,
            limit=limit,
            purpose=(purpose or "").strip()[:1000] or None,
        )
        db.add(definition)
    else:
        definition.source = source_key
        definition.columns = [_validate_column_name(str(item)) for item in columns]
        definition.filters = filters or []
        definition.aggregate = aggregate
        definition.order_by = order_by
        definition.limit = limit
        definition.purpose = (purpose or "").strip()[:1000] or None
    db.commit()
    db.refresh(definition)
    return {
        "type": "custom_view",
        "name": normalized_name,
        "id": definition.id,
        "source": source_key,
        "columns": definition.columns,
        "purpose": definition.purpose,
    }


def list_custom_schema(db: Session) -> dict[str, list[dict[str, Any]]]:
    tables = list(db.scalars(select(CustomTableDefinition).order_by(CustomTableDefinition.id)))
    views = list(db.scalars(select(CustomViewDefinition).order_by(CustomViewDefinition.id)))
    return {
        "tables": [
            {
                "id": item.id,
                "name": item.table_name,
                "columns": item.columns,
                "purpose": item.purpose,
                "created_at": item.created_at,
                "updated_at": item.updated_at,
            }
            for item in tables
        ],
        "views": [
            {
                "id": item.id,
                "name": item.view_name,
                "source": item.source,
                "columns": item.columns,
                "filters": item.filters,
                "aggregate": item.aggregate,
                "order_by": item.order_by,
                "limit": item.limit,
                "purpose": item.purpose,
                "created_at": item.created_at,
                "updated_at": item.updated_at,
            }
            for item in views
        ],
    }


def drop_custom_object(db: Session, *, kind: str, name: str) -> dict[str, Any]:
    """Drop a custom table/view and its definition (used by approval-gated delete)."""

    engine = db.get_bind()
    if kind == "custom_table":
        normalized = _validate_name(name, TABLE_NAME_RE, "Table")
        definition = db.scalar(
            select(CustomTableDefinition).where(CustomTableDefinition.table_name == normalized)
        )
        if definition is not None:
            with engine.begin() as connection:
                connection.exec_driver_sql(f'DROP TABLE IF EXISTS "{normalized}"')
            db.delete(definition)
            db.commit()
            return {"type": "custom_table", "name": normalized, "deleted": True}
        raise CustomSchemaError(f"Custom table '{normalized}' was not found")
    if kind == "custom_view":
        normalized = _validate_name(name, VIEW_NAME_RE, "View")
        definition = db.scalar(
            select(CustomViewDefinition).where(CustomViewDefinition.view_name == normalized)
        )
        if definition is not None:
            with engine.begin() as connection:
                connection.exec_driver_sql(f'DROP VIEW IF EXISTS "{normalized}"')
            db.delete(definition)
            db.commit()
            return {"type": "custom_view", "name": normalized, "deleted": True}
        raise CustomSchemaError(f"Custom view '{normalized}' was not found")
    raise CustomSchemaError("kind must be custom_table or custom_view")


def query_custom_object(
    db: Session, *, kind: str, name: str, limit: int = 50
) -> list[dict[str, Any]]:
    """Read rows from an existing custom table or view (safe, validated names)."""

    engine = db.get_bind()
    inspector = inspect(engine)
    if kind == "custom_table":
        normalized = _validate_name(name, TABLE_NAME_RE, "Table")
        if not inspector.has_table(normalized):
            raise CustomSchemaError(f"Custom table '{normalized}' was not found")
    elif kind == "custom_view":
        normalized = _validate_name(name, VIEW_NAME_RE, "View")
        if normalized not in inspector.get_view_names():
            raise CustomSchemaError(f"Custom view '{normalized}' was not found")
    else:
        raise CustomSchemaError("kind must be custom_table or custom_view")
    safe_limit = max(1, min(int(limit), MAX_LIMIT))
    from sqlalchemy import text

    rows = db.execute(text(f'SELECT * FROM "{normalized}" LIMIT :lim'), {"lim": safe_limit})
    return [dict(row._mapping) for row in rows]


def _recreate_tables(definitions: list[Any], engine: Engine) -> None:
    inspector = inspect(engine)
    for definition in definitions:
        if inspector.has_table(definition.table_name):
            continue
        columns = _validate_columns(definition.columns or [])
        table = Table(
            definition.table_name,
            MetaData(),
            *[
                Column(
                    item["name"],
                    _column_type(item["type"]),
                    primary_key=item["primary_key"],
                    nullable=item["nullable"],
                )
                for item in columns
            ],
        )
        table.create(bind=engine, checkfirst=True)


def _recreate_views(definitions: list[Any], engine: Engine) -> None:
    existing = set(inspect(engine).get_view_names())
    for definition in definitions:
        if definition.view_name in existing:
            continue
        view_spec: dict[str, Any] = {
            "source": definition.source,
            "columns": definition.columns,
            "filters": definition.filters or [],
            "aggregate": definition.aggregate,
            "order_by": definition.order_by,
            "limit": definition.limit,
        }
        _, statement = _build_view_statement(view_spec)
        sql_text = str(
            statement.compile(dialect=engine.dialect, compile_kwargs={"literal_binds": True})
        )
        with engine.begin() as connection:
            connection.exec_driver_sql(
                f'CREATE VIEW IF NOT EXISTS "{definition.view_name}" AS {sql_text}'
            )


def sync_custom_schema(db: Session | None = None) -> None:
    """Recreate missing custom tables/views on startup from stored definitions."""

    owns_session = db is None
    if db is None:
        db = SessionLocal()
    try:
        tables = list(db.scalars(select(CustomTableDefinition).order_by(CustomTableDefinition.id)))
        views = list(db.scalars(select(CustomViewDefinition).order_by(CustomViewDefinition.id)))
        if not tables and not views:
            return
        engine = db.get_bind()
        _recreate_tables(tables, engine)
        _recreate_views(views, engine)
    finally:
        if owns_session:
            db.close()
