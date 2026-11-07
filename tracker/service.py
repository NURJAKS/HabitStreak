"""Core business logic for Physical Activity Tracker (independent of UI)."""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from tracker.db import connect

DATE_FMT = "%Y-%m-%d"
TIMESTAMP_FMT = "%Y-%m-%d %H:%M:%S"
WEEK_DAYS = 7
MAX_TITLE_LENGTH = 80
VALID_CATEGORIES = ("Cardio", "Strength", "Flexibility", "Steps", "Hydration", "Sport")


class TrackerError(Exception):
    """Domain exception raised when business validation rules fail."""


def parse_date(value: str) -> date:
    """Parse a YYYY-MM-DD string into a date object or raise TrackerError."""
    if not isinstance(value, str):
        raise TrackerError("Date must be a string in YYYY-MM-DD format")
    try:
        return datetime.strptime(value.strip(), DATE_FMT).date()
    except ValueError as exc:
        raise TrackerError("Date must be in YYYY-MM-DD format") from exc


def _validate_activity_inputs(
    title: str, category: str, target_value: float, unit: str
) -> tuple[str, str, float, str]:
    """Validate and normalize inputs for creating an activity."""
    clean_title = (title or "").strip()
    clean_category = (category or "").strip()
    clean_unit = (unit or "").strip()
    if not clean_title:
        raise TrackerError("Activity title must not be empty")
    if len(clean_title) > MAX_TITLE_LENGTH:
        raise TrackerError(f"Activity title must not exceed {MAX_TITLE_LENGTH} characters")
    if not clean_category:
        raise TrackerError("Category must not be empty")
    if not clean_unit:
        raise TrackerError("Unit must not be empty")
    try:
        numeric_target = float(target_value)
    except (TypeError, ValueError) as exc:
        raise TrackerError("Target value must be a valid number") from exc
    if numeric_target <= 0:
        raise TrackerError("Target value must be greater than zero")
    return clean_title, clean_category, numeric_target, clean_unit


def add_activity(
    db: sqlite3.Connection,
    title: str,
    category: str,
    target_value: float,
    unit: str,
) -> int:
    """Create a new physical activity goal and return its ID."""
    clean_title, clean_cat, num_target, clean_unit = _validate_activity_inputs(
        title, category, target_value, unit
    )
    now_str = datetime.now().strftime(TIMESTAMP_FMT)
    try:
        cur = db.execute(
            "INSERT INTO activities (title, category, target_value, unit, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (clean_title, clean_cat, num_target, clean_unit, now_str),
        )
        db.commit()
        return int(cur.lastrowid or 0)
    except sqlite3.IntegrityError as exc:
        raise TrackerError(f"Activity '{clean_title}' already exists") from exc


def get_activity(db: sqlite3.Connection, activity_id: int) -> dict[str, Any]:
    """Fetch a single activity by ID or raise TrackerError."""
    row = db.execute(
        "SELECT id, title, category, target_value, unit, created_at "
        "FROM activities WHERE id = ?",
        (activity_id,),
    ).fetchone()
    if not row:
        raise TrackerError("Activity not found")
    return dict(row)


def delete_activity(db: sqlite3.Connection, activity_id: int) -> None:
    """Delete an activity and its associated logs by ID."""
    cur = db.execute("DELETE FROM activities WHERE id = ?", (activity_id,))
    db.commit()
    if cur.rowcount == 0:
        raise TrackerError("Activity not found")


def log_progress(
    db: sqlite3.Connection,
    activity_id: int,
    log_date: str,
    actual_value: float,
    notes: str = "",
) -> int:
    """Record or update daily activity progress for a given date."""
    parsed_date = parse_date(log_date).strftime(DATE_FMT)
    try:
        numeric_actual = float(actual_value)
    except (TypeError, ValueError) as exc:
        raise TrackerError("Progress value must be a valid number") from exc
    if numeric_actual < 0:
        raise TrackerError("Progress value cannot be negative")

    activity = get_activity(db, activity_id)
    is_completed = int(numeric_actual >= float(activity["target_value"]))
    clean_notes = (notes or "").strip()

    cur = db.execute(
        "INSERT INTO activity_logs (activity_id, log_date, actual_value, is_completed, notes) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(activity_id, log_date) DO UPDATE SET "
        "actual_value = excluded.actual_value, "
        "is_completed = excluded.is_completed, "
        "notes = excluded.notes",
        (activity_id, parsed_date, numeric_actual, is_completed, clean_notes),
    )
    db.commit()
    return int(cur.lastrowid or 0)


def get_activity_logs(
    db: sqlite3.Connection, activity_id: int | None = None
) -> list[dict[str, Any]]:
    """Return activity logs ordered by date descending."""
    sql = (
        "SELECT l.id, l.activity_id, a.title AS activity_title, a.unit, "
        "a.target_value, l.log_date, l.actual_value, l.is_completed, l.notes "
        "FROM activity_logs l "
        "JOIN activities a ON a.id = l.activity_id"
    )
    params: tuple[Any, ...] = ()
    if activity_id is not None:
        get_activity(db, activity_id)
        sql += " WHERE l.activity_id = ?"
        params = (activity_id,)
    rows = db.execute(sql + " ORDER BY l.log_date DESC, l.id DESC", params).fetchall()
    return [dict(r) for r in rows]


