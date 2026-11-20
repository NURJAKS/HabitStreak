"""Unit and integration tests for Google Health Connect pedometer features."""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

import flet as ft
import pytest

from tracker.db import connect
from tracker.health_connect import HealthConnectManager, is_android
from tracker.i18n import tr
from tracker.mobile import ActivityTrackerUI
from tracker.service import (
    DATE_FMT,
    TrackerError,
    add_activity,
    get_hardware_sensor_steps,
    get_health_sync_config,
    get_or_create_steps_activity,
    get_weekly_report,
    record_hardware_sensor_steps,
    sync_health_connect_range,
    sync_health_connect_steps,
    update_health_sync_config,
)


@pytest.fixture
def memory_db():
    """In-memory SQLite database initialized with fresh schema."""
    return connect(":memory:")


def test_health_sync_config_defaults(memory_db):
    """Verify default initial values for health_sync_config table."""
    cfg = get_health_sync_config(memory_db)
    assert cfg["is_connected"] == 0
    assert cfg["auto_sync"] == 1
    assert cfg["last_sync_status"] == "IDLE"
    assert cfg["last_steps_synced"] == 0
    assert cfg["target_activity_id"] is None


def test_update_health_sync_config(memory_db):
    """Verify updating health sync settings."""
    cfg = update_health_sync_config(
        memory_db,
        is_connected=True,
        auto_sync=False,
        last_sync_status="SYNCED",
        last_steps_synced=8500,
    )
    assert cfg["is_connected"] == 1
    assert cfg["auto_sync"] == 0
    assert cfg["last_sync_status"] == "SYNCED"
    assert cfg["last_steps_synced"] == 8500


def test_get_or_create_steps_activity(memory_db):
    """Verify finding existing Steps activity or automatically creating one."""
    # First call creates default Daily Steps
    act1 = get_or_create_steps_activity(memory_db, target_steps=10000.0)
    assert act1["category"] == "Steps"
    assert act1["title"] == "Daily Steps"
    assert float(act1["target_value"]) == 10000.0

    # Second call returns the existing activity without creating a duplicate
    act2 = get_or_create_steps_activity(memory_db, target_steps=8000.0)
    assert act2["id"] == act1["id"]

    # If a custom Steps habit was pre-created, it should be reused
    db2 = connect(":memory:")
    custom_id = add_activity(db2, "Morning Walk", "Steps", 12000.0, "steps")
    found = get_or_create_steps_activity(db2)
    assert found["id"] == custom_id
    assert found["title"] == "Morning Walk"


def test_sync_health_connect_steps_and_streak(memory_db):
    """Test step synchronization, log creation, and streak progression."""
    # Rejects negative steps
    with pytest.raises(TrackerError, match="Step count cannot be negative"):
        sync_health_connect_steps(memory_db, -500)

    # Rejects non-numeric steps
    with pytest.raises(TrackerError, match="Step count must be a valid integer"):
        sync_health_connect_steps(memory_db, "abc")  # type: ignore[arg-type]

    today = date.today()
    d1 = (today - timedelta(days=2)).strftime(DATE_FMT)
    d2 = (today - timedelta(days=1)).strftime(DATE_FMT)
    d3 = today.strftime(DATE_FMT)

    # Day 1: Under target (e.g. 5,000 steps)
    r1 = sync_health_connect_steps(memory_db, steps=5000, log_date=d1)
    assert r1["steps"] == 5000
    assert not r1["is_completed"]
    assert r1["current_streak"] == 0

    # Day 2: Reaching target (10,500 steps) -> streak 1
    r2 = sync_health_connect_steps(memory_db, steps=10500, log_date=d2)
    assert r2["steps"] == 10500
    assert r2["is_completed"]
    assert r2["current_streak"] == 1

    # Day 3 (today): Reaching target (12,000 steps) -> streak 2
    r3 = sync_health_connect_steps(memory_db, steps=12000, log_date=d3)
    assert r3["steps"] == 12000
    assert r3["is_completed"]
    assert r3["current_streak"] == 2
    assert r3["longest_streak"] == 2

    # Verify config state was updated
    cfg = get_health_sync_config(memory_db)
    assert cfg["is_connected"] == 1
    assert cfg["last_sync_status"] == "SUCCESS"
    assert cfg["last_steps_synced"] == 12000


