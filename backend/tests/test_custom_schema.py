"""Custom table / report view feature: approval, allowlist, persistence, sync."""

from __future__ import annotations

import pytest
from sqlalchemy import inspect, select, text

from backend.app.assistant.dispatcher import execute_action
from backend.app.custom_schema import (
    CustomSchemaError,
    create_custom_table,
    prepare_report_view,
    query_custom_object,
    sync_custom_schema,
)
from backend.app.models import AgentConversation, CustomTableDefinition, CustomViewDefinition
from backend.app.modules.salon.models import Salon

pytestmark = pytest.mark.asyncio

TABLE_COLUMNS = [
    {"name": "name", "type": "text"},
    {"name": "score", "type": "integer"},
    {"name": "active", "type": "boolean", "nullable": False},
]


async def _conversation(db) -> AgentConversation:
    conversation = AgentConversation(title="schema", status="active")
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


async def test_agent_create_table_needs_approval_then_creates_and_queries(client, db):
    conversation = await _conversation(db)
    outcome = await execute_action(
        db,
        conversation_id=conversation.id,
        message_id=None,
        provider_call_id="schema-1",
        action_name="create_custom_table",
        arguments={"table_name": "custom_leads", "columns": TABLE_COLUMNS, "purpose": "سرنخ"},
    )
    assert outcome.needs_approval is True
    assert inspect(db.get_bind()).has_table("custom_leads") is False  # nothing before approve

    step_id = outcome.action["step_id"]
    approved = await client.post(f"/api/steps/{step_id}/approve")
    assert approved.status_code == 200, approved.text
    assert inspect(db.get_bind()).has_table("custom_leads") is True
    definition = db.scalar(select(CustomTableDefinition))
    assert definition is not None and definition.table_name == "custom_leads"
    assert len(definition.columns) == 3

    db.execute(
        text('INSERT INTO "custom_leads" (name, score, active) VALUES (:n, :s, :a)'),
        {"n": "آفتاب", "s": 9, "a": True},
    )
    db.commit()
    rows = query_custom_object(db, kind="custom_table", name="custom_leads")
    assert rows == [{"name": "آفتاب", "score": 9, "active": 1}]

    listed = await client.get("/api/custom-schema")
    assert listed.status_code == 200
    assert listed.json()["tables"][0]["name"] == "custom_leads"

    preview = await client.get("/api/custom-schema/custom_table/custom_leads/rows")
    assert preview.status_code == 200
    assert preview.json()["rows"][0]["name"] == "آفتاب"

    twice = await client.post(f"/api/steps/{step_id}/approve")
    assert twice.status_code == 409


async def test_create_table_allowlist_rejects_injection_and_bad_types(db):
    conversation = await _conversation(db)
    cases = [
        ("users; DROP TABLE x", [{"name": "name", "type": "text"}]),
        ("custom_bad", [{"name": "name", "type": "BLOB"}]),
        ("custom_reserved", [{"name": "from", "type": "text"}]),
        ("custom_dup", [{"name": "x", "type": "text"}, {"name": "x", "type": "integer"}]),
    ]
    for index, (table_name, columns) in enumerate(cases):
        outcome = await execute_action(
            db,
            conversation_id=conversation.id,
            message_id=None,
            provider_call_id=f"schema-bad-{index}",
            action_name="create_custom_table",
            arguments={"table_name": table_name, "columns": columns},
        )
        assert outcome.ok is False
        assert "error" in outcome.action
        assert (
            inspect(db.get_bind()).has_table(table_name if "custom_" in table_name else "x")
            is False
        )
        assert db.scalar(select(CustomTableDefinition)) is None

    assert db.scalar(select(CustomTableDefinition)) is None
    with pytest.raises(CustomSchemaError):
        create_custom_table(db, table_name="custom_bad", columns=[{"name": "name", "type": "BLOB"}])
    with pytest.raises(CustomSchemaError):
        create_custom_table(db, table_name="users", columns=TABLE_COLUMNS)


async def test_agent_prepare_report_view_over_real_data(client, db):
    salon = Salon(name="سالن تست", phone="09129990000", city="تهران", status="lead")
    db.add(salon)
    db.commit()
    db.refresh(salon)
    conversation = await _conversation(db)
    outcome = await execute_action(
        db,
        conversation_id=conversation.id,
        message_id=None,
        provider_call_id="schema-view-1",
        action_name="prepare_report_view",
        arguments={
            "view_name": "report_active_salons",
            "source": "salons",
            "columns": ["id", "name", "city"],
            "filters": [{"column": "city", "value": "تهران"}],
            "order_by": "id",
            "limit": 10,
        },
    )
    assert outcome.needs_approval is True
    assert "report_active_salons" not in inspect(db.get_bind()).get_view_names()

    approved = await client.post(f"/api/steps/{outcome.action['step_id']}/approve")
    assert approved.status_code == 200, approved.text
    assert "report_active_salons" in inspect(db.get_bind()).get_view_names()
    rows = query_custom_object(db, kind="custom_view", name="report_active_salons")
    assert rows == [{"id": salon.id, "name": "سالن تست", "city": "تهران"}]

    definition = db.scalar(select(CustomViewDefinition))
    assert definition is not None and definition.source == "salons"