def _compute_longest_streak(sorted_dates: list[date]) -> int:
    """Compute the maximum consecutive day chain from sorted unique dates."""
    if not sorted_dates:
        return 0
    longest = 1
    current = 1
    for idx in range(1, len(sorted_dates)):
        if (sorted_dates[idx] - sorted_dates[idx - 1]).days == 1:
            current += 1
            longest = max(longest, current)
        else:
            current = 1
    return longest


def _compute_current_streak(completed_set: set[date], anchor: date) -> int:
    """Compute active streak counting backwards from anchor or anchor - 1 day."""
    if anchor in completed_set:
        cursor = anchor
    elif (anchor - timedelta(days=1)) in completed_set:
        cursor = anchor - timedelta(days=1)
    else:
        return 0
    streak = 0
    while cursor in completed_set:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def calculate_streak(
    db: sqlite3.Connection,
    activity_id: int,
    reference_date: str | None = None,
) -> dict[str, int]:
    """Calculate current streak, longest streak, and total completed days."""
    get_activity(db, activity_id)
    rows = db.execute(
        "SELECT log_date, is_completed FROM activity_logs "
        "WHERE activity_id = ? ORDER BY log_date ASC",
        (activity_id,),
    ).fetchall()
    completed_dates = [
        parse_date(r["log_date"]) for r in rows if int(r["is_completed"]) == 1
    ]
    if not completed_dates:
        return {"current_streak": 0, "longest_streak": 0, "total_completed": 0}

    if reference_date is not None:
        anchor = parse_date(reference_date)
    else:
        anchor = parse_date(rows[-1]["log_date"])

    completed_set = set(completed_dates)
    return {
        "current_streak": _compute_current_streak(completed_set, anchor),
        "longest_streak": _compute_longest_streak(completed_dates),
        "total_completed": len(completed_dates),
    }


def list_activities(
    db: sqlite3.Connection, reference_date: str | None = None
) -> list[dict[str, Any]]:
    """List all activities enriched with their current and longest streaks."""
    rows = db.execute(
        "SELECT id, title, category, target_value, unit, created_at "
        "FROM activities ORDER BY id ASC"
    ).fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        streaks = calculate_streak(db, item["id"], reference_date=reference_date)
        item.update(streaks)
        result.append(item)
    return result


def _build_activity_weekly_stats(
    activities: list[dict[str, Any]],
    logs_by_act: dict[int, list[sqlite3.Row]],
) -> list[dict[str, Any]]:
    """Build per-activity weekly completion metrics."""
    summaries: list[dict[str, Any]] = []
    for act in activities:
        act_logs = logs_by_act.get(act["id"], [])
        comp_days = sum(1 for r in act_logs if int(r["is_completed"]) == 1)
        total_val = sum(float(r["actual_value"]) for r in act_logs)
        rate = round((comp_days / WEEK_DAYS) * 100.0, 1)
        summaries.append({
            "activity_id": act["id"],
            "title": act["title"],
            "unit": act["unit"],
            "completed_days": comp_days,
            "total_value": round(total_val, 2),
            "completion_rate": rate,
        })
    return summaries


def get_weekly_report(
    db: sqlite3.Connection, end_date: str | None = None
) -> dict[str, Any]:
    """Generate a 7-day physical activity report ending on end_date."""
    end_dt = parse_date(end_date) if end_date else date.today()
    start_dt = end_dt - timedelta(days=WEEK_DAYS - 1)
    start_str, end_str = start_dt.strftime(DATE_FMT), end_dt.strftime(DATE_FMT)

    activities = list_activities(db, reference_date=end_str)
    rows = db.execute(
        "SELECT activity_id, log_date, actual_value, is_completed "
        "FROM activity_logs WHERE log_date >= ? AND log_date <= ?",
        (start_str, end_str),
    ).fetchall()

    logs_by_act: dict[int, list[sqlite3.Row]] = {}
    logs_by_day: dict[str, int] = {}
    for row in rows:
        logs_by_act.setdefault(row["activity_id"], []).append(row)
        if int(row["is_completed"]) == 1:
            logs_by_day[row["log_date"]] = logs_by_day.get(row["log_date"], 0) + 1

    daily_breakdown = [
        {
            "date": (start_dt + timedelta(days=i)).strftime(DATE_FMT),
            "completed_count": logs_by_day.get(
                (start_dt + timedelta(days=i)).strftime(DATE_FMT), 0
            ),
        }
        for i in range(WEEK_DAYS)
    ]
    total_completed = sum(d["completed_count"] for d in daily_breakdown)
    possible = len(activities) * WEEK_DAYS
    overall_rate = round((total_completed / possible) * 100.0, 1) if possible else 0.0

    return {
        "start_date": start_str,
        "end_date": end_str,
        "total_activities": len(activities),
        "completed_checkins": total_completed,
        "possible_checkins": possible,
        "completion_rate": overall_rate,
        "daily_breakdown": daily_breakdown,
        "activity_summaries": _build_activity_weekly_stats(activities, logs_by_act),
    }