def test_sync_health_connect_range(memory_db):
    """Test batch syncing multiple days of health data."""
    today = date.today()
    batch = {
        (today - timedelta(days=2)).strftime(DATE_FMT): 10000,
        (today - timedelta(days=1)).strftime(DATE_FMT): 11000,
        today.strftime(DATE_FMT): 12500,
    }
    results = sync_health_connect_range(memory_db, batch)
    assert len(results) == 3
    assert results[-1]["current_streak"] == 3

    # Weekly report reflects total step volume
    report = get_weekly_report(memory_db, end_date=today.strftime(DATE_FMT))
    assert report["completed_checkins"] >= 3
    stats = report["activity_summaries"][0]
    assert stats["total_value"] == 33500.0


def test_health_connect_manager_lifecycle(memory_db):
    """Verify HealthConnectManager methods on emulator/desktop."""
    mgr = HealthConnectManager(memory_db, initial_simulated_steps=7500)

    # Initial summary
    summary = mgr.get_status_summary()
    assert not summary["is_connected"]
    assert summary["today_steps"] == 7500
    assert summary["target_steps"] == 10000
    assert summary["progress_ratio"] == 0.75
    assert not summary["goal_reached"]

    # Connect
    assert mgr.connect()
    assert mgr.is_connected()

    # Simulate walking +3,000 steps -> 10,500 (goal reached)
    new_total = mgr.simulate_walk(3000)
    assert new_total == 10500

    # Sync now
    res = mgr.sync_now(backfill_days=5)
    assert res["status"] == "SUCCESS"
    assert res["synced_steps"] == 10500
    assert res["is_completed"]

    summary_after = mgr.get_status_summary()
    assert summary_after["is_connected"]
    assert summary_after["today_steps"] == 10500
    assert summary_after["goal_reached"]

    # Disconnect
    mgr.disconnect()
    assert not mgr.is_connected()
    assert not mgr.get_status_summary()["is_connected"]


def test_health_connect_auto_sync_toggle(memory_db):
    """Test toggling the auto_sync property."""
    mgr = HealthConnectManager(memory_db)
    assert mgr.is_auto_sync_enabled()

    mgr.set_auto_sync(False)
    assert not mgr.is_auto_sync_enabled()

    mgr.set_auto_sync(True)
    assert mgr.is_auto_sync_enabled()


def test_is_android_helper():
    """Verify platform detection helper."""
    # In Linux test runner, is_android() returns False unless env vars are set
    assert isinstance(is_android(), bool)


def test_mobile_ui_health_connect_interactions(memory_db):
    """Verify UI rendering and click handlers for Google Health Connect."""
    fake_page = MagicMock(spec=ft.Page)
    ui = ActivityTrackerUI(fake_page, memory_db)
    ui._on_guest_login()

    # Render habits tab with Health Connect card
    ui.render_tab(0)
    assert fake_page.update.called

    # Click Connect Google Health button
    ui._on_health_connect_click(None)
    assert "Synced" in ui.last_message or "Google Health" in ui.last_message
    assert ui.health_mgr.is_connected()

    # Click Simulate +1,000 steps button
    prev_steps = ui.health_mgr.fetch_today_steps()
    ui._on_health_simulate_click(None)
    assert ui.health_mgr.fetch_today_steps() == prev_steps + 1000

    # Click Sync steps button
    ui._on_health_sync_click(None)
    assert not ui.last_error

    # Render Profile tab and test auto-sync switch
    ui.render_tab(4)
    fake_event = MagicMock()
    fake_event.control.value = False
    ui._on_toggle_auto_sync(fake_event)
    assert not ui.health_mgr.is_auto_sync_enabled()

    # Click Disconnect in Profile
    ui._on_health_disconnect_click(None)
    assert not ui.health_mgr.is_connected()


