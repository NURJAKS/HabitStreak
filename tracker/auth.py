"""Authentication, user profile management, and health metrics calculation."""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
from datetime import datetime
from typing import Any

from tracker.service import TIMESTAMP_FMT, TrackerError


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """Hash a password using SHA-256 with a unique random salt."""
    clean_salt = salt or secrets.token_hex(16)
    hashed = hashlib.sha256((clean_salt + password).encode("utf-8")).hexdigest()
    return hashed, clean_salt


def verify_password(password: str, hashed: str, salt: str) -> bool:
    """Verify whether a candidate password matches the stored hash."""
    candidate_hash, _ = hash_password(password, salt)
    return secrets.compare_digest(candidate_hash, hashed)


def calculate_bmi(
    weight: float | None, height: float | None
) -> tuple[float, str] | None:
    """Calculate Body Mass Index (BMI) and category (underweight, normal, overweight, obese)."""
    if weight is None or height is None:
        return None
    try:
        w = float(weight)
        h = float(height)
    except (ValueError, TypeError):
        return None

    if w <= 0 or h <= 0:
        return None

    height_m = h / 100.0
    bmi = round(w / (height_m * height_m), 1)

    if bmi < 18.5:
        category = "bmi_underweight"
    elif bmi < 25.0:
        category = "bmi_normal"
    elif bmi < 30.0:
        category = "bmi_overweight"
    else:
        category = "bmi_obese"

    return bmi, category


