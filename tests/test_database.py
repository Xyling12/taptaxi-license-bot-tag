import pytest

from database import Database


@pytest.mark.asyncio
async def test_upsert_and_get_license_request(tmp_path):
    db = Database(str(tmp_path / "licenses.db"))
    await db.init()

    is_new = await db.upsert_request("DEV-001", 12345, "driver_one")
    assert is_new is True

    record = await db.get("DEV-001")
    assert record is not None
    assert record["device_id"] == "DEV-001"
    assert record["telegram_id"] == 12345
    assert record["telegram_username"] == "driver_one"
    assert record["status"] == "pending"
    assert record["license_code"] is None
    assert record["created_at"]


@pytest.mark.asyncio
async def test_upsert_existing_device_updates_telegram_data(tmp_path):
    db = Database(str(tmp_path / "licenses.db"))
    await db.init()

    await db.upsert_request("DEV-002", 111, "old_user")
    is_new = await db.upsert_request("DEV-002", 222, "new_user")

    assert is_new is False

    record = await db.get("DEV-002")
    assert record is not None
    assert record["telegram_id"] == 222
    assert record["telegram_username"] == "new_user"
    assert record["status"] == "pending"


@pytest.mark.asyncio
async def test_approve_revoke_and_list_flow(tmp_path):
    db = Database(str(tmp_path / "licenses.db"))
    await db.init()

    await db.upsert_request("DEV-003", 333, "driver_three")
    approved = await db.approve("DEV-003", "ABCDEF1234567890")

    assert approved is not None
    assert approved["status"] == "approved"
    assert approved["license_code"] == "ABCDEF1234567890"
    assert approved["approved_at"]

    revoked = await db.revoke("DEV-003")
    assert revoked is True

    revoked_record = await db.get("DEV-003")
    assert revoked_record is not None
    assert revoked_record["status"] == "revoked"

    all_records = await db.list_all()
    assert len(all_records) == 1
    assert all_records[0]["device_id"] == "DEV-003"