def test_health_connect_i18n():
    """Verify that all Google Health Connect localization keys exist in kz, ru, en."""
    keys = [
        "health_card_title",
        "health_card_sub",
        "health_status_connected",
        "health_status_disconnected",
        "health_btn_connect",
        "health_btn_disconnect",
        "health_btn_sync",
        "health_btn_simulate",
        "health_last_sync",
        "health_not_synced",
        "health_msg_synced",
        "health_auto_sync_toggle",
        "health_goal_reached",
        "health_privacy_note",
    ]
    for lang in ("en", "ru", "kz"):
        for k in keys:
            val = tr(k, lang, time="12:00", steps="10,000")
            assert val != k, f"Missing translation for key {k} in {lang}"
            assert len(val) > 0


def test_hardware_sensor_delta_and_reboot(memory_db):
    """Verify boot-cumulative sensor conversion handles progression, reboots, and day rollover."""
    with pytest.raises(TrackerError, match="Raw step count cannot be negative"):
        record_hardware_sensor_steps(memory_db, -10)
    with pytest.raises(TrackerError, match="Raw step count must be a valid integer"):
        record_hardware_sensor_steps(memory_db, "bad")  # type: ignore[arg-type]

    today = date.today().strftime(DATE_FMT)
    yesterday = (date.today() - timedelta(days=1)).strftime(DATE_FMT)

    # First reading establishes baseline
    r1 = record_hardware_sensor_steps(memory_db, 5000, log_date=yesterday)
    assert r1["today_sensor_steps"] == 0
    r2 = record_hardware_sensor_steps(memory_db, 5300, log_date=yesterday)
    assert r2["today_sensor_steps"] == 300

    # Day rollover starts fresh today
    r3 = record_hardware_sensor_steps(memory_db, 5300, log_date=today)
    assert r3["today_sensor_steps"] == 0

    # Normal walk progression (+450 steps)
    r4 = record_hardware_sensor_steps(memory_db, 5750, log_date=today)
    assert r4["today_sensor_steps"] == 450

    # Device reboot (raw resets below 5750 to 200) adds 200 -> 650
    r5 = record_hardware_sensor_steps(memory_db, 200, log_date=today)
    assert r5["today_sensor_steps"] == 650
    assert get_hardware_sensor_steps(memory_db, today) == 650


