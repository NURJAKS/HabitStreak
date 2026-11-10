"""Seed sample physical activities and 7-day habit streaks for demonstration."""

from __future__ import annotations

from datetime import date, timedelta

from tracker.auth import register_user, set_active_session
from tracker.db import DEFAULT_DB_NAME, connect
from tracker.service import (
    DATE_FMT,
    TrackerError,
    add_activity,
    export_backup,
    log_progress,
)


def seed_database(db_path: str = DEFAULT_DB_NAME) -> None:
    """Populate SQLite database with sample habits, streaks, profile, and a backup."""
    db = connect(db_path)

    # Seed demo user account
    try:
        user = register_user(
            db,
            username="alex",
            password="streak2026",
            full_name="Alex Johnson",
            age=22,
            weight=73.5,
            height=178.0,
            personal_goals="Run 10km weekly, maintain a 30-day streak, and drink 2.5L water daily.",
        )
        set_active_session(db, int(user["id"]))
    except TrackerError:
        pass

    samples = [
        ("Morning Run", "Cardio", 5.0, "km"),
        ("Daily 10k Steps", "Steps", 10000.0, "steps"),
        ("Pushup Session", "Strength", 50.0, "reps"),
        ("Water Hydration", "Hydration", 2.5, "L"),
    ]
    act_ids: list[int] = []
    for title, cat, target, unit in samples:
        try:
            act_ids.append(add_activity(db, title, cat, target, unit))
        except TrackerError:
            row = db.execute(
                "SELECT id FROM activities WHERE title = ?", (title,)
            ).fetchone()
            if row:
                act_ids.append(int(row["id"]))

    today = date.today()
    for offset in range(6, -1, -1):
        day_str = (today - timedelta(days=offset)).strftime(DATE_FMT)
        # Activity 1: 7-day unbroken streak
        log_progress(db, act_ids[0], day_str, 5.5, "Completed morning track")
        # Activity 2: 5-day streak (missed 6 days ago, completed last 5 days)
        if offset != 5:
            log_progress(db, act_ids[1], day_str, 11200.0, "Campus walk")
        # Activity 3: Completed on even offsets, 35/50 (70%) today for visual demo
        if offset == 0:
            log_progress(db, act_ids[2], day_str, 35.0, "2 sets done, 15 reps left")
        elif offset % 2 == 0:
            log_progress(db, act_ids[2], day_str, 60.0, "3 sets of 20")
        else:
            log_progress(db, act_ids[2], day_str, 25.0, "Partial warmup")
        # Activity 4: Completed last 3 days
        if offset <= 2:
            log_progress(db, act_ids[3], day_str, 2.8, "Daily bottle goal")

    export_backup(db, "backups/demo_snapshot.json")
    db.close()
    print(f"Seeded {len(act_ids)} activities and 7-day logs into '{db_path}'.")


if __name__ == "__main__":
    seed_database()
