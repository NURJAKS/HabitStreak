"""Automated unit tests for Physical Activity Tracker business logic."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from tracker.service import (
    TrackerError,
    add_activity,
    calculate_streak,
    connect,
    delete_activity,
    export_backup,
    get_activity,
    get_activity_logs,
    get_backup_history,
    get_weekly_report,
    list_activities,
    log_progress,
    restore_backup,
)


@pytest.fixture()
def db() -> sqlite3.Connection:
    """Create a fresh in-memory database pre-populated with one activity."""
    conn = connect(":memory:")
    add_activity(conn, "Morning Run", "Cardio", 5.0, "km")
    return conn


def test_add_and_list_activities(db: sqlite3.Connection) -> None:
    """Verify creating activities and listing them with default zero streaks."""
    act_id = add_activity(db, "Daily Steps", "Steps", 10000, "steps")
    assert act_id == 2
    items = list_activities(db)
    assert len(items) == 2
    assert items[0]["title"] == "Morning Run"
    assert items[1]["title"] == "Daily Steps"
    assert items[1]["current_streak"] == 0
    assert items[1]["longest_streak"] == 0


def test_duplicate_activity_rejected(db: sqlite3.Connection) -> None:
    """Verify duplicate activity titles raise TrackerError."""
    with pytest.raises(TrackerError, match="already exists"):
        add_activity(db, "Morning Run", "Cardio", 3.0, "km")


@pytest.mark.parametrize(
    ("title", "category", "target", "unit"),
    [
        ("", "Cardio", 5.0, "km"),
        ("   ", "Cardio", 5.0, "km"),
        ("A" * 90, "Cardio", 5.0, "km"),
        ("Pushups", "", 50, "reps"),
        ("Pushups", "Strength", 0, "reps"),
        ("Pushups", "Strength", -10, "reps"),
        ("Pushups", "Strength", "invalid", "reps"),
        ("Pushups", "Strength", 50, ""),
    ],
)
def test_invalid_activity_inputs(
    db: sqlite3.Connection, title: str, category: str, target: object, unit: str
) -> None:
    """Verify invalid activity parameters raise TrackerError."""
    with pytest.raises(TrackerError):
        add_activity(db, title, category, target, unit)  # type: ignore[arg-type]


def test_delete_activity_and_cascade(db: sqlite3.Connection) -> None:
    """Verify deleting an activity removes its logs and raises on second delete."""
    log_progress(db, 1, "2026-11-01", 5.5, "Great pace")
    assert len(get_activity_logs(db, 1)) == 1
    delete_activity(db, 1)
    assert list_activities(db) == []
    assert get_activity_logs(db) == []
    with pytest.raises(TrackerError, match="not found"):
        delete_activity(db, 1)


def test_log_progress_partial_and_completed(db: sqlite3.Connection) -> None:
    """Verify logs below target are incomplete and at/above target are completed."""
    log_progress(db, 1, "2026-11-01", 3.2, "Short jog")
    log_progress(db, 1, "2026-11-02", 5.0, "Exact target")
    logs = get_activity_logs(db, 1)
    assert len(logs) == 2
    assert logs[0]["log_date"] == "2026-11-02"
    assert logs[0]["is_completed"] == 1
    assert logs[1]["log_date"] == "2026-11-01"
    assert logs[1]["is_completed"] == 0


def test_same_day_upsert_updates_log(db: sqlite3.Connection) -> None:
    """Verify logging twice on the same date updates the existing entry."""
    log_progress(db, 1, "2026-11-05", 2.0, "Morning")
    assert calculate_streak(db, 1)["current_streak"] == 0
    log_progress(db, 1, "2026-11-05", 6.0, "Evening finish")
    logs = get_activity_logs(db, 1)
    assert len(logs) == 1
    assert logs[0]["actual_value"] == 6.0
    assert logs[0]["is_completed"] == 1
    assert calculate_streak(db, 1)["current_streak"] == 1


@pytest.mark.parametrize(
    ("act_id", "log_date", "val"),
    [
        (1, "2026/11/01", 5.0),
        (1, "bad-date", 5.0),
        (1, 12345, 5.0),
        (1, "2026-11-01", -1.0),
        (1, "2026-11-01", "not-a-number"),
        (999, "2026-11-01", 5.0),
    ],
)
def test_invalid_log_inputs(
    db: sqlite3.Connection, act_id: int, log_date: object, val: object
) -> None:
    """Verify invalid log inputs raise TrackerError."""
    with pytest.raises(TrackerError):
        log_progress(db, act_id, log_date, val)  # type: ignore[arg-type]


def test_continuous_streak_across_year_boundary(db: sqlite3.Connection) -> None:
    """Verify consecutive day streaks across December 31 and January 1."""
    for day in ("2025-12-30", "2025-12-31", "2026-01-01", "2026-01-02"):
        log_progress(db, 1, day, 5.0)
    stats = calculate_streak(db, 1, reference_date="2026-01-02")
    assert stats["current_streak"] == 4
    assert stats["longest_streak"] == 4
    assert stats["total_completed"] == 4


def test_broken_streak_preserves_longest(db: sqlite3.Connection) -> None:
    """Verify skipping a day resets current streak while keeping longest streak."""
    for day in ("2026-11-01", "2026-11-02", "2026-11-03"):
        log_progress(db, 1, day, 5.0)
    # Skip 2026-11-04, then log 2026-11-05 and 2026-11-06
    log_progress(db, 1, "2026-11-05", 5.0)
    log_progress(db, 1, "2026-11-06", 5.0)

    stats = calculate_streak(db, 1, reference_date="2026-11-06")
    assert stats["current_streak"] == 2
    assert stats["longest_streak"] == 3
    assert stats["total_completed"] == 5


def test_active_streak_from_yesterday(db: sqlite3.Connection) -> None:
    """Verify streak stays active on reference_date if yesterday was completed."""
    log_progress(db, 1, "2026-11-05", 5.0)
    log_progress(db, 1, "2026-11-06", 5.0)
    # On 2026-11-07 (before today's workout), streak is still 2
    assert calculate_streak(db, 1, reference_date="2026-11-07")["current_streak"] == 2
    # On 2026-11-08 (missed 2026-11-07), current streak drops to 0
    assert calculate_streak(db, 1, reference_date="2026-11-08")["current_streak"] == 0


def test_weekly_report_aggregation(db: sqlite3.Connection) -> None:
    """Verify 7-day weekly report calculations across multiple activities."""
    act2 = add_activity(db, "Plank", "Strength", 2.0, "mins")
    for day in ("2026-11-01", "2026-11-02", "2026-11-04", "2026-11-07"):
        log_progress(db, 1, day, 5.0)
    for day in ("2026-11-05", "2026-11-06", "2026-11-07"):
        log_progress(db, act2, day, 3.0)

    report = get_weekly_report(db, end_date="2026-11-07")
    assert report["start_date"] == "2026-11-01"
    assert report["end_date"] == "2026-11-07"
    assert report["total_activities"] == 2
    assert report["completed_checkins"] == 7
    assert report["possible_checkins"] == 14
    assert report["completion_rate"] == 50.0
    assert len(report["daily_breakdown"]) == 7
    assert len(report["activity_summaries"]) == 2


def test_backup_export_and_restore_roundtrip(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """Verify exporting database to JSON and restoring into a clean database."""
    act2 = add_activity(db, "Hydration", "Hydration", 2.5, "L")
    log_progress(db, 1, "2026-11-06", 5.5, "Morning track")
    log_progress(db, act2, "2026-11-06", 2.5, "All day")

    backup_file = tmp_path / "tracker_backup.json"
    exp_meta = export_backup(db, backup_file)
    assert exp_meta["activities_count"] == 2
    assert exp_meta["logs_count"] == 2
    assert backup_file.exists()

    # Wipe activities and restore from backup
    delete_activity(db, 1)
    delete_activity(db, act2)
    assert list_activities(db) == []

    res_meta = restore_backup(db, backup_file)
    assert res_meta["activities_count"] == 2
    assert res_meta["logs_count"] == 2
    assert len(list_activities(db)) == 2
    assert get_activity(db, 1)["title"] == "Morning Run"

    history = get_backup_history(db)
    assert len(history) == 2
    assert {h["action"] for h in history} == {"EXPORT", "RESTORE"}


def test_backup_restore_invalid_files_rollback(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """Verify invalid backup paths or corrupted payloads raise TrackerError safely."""
    with pytest.raises(TrackerError, match=".json extension"):
        export_backup(db, tmp_path / "bad.txt")

    with pytest.raises(TrackerError, match="not found"):
        restore_backup(db, tmp_path / "missing.json")

    bad_json = tmp_path / "corrupt.json"
    bad_json.write_text("{not_valid_json", encoding="utf-8")
    with pytest.raises(TrackerError, match="invalid JSON"):
        restore_backup(db, bad_json)

    missing_keys = tmp_path / "missing_keys.json"
    missing_keys.write_text(json.dumps({"version": "1.0"}), encoding="utf-8")
    with pytest.raises(TrackerError, match="missing required keys"):
        restore_backup(db, missing_keys)

    bad_types = tmp_path / "bad_types.json"
    bad_types.write_text(
        json.dumps({"activities": "not-a-list", "activity_logs": []}),
        encoding="utf-8",
    )
    with pytest.raises(TrackerError, match="must be lists"):
        restore_backup(db, bad_types)

    # Existing activity must remain intact after failed restores
    assert len(list_activities(db)) == 1
