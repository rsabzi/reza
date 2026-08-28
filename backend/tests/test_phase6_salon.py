from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from backend.app.models import MemoryEntry, Playbook
from backend.app.modules.salon.models import Salon, SalonInteraction
from backend.app.modules.salon.service import cadence_days_from_text, daily_salon_plan

pytestmark = pytest.mark.asyncio


async def test_bulk_import_creates_valid_rows_and_reports_malformed_row(client, db):
    response = await client.post(
        "/api/salons/import",
        json={
            "salons": [
                {"name": "Niloofar", "phone": "+98 912 111 1111", "city": "Tehran"},
                {"name": "Missing phone", "city": "Shiraz"},
                {"name": "Roya", "phone": "071-1234567", "city": "Shiraz"},
            ]
        },
    )
    assert response.status_code == 207, response.text
    body = response.json()
    assert body["created_count"] == 2
    assert body["error_count"] == 1
    assert body["errors"][0]["index"] == 1
    assert any(error["loc"] == ["phone"] for error in body["errors"][0]["errors"])
    assert db.scalar(select(func.count(Salon.id))) == 2


async def test_generate_outreach_script_is_registered_and_guarded(client):
    tools = (await client.get("/api/tools")).json()
    tool = next(item for item in tools if item["name"] == "generate_outreach_script")
    assert tool["requires_approval"] is True
    assert tool["enabled"] is True


async def test_log_interaction_writes_interaction_and_memory(client, db):
    salon = (
        await client.post("/api/salons", json={"name": "Setareh", "phone": "+98 912 222 2222"})
    ).json()
    response = await client.post(
        f"/api/salons/{salon['id']}/interactions",
        json={
            "channel": "whatsapp",
            "direction": "outbound",
            "content": "Introduced growth package",
            "outcome": "asked_for_details",
        },
    )
    assert response.status_code == 201, response.text
    interaction_id = response.json()["id"]
    db.expire_all()
    interaction = db.get(SalonInteraction, interaction_id)
    memory = db.scalar(
        select(MemoryEntry).where(
            MemoryEntry.source == "salon_interaction",
            MemoryEntry.source_id == str(interaction_id),
        )
    )
    assert interaction is not None
    assert memory is not None
    assert memory.module_name == "salon"
    assert "Setareh" in memory.content
    assert len(memory.embedding) == 128


async def test_daily_plan_honors_playbook_seven_day_exclusion(db):
    as_of = datetime(2026, 8, 27, 12, tzinfo=timezone.utc)
    db.add(
        Playbook(
            title="Salon cadence",
            module_name="salon",
            content="Do not contact any salon within 7 days of the latest interaction.",
        )
    )
    recent = Salon(name="Recent Salon X", phone="09120000001")
    eligible = Salon(name="Old Salon Y", phone="09120000002")
    untouched = Salon(name="Fresh Salon Z", phone="09120000003")
    db.add_all([recent, eligible, untouched])
    db.flush()
    db.add_all(
        [
            SalonInteraction(
                salon_id=recent.id,
                channel="phone",
                content="Recent call",
                occurred_at=as_of - timedelta(days=3),
            ),
            SalonInteraction(
                salon_id=eligible.id,
                channel="phone",
                content="Old call",
                occurred_at=as_of - timedelta(days=8),
            ),
        ]
    )
    db.commit()

    plan = daily_salon_plan(db, as_of=as_of)
    names = [item["salon"].name for item in plan]
    assert "Recent Salon X" not in names  # key 3-days-vs-7-days business rule
    assert names == ["Old Salon Y", "Fresh Salon Z"]
    assert all(item["cadence_days"] == 7 for item in plan)


async def test_salon_crud_interaction_edges_and_duplicate_constraint(client, db):
    created = await client.post("/api/salons", json={"name": "CRUD Salon", "phone": "021-12345678"})
    assert created.status_code == 201
    salon_id = created.json()["id"]
    assert (await client.get(f"/api/salons/{salon_id}")).status_code == 200
    updated = await client.patch(f"/api/salons/{salon_id}", json={"status": "interested"})
    assert updated.status_code == 200
    assert updated.json()["status"] == "interested"
    assert (await client.get(f"/api/salons/{salon_id}/interactions")).json() == []

    duplicate = await client.post(
        "/api/salons", json={"name": "Duplicate", "phone": "021-12345678"}
    )
    assert duplicate.status_code == 409
    assert (
        await client.post(
            "/api/salons/99999/interactions",
            json={"channel": "phone", "content": "missing"},
        )
    ).status_code == 404
    assert (await client.get("/api/salons/99999")).status_code == 404
    assert (await client.delete(f"/api/salons/{salon_id}")).status_code == 204
    assert (await client.get(f"/api/salons/{salon_id}")).status_code == 404


async def test_cadence_parser_and_phone_db_constraint(db):
    assert cadence_days_from_text("don't contact within 14 days") == 14
    assert cadence_days_from_text("پیگیری تا ۱۰ روز انجام نشود") == 10
    db.add_all([Salon(name="A", phone="09121111111"), Salon(name="B", phone="09121111111")])
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