def _record_backup_event(
    db: sqlite3.Connection,
    file_path: str,
    activities_count: int,
    logs_count: int,
    action: str,
) -> None:
    """Log an EXPORT or RESTORE operation in backup_records."""
    now_str = datetime.now().strftime(TIMESTAMP_FMT)
    db.execute(
        "INSERT INTO backup_records "
        "(created_at, file_path, activities_count, logs_count, action) "
        "VALUES (?, ?, ?, ?, ?)",
        (now_str, str(file_path), activities_count, logs_count, action),
    )
    db.commit()


def export_backup(db: sqlite3.Connection, file_path: str | Path) -> dict[str, Any]:
    """Export all activities and logs to a JSON backup file."""
    target = Path(file_path)
    if target.suffix.lower() != ".json":
        raise TrackerError("Backup file must have a .json extension")
    target.parent.mkdir(parents=True, exist_ok=True)

    activities = [
        dict(r)
        for r in db.execute(
            "SELECT id, title, category, target_value, unit, created_at "
            "FROM activities ORDER BY id ASC"
        ).fetchall()
    ]
    logs = [
        dict(r)
        for r in db.execute(
            "SELECT id, activity_id, log_date, actual_value, is_completed, notes "
            "FROM activity_logs ORDER BY id ASC"
        ).fetchall()
    ]
    payload = {
        "version": "1.0",
        "exported_at": datetime.now().strftime(TIMESTAMP_FMT),
        "activities": activities,
        "activity_logs": logs,
    }
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    _record_backup_event(db, str(target), len(activities), len(logs), "EXPORT")
    return {
        "file_path": str(target),
        "activities_count": len(activities),
        "logs_count": len(logs),
    }


def _validate_backup_payload(data: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Validate structure and required keys of a parsed JSON backup."""
    if not isinstance(data, dict):
        raise TrackerError("Invalid backup format: root must be a JSON object")
    if "activities" not in data or "activity_logs" not in data:
        raise TrackerError("Invalid backup format: missing required keys")
    activities = data["activities"]
    logs = data["activity_logs"]
    if not isinstance(activities, list) or not isinstance(logs, list):
        raise TrackerError("Invalid backup format: collections must be lists")
    return activities, logs


def restore_backup(db: sqlite3.Connection, file_path: str | Path) -> dict[str, Any]:
    """Restore activities and logs atomically from a JSON backup file."""
    source = Path(file_path)
    if not source.exists() or not source.is_file():
        raise TrackerError("Backup file not found")
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise TrackerError("Backup file contains invalid JSON") from exc

    activities, logs = _validate_backup_payload(raw)
    try:
        db.execute("DELETE FROM activity_logs")
        db.execute("DELETE FROM activities")
        for act in activities:
            _validate_activity_inputs(
                act["title"], act["category"], act["target_value"], act["unit"]
            )
            db.execute(
                "INSERT INTO activities (id, title, category, target_value, unit, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    int(act["id"]),
                    act["title"].strip(),
                    act["category"].strip(),
                    float(act["target_value"]),
                    act["unit"].strip(),
                    act.get("created_at") or datetime.now().strftime(TIMESTAMP_FMT),
                ),
            )
        for log in logs:
            parse_date(log["log_date"])
            db.execute(
                "INSERT INTO activity_logs "
                "(id, activity_id, log_date, actual_value, is_completed, notes) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    int(log["id"]),
                    int(log["activity_id"]),
                    log["log_date"].strip(),
                    float(log["actual_value"]),
                    int(log["is_completed"]),
                    log.get("notes", ""),
                ),
            )
        db.commit()
    except (KeyError, TypeError, ValueError, sqlite3.Error, TrackerError) as exc:
        db.rollback()
        if isinstance(exc, TrackerError):
            raise
        raise TrackerError(f"Failed to restore backup data: {exc}") from exc

    _record_backup_event(db, str(source), len(activities), len(logs), "RESTORE")
    return {
        "file_path": str(source),
        "activities_count": len(activities),
        "logs_count": len(logs),
    }


def get_backup_history(db: sqlite3.Connection) -> list[dict[str, Any]]:
    """Return history of backup export and restore events."""
    rows = db.execute(
        "SELECT id, created_at, file_path, activities_count, logs_count, action "
        "FROM backup_records ORDER BY id DESC"
    ).fetchall()
    return [dict(r) for r in rows]


__all__ = [
    "DATE_FMT",
    "VALID_CATEGORIES",
    "TrackerError",
    "add_activity",
    "calculate_streak",
    "connect",
    "delete_activity",
    "export_backup",
    "get_activity",
    "get_activity_logs",
    "get_backup_history",
    "get_weekly_report",
    "list_activities",
    "log_progress",
    "parse_date",
    "restore_backup",
]
