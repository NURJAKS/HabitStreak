"""Unit tests for authentication, user session, and profile calculation."""

from __future__ import annotations

import pytest

from tracker.auth import (
    calculate_bmi,
    ensure_guest_user,
    get_active_user,
    hash_password,
    login_user,
    logout_user,
    register_user,
    update_profile,
    verify_password,
)
from tracker.db import connect
from tracker.service import TrackerError


def test_password_hashing_and_verification() -> None:
    """Verify SHA-256 salt generation and password verification."""
    pwd = "secret_password"
    hashed, salt = hash_password(pwd)
    assert len(hashed) == 64
    assert len(salt) == 32
    assert verify_password(pwd, hashed, salt) is True
    assert verify_password("wrong_password", hashed, salt) is False


def test_calculate_bmi_categories() -> None:
    """Verify BMI formula and category classifications."""
    assert calculate_bmi(None, 180.0) is None
    assert calculate_bmi(70.0, None) is None
    assert calculate_bmi(-5.0, 180.0) is None
    assert calculate_bmi(70.0, 0.0) is None

    # Underweight (< 18.5)
    bmi, cat = calculate_bmi(45.0, 175.0)  # ~14.7
    assert cat == "bmi_underweight"

    # Normal weight (18.5 - 24.9)
    bmi, cat = calculate_bmi(70.0, 178.0)  # ~22.1
    assert cat == "bmi_normal"
    assert bmi == 22.1

    # Overweight (25.0 - 29.9)
    bmi, cat = calculate_bmi(85.0, 175.0)  # ~27.8
    assert cat == "bmi_overweight"

    # Obese (>= 30.0)
    bmi, cat = calculate_bmi(110.0, 170.0)  # ~38.1
    assert cat == "bmi_obese"


def test_register_and_authenticate_user() -> None:
    """Verify user registration, validation, login, and active session management."""
    db = connect(":memory:")

    # Validation errors
    with pytest.raises(TrackerError, match="at least 3 characters"):
        register_user(db, "a", "password123")

    with pytest.raises(TrackerError, match="letters, numbers"):
        register_user(db, "user@invalid!", "password123")

    with pytest.raises(TrackerError, match="at least 4 characters"):
        register_user(db, "valid_user", "12")

    with pytest.raises(TrackerError, match="Age must be between"):
        register_user(db, "valid_user", "pass123", age=200)

    with pytest.raises(TrackerError, match="Weight must be between"):
        register_user(db, "valid_user", "pass123", weight=500.0)

    with pytest.raises(TrackerError, match="Height must be between"):
        register_user(db, "valid_user", "pass123", height=20.0)

    # Valid registration
    user = register_user(
        db,
        username="runner_tim",
        password="timpass2026",
        full_name="Tim Runner",
        age=25,
        weight=72.0,
        height=176.0,
        personal_goals="Run 20km weekly",
    )
    assert user["username"] == "runner_tim"
    assert user["full_name"] == "Tim Runner"
    assert user["age"] == 25

    # Username uniqueness
    with pytest.raises(TrackerError, match="already taken"):
        register_user(db, "runner_tim", "otherpass")

    # Active session check
    active = get_active_user(db)
    assert active is not None
    assert active["id"] == user["id"]

    # Logout
    logout_user(db)
    assert get_active_user(db) is None

    # Invalid login
    with pytest.raises(TrackerError, match="Invalid username or password"):
        login_user(db, "nonexistent", "secret")

    with pytest.raises(TrackerError, match="Invalid username or password"):
        login_user(db, "runner_tim", "wrong_password")

    # Successful login
    logged = login_user(db, "runner_tim", "timpass2026")
    assert logged["id"] == user["id"]
    assert get_active_user(db)["id"] == user["id"]


def test_update_profile_and_guest_user() -> None:
    """Verify profile updates and instant guest user creation."""
    db = connect(":memory:")

    # Instant guest
    guest = ensure_guest_user(db)
    assert guest["username"] == "guest"
    assert get_active_user(db)["username"] == "guest"

    # Repeated call returns the same guest without error
    guest2 = ensure_guest_user(db)
    assert guest2["id"] == guest["id"]

    # Update profile
    updated = update_profile(
        db,
        user_id=guest["id"],
        full_name="Guest Upgraded",
        age=22,
        weight=71.5,
        height=177.0,
        personal_goals="Reach 10k steps every day",
    )
    assert updated["full_name"] == "Guest Upgraded"
    assert updated["weight"] == 71.5

    # Update profile validation failures
    with pytest.raises(TrackerError, match="Age must be between"):
        update_profile(db, guest["id"], "Name", 150, 70.0, 175.0, "")

    with pytest.raises(TrackerError, match="Weight must be between"):
        update_profile(db, guest["id"], "Name", 22, 10.0, 175.0, "")

    with pytest.raises(TrackerError, match="Height must be between"):
        update_profile(db, guest["id"], "Name", 22, 70.0, 350.0, "")

    with pytest.raises(TrackerError, match="User not found"):
        update_profile(db, 99999, "Name", 22, 70.0, 175.0, "")