def register_user(
    db: sqlite3.Connection,
    username: str,
    password: str,
    full_name: str = "",
    age: int | None = None,
    weight: float | None = None,
    height: float | None = None,
    personal_goals: str = "",
) -> dict[str, Any]:
    """Register a new user account with hashed credentials and optional profile metrics."""
    clean_username = (username or "").strip().lower()
    clean_password = (password or "").strip()
    clean_full_name = (full_name or "").strip()
    clean_goals = (personal_goals or "").strip()

    if len(clean_username) < 3:
        raise TrackerError("Username must be at least 3 characters")
    if not clean_username.replace("_", "").isalnum():
        raise TrackerError("Username can only contain letters, numbers, and underscores")
    if len(clean_password) < 4:
        raise TrackerError("Password must be at least 4 characters")

    existing = db.execute(
        "SELECT id FROM users WHERE username = ?", (clean_username,)
    ).fetchone()
    if existing:
        raise TrackerError("Username already taken")

    clean_age: int | None = None
    if age is not None and str(age).strip():
        try:
            clean_age = int(age)
            if clean_age < 5 or clean_age > 120:
                raise TrackerError("Age must be between 5 and 120")
        except ValueError as exc:
            raise TrackerError("Age must be an integer") from exc

    clean_weight: float | None = None
    if weight is not None and str(weight).strip():
        try:
            clean_weight = round(float(weight), 1)
            if clean_weight <= 20 or clean_weight > 400:
                raise TrackerError("Weight must be between 20 and 400 kg")
        except ValueError as exc:
            raise TrackerError("Weight must be a number") from exc

    clean_height: float | None = None
    if height is not None and str(height).strip():
        try:
            clean_height = round(float(height), 1)
            if clean_height <= 50 or clean_height > 260:
                raise TrackerError("Height must be between 50 and 260 cm")
        except ValueError as exc:
            raise TrackerError("Height must be a number") from exc

    pwd_hash, salt = hash_password(clean_password)
    now_str = datetime.now().strftime(TIMESTAMP_FMT)

    cursor = db.execute(
        """
        INSERT INTO users (
            username, password_hash, salt, full_name, age, weight, height, personal_goals, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            clean_username,
            pwd_hash,
            salt,
            clean_full_name or clean_username.capitalize(),
            clean_age,
            clean_weight,
            clean_height,
            clean_goals,
            now_str,
        ),
    )
    db.commit()
    user_id = cursor.lastrowid
    set_active_session(db, user_id)
    return get_user_by_id(db, user_id)  # type: ignore[return-value]


def login_user(
    db: sqlite3.Connection, username: str, password: str
) -> dict[str, Any]:
    """Authenticate username and password, updating the active session on success."""
    clean_username = (username or "").strip().lower()
    clean_password = (password or "").strip()

    row = db.execute(
        "SELECT * FROM users WHERE username = ?", (clean_username,)
    ).fetchone()
    if not row:
        raise TrackerError("Invalid username or password")

    if not verify_password(clean_password, row["password_hash"], row["salt"]):
        raise TrackerError("Invalid username or password")

    user_id = int(row["id"])
    set_active_session(db, user_id)
    return dict(row)


def set_active_session(db: sqlite3.Connection, user_id: int | None) -> None:
    """Store or clear the single active session pointer."""
    now_str = datetime.now().strftime(TIMESTAMP_FMT)
    db.execute(
        """
        INSERT INTO session (id, active_user_id, updated_at)
        VALUES (1, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            active_user_id = excluded.active_user_id,
            updated_at = excluded.updated_at
        """,
        (user_id, now_str),
    )
    db.commit()


def logout_user(db: sqlite3.Connection) -> None:
    """Clear active session, logging the current user out."""
    set_active_session(db, None)


def get_active_user(db: sqlite3.Connection) -> dict[str, Any] | None:
    """Return the currently authenticated user dict, or None if logged out."""
    session = db.execute("SELECT active_user_id FROM session WHERE id = 1").fetchone()
    if not session or not session["active_user_id"]:
        return None
    return get_user_by_id(db, int(session["active_user_id"]))


def get_user_by_id(db: sqlite3.Connection, user_id: int) -> dict[str, Any] | None:
    """Retrieve user record by primary key."""
    row = db.execute(
        """
        SELECT id, username, full_name, age, weight, height, personal_goals, created_at
        FROM users WHERE id = ?
        """,
        (user_id,),
    ).fetchone()
    return dict(row) if row else None


def update_profile(
    db: sqlite3.Connection,
    user_id: int,
    full_name: str,
    age: int | None,
    weight: float | None,
    height: float | None,
    personal_goals: str,
) -> dict[str, Any]:
    """Validate and update user profile attributes."""
    clean_full_name = (full_name or "").strip()
    clean_goals = (personal_goals or "").strip()

    clean_age: int | None = None
    if age is not None and str(age).strip():
        try:
            clean_age = int(age)
            if clean_age < 5 or clean_age > 120:
                raise TrackerError("Age must be between 5 and 120")
        except ValueError as exc:
            raise TrackerError("Age must be an integer") from exc

    clean_weight: float | None = None
    if weight is not None and str(weight).strip():
        try:
            clean_weight = round(float(weight), 1)
            if clean_weight <= 20 or clean_weight > 400:
                raise TrackerError("Weight must be between 20 and 400 kg")
        except ValueError as exc:
            raise TrackerError("Weight must be a number") from exc

    clean_height: float | None = None
    if height is not None and str(height).strip():
        try:
            clean_height = round(float(height), 1)
            if clean_height <= 50 or clean_height > 260:
                raise TrackerError("Height must be between 50 and 260 cm")
        except ValueError as exc:
            raise TrackerError("Height must be a number") from exc

    db.execute(
        """
        UPDATE users
        SET full_name = ?, age = ?, weight = ?, height = ?, personal_goals = ?
        WHERE id = ?
        """,
        (clean_full_name, clean_age, clean_weight, clean_height, clean_goals, user_id),
    )
    db.commit()
    user = get_user_by_id(db, user_id)
    if not user:
        raise TrackerError("User not found")
    return user


def ensure_guest_user(db: sqlite3.Connection) -> dict[str, Any]:
    """Provide a instant Guest user account for quick preview without registration."""
    guest = db.execute("SELECT * FROM users WHERE username = 'guest'").fetchone()
    if guest:
        user_id = int(guest["id"])
        set_active_session(db, user_id)
        return get_user_by_id(db, user_id)  # type: ignore[return-value]

    return register_user(
        db,
        username="guest",
        password="guestpassword123",
        full_name="Guest Athlete",
        age=20,
        weight=70.0,
        height=175.0,
        personal_goals="Explore the app and build a 7-day habit streak!",
    )