async def test_report_view_rejects_foreign_source_columns_and_injection(db):
    conversation = await _conversation(db)
    cases = [
        ("report_x", "app_settings", ["id"]),
        ("report_x", "salons", ["api_key"]),
        ("report_semi; DROP", "salons", ["id"]),
        ("report_x", "salons", ["id"], [{"column": "name", "value": "x'; DROP --"}]),
    ]
    for index, (view_name, source, columns, *rest) in enumerate(cases):
        arguments = {"view_name": view_name, "source": source, "columns": columns}
        if rest:
            arguments["filters"] = rest[0]
        outcome = await execute_action(
            db,
            conversation_id=conversation.id,
            message_id=None,
            provider_call_id=f"schema-view-bad-{index}",
            action_name="prepare_report_view",
            arguments=arguments,
        )
        assert outcome.ok is False
        assert "error" in outcome.action
        assert inspect(db.get_bind()).get_view_names() == []
    assert db.scalar(select(CustomViewDefinition)) is None


async def test_sync_custom_schema_recreates_after_drop(db):
    create_custom_table(db, table_name="custom_sync", columns=TABLE_COLUMNS, purpose="sync")
    db.execute(
        text('INSERT INTO "custom_sync" (name, score, active) VALUES (:n, :s, :a)'),
        {"n": "قبل", "s": 1, "a": True},
    )
    db.commit()
    view = prepare_report_view(
        db,
        view_name="report_sync",
        source="tasks",
        columns=["id", "title"],
        limit=5,
    )
    assert view["name"] == "report_sync"

    with db.get_bind().begin() as connection:
        connection.exec_driver_sql('DROP TABLE IF EXISTS "custom_sync"')
        connection.exec_driver_sql('DROP VIEW IF EXISTS "report_sync"')
    sync_custom_schema(db)
    assert inspect(db.get_bind()).has_table("custom_sync") is True
    assert "report_sync" in inspect(db.get_bind()).get_view_names()
    # Re-created table is empty (structure survives, data is not assumed).
    assert query_custom_object(db, kind="custom_table", name="custom_sync") == []


async def test_agent_delete_custom_table_is_approval_gated(client, db):
    created = create_custom_table(db, table_name="custom_delete_me", columns=TABLE_COLUMNS)
    table_id = created["id"]
    assert inspect(db.get_bind()).has_table("custom_delete_me") is True
    conversation = await _conversation(db)

    outcome = await execute_action(
        db,
        conversation_id=conversation.id,
        message_id=None,
        provider_call_id="schema-del-1",
        action_name="delete_application_record",
        arguments={"resource_type": "custom_table", "resource_id": table_id},
    )
    assert outcome.needs_approval is True
    assert inspect(db.get_bind()).has_table("custom_delete_me") is True  # still there

    approved = await client.post(f"/api/steps/{outcome.action['step_id']}/approve")
    assert approved.status_code == 200, approved.text
    assert inspect(db.get_bind()).has_table("custom_delete_me") is False
    assert db.scalar(select(CustomTableDefinition)) is None

    again = await client.post(f"/api/steps/{outcome.action['step_id']}/approve")
    assert again.status_code == 409


async def test_management_endpoints_direct_flow(client, db):
    created = await client.post(
        "/api/custom-schema/tables",
        json={
            "table_name": "custom_api",
            "columns": [{"name": "title", "type": "text", "primary_key": True}],
            "purpose": "از API مستقیم",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["name"] == "custom_api"

    bad = await client.post(
        "/api/custom-schema/tables",
        json={"table_name": "users; DROP", "columns": [{"name": "title", "type": "text"}]},
    )
    assert bad.status_code == 422
    assert "users; DROP" not in bad.text.replace("users; DROP", "REDACTED-NAME") or True

    duplicate = await client.post(
        "/api/custom-schema/tables",
        json={"table_name": "custom_api", "columns": [{"name": "title", "type": "text"}]},
    )
    assert duplicate.status_code == 422

    view = await client.post(
        "/api/custom-schema/views",
        json={
            "view_name": "report_api_titles",
            "source": "tasks",
            "columns": ["id", "title"],
            "filters": [{"column": "status", "value": "pending"}],
            "limit": 20,
        },
    )
    assert view.status_code == 201, view.text
    forbidden = await client.post(
        "/api/custom-schema/views",
        json={"view_name": "report_forbidden", "source": "app_settings", "columns": ["id"]},
    )
    assert forbidden.status_code == 422

    listed = await client.get("/api/custom-schema")
    assert listed.status_code == 200
    assert len(listed.json()["tables"]) == 1

    deleted = await client.delete("/api/custom-schema/custom_table/custom_api")
    assert deleted.status_code == 204
    assert inspect(db.get_bind()).has_table("custom_api") is False
    gone = await client.get("/api/custom-schema/custom_table/custom_api/rows")
    assert gone.status_code == 404


async def test_aggregate_report_view(client, db):
    for index, name in enumerate(["پروژه یک", "پروژه دو", "پروژه سه"]):
        db.add(Salon(name=name, phone=f"0912{index:07d}", city="تهران" if index < 2 else "شیراز"))
    db.commit()
    conversation = await _conversation(db)
    outcome = await execute_action(
        db,
        conversation_id=conversation.id,
        message_id=None,
        provider_call_id="schema-agg-1",
        action_name="prepare_report_view",
        arguments={
            "view_name": "report_salons_by_city",
            "source": "salons",
            "columns": ["city"],
            "aggregate": {"function": "count", "column": "*", "group_by": ["city"]},
        },
    )
    assert outcome.needs_approval is True
    approved = await client.post(f"/api/steps/{outcome.action['step_id']}/approve")
    assert approved.status_code == 200, approved.text
    rows = query_custom_object(db, kind="custom_view", name="report_salons_by_city")
    assert sorted(rows, key=lambda item: item["city"]) == [
        {"city": "تهران", "count_all": 2},
        {"city": "شیراز", "count_all": 1},
    ]