def test_hybrid_sync_health_connect_primary_and_sensor_fallback(memory_db):
    """Verify hybrid async sync uses Health Connect when available and falls back to sensor."""
    today = date.today().strftime(DATE_FMT)
    yesterday = (date.today() - timedelta(days=1)).strftime(DATE_FMT)

    mock_native = MagicMock()
    mock_native.request_permissions = AsyncMock(
        return_value={
            "activity_recognition": True,
            "health_connect": True,
            "pedometer_active": True,
        }
    )
    mock_native.check_health_connect_status = AsyncMock(
        return_value={"available": True, "status": "sdkAvailable"}
    )
    mock_native.get_steps_range = AsyncMock(
        return_value={"ok": True, "steps": {yesterday: 10200, today: 8400}, "error": None}
    )
    mock_native.get_latest_raw_steps = AsyncMock(
        return_value={"raw_steps": 1000, "active": True}
    )
    mock_native.start_pedometer = AsyncMock(return_value={"active": True})

    mgr = HealthConnectManager(memory_db)
    mgr.set_native_service(mock_native)
    assert mgr.is_native

    # Case 1: Health Connect succeeds and backfills yesterday + today
    res = asyncio.run(mgr.connect_native_async())
    assert res["synced_steps"] == 8400
    assert res["source"] == "Google Health Connect"
    assert res["backfilled_days"] == 1
    assert mgr.fetch_today_steps() == 8400

    # Case 2: Live hardware pedometer walks +2000 steps (exceeds HC's 8400 -> 10400)
    # First reading set baseline at 1000; next reading 3000 -> +2000 sensor steps
    # Wait: since existing logged is 8400 and sensor_today is 2000, max is 8400 until sensor > 8400.
    # Simulate Health Connect unavailable on a new DB where only hardware sensor counts:
    db2 = connect(":memory:")
    mock_fallback = MagicMock()
    mock_fallback.request_permissions = AsyncMock(
        return_value={
            "activity_recognition": True,
            "health_connect": False,
            "pedometer_active": True,
        }
    )
    mock_fallback.check_health_connect_status = AsyncMock(
        return_value={"available": False, "status": "sdkUnavailable"}
    )
    mock_fallback.get_steps_range = AsyncMock(
        return_value={"ok": False, "steps": {}, "error": "health_connect_unavailable"}
    )
    mock_fallback.get_latest_raw_steps = AsyncMock(
        return_value={"raw_steps": 4000, "active": True}
    )
    mock_fallback.start_pedometer = AsyncMock(return_value={"active": True})

    mgr2 = HealthConnectManager(db2, native_service=mock_fallback)
    asyncio.run(mgr2.connect_native_async())
    # Hardware sensor emits +1250 steps
    live = mgr2.handle_sensor_step_event(5250)
    assert live["updated"]
    assert live["sensor_steps"] == 1250
    assert mgr2.fetch_today_steps() == 1250

    mock_fallback.get_latest_raw_steps = AsyncMock(
        return_value={"raw_steps": 5250, "active": True}
    )
    sync_fb = asyncio.run(mgr2.sync_hybrid_async())
    assert sync_fb["source"] == "Hardware Pedometer"
    assert sync_fb["synced_steps"] == 1250


def test_ui_native_sensor_event_updates_tab(memory_db):
    """Verify ActivityTrackerUI handles SensorStepEvent cleanly."""
    fake_page = MagicMock(spec=ft.Page)
    ui = ActivityTrackerUI(fake_page, memory_db)
    ui._on_guest_login()
    ui.health_mgr.connect()
    ui.health_mgr.handle_sensor_step_event(1000)

    fake_evt = MagicMock()
    fake_evt.raw_steps = 1500
    ui.current_tab = 0
    ui._on_native_sensor_step(fake_evt)
    assert get_hardware_sensor_steps(memory_db) == 500


def test_flet_health_steps_event_dispatch():
    """Verify Flet resolves SensorStepEvent, PedestrianStatusEvent, and SensorErrorEvent."""
    from flet.messaging.connection import Connection
    from flet.messaging.session import Session
    from flet.pubsub.pubsub_hub import PubSubHub
    from flet_health_steps import FletHealthSteps

    received: list[tuple] = []
    conn = MagicMock(spec=Connection)
    conn.pubsubhub = PubSubHub()
    sess = Session(conn)
    sess.attach_connection(conn)
    svc = FletHealthSteps(
        on_sensor_step=lambda e: received.append(("step", e.raw_steps, e.timestamp)),
        on_pedestrian_status=lambda e: received.append(("status", e.status)),
        on_sensor_error=lambda e: received.append(("err", e.message)),
    )
    sess.get_page_patch()

    async def _run() -> None:
        await svc._trigger_event(
            "sensor_step", {"raw_steps": 4321, "timestamp": "2026-11-20T15:50:00"}
        )
        await svc._trigger_event(
            "pedestrian_status",
            {"status": "walking", "timestamp": "2026-11-20T15:50:00"},
        )
        await svc._trigger_event("sensor_error", {"message": "ok"})

    asyncio.run(_run())
    assert received == [
        ("step", 4321, "2026-11-20T15:50:00"),
        ("status", "walking"),
        ("err", "ok"),
    ]

