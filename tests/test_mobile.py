"""Unit tests for the Duolingo-style Flet mobile UI controller."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import flet as ft
import pytest

from tracker.db import connect
from tracker.mobile import ActivityTrackerUI, main


def test_main_page_initialization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify main() configures Duolingo theme, FAB, header, and navigation bar."""
    monkeypatch.chdir(tmp_path)
    fake_page = MagicMock(spec=ft.Page)
    fake_page.window = MagicMock()
    fake_page.route = "/0"
    main(fake_page)
    assert fake_page.title == "HabitStreak — Physical Activity Tracker"
    assert fake_page.floating_action_button is not None
    assert fake_page.add.called
    assert fake_page.navigation_bar is not None


def test_mobile_ui_controller_workflow(tmp_path: Path) -> None:
    """Verify all 5 mobile UI tabs, BottomSheet, Slider, Boosts, Profile, and Backup."""
    fake_page = MagicMock(spec=ft.Page)
    db = connect(":memory:")
    ui = ActivityTrackerUI(fake_page, db)

    # Initial state gates on auth screen
    assert ui.current_user is None
    ui.render_tab(0)
    assert fake_page.update.called

    # Log in as guest to enter main app
    ui._on_guest_login()
    assert ui.current_user is not None

    # Render empty states across all 5 tabs
    for tab_idx in range(5):
        ui.render_tab(tab_idx)
    assert fake_page.update.called

    # Open BottomSheet and add an activity
    ui.open_add_sheet()
    assert fake_page.show_dialog.called
    ui.title_in.value = "Evening Cycling"
    ui.cat_dd.value = "Cardio"
    ui.target_in.value = "15"
    ui.unit_in.value = "km"
    ui._on_add_activity()
    assert "created" in ui.last_message
    assert not ui.last_error

    # Render Check-In tab, test quick boost, slider, and activity selection
    ui.render_tab(1)
    assert not ui.fab.visible
    ui._on_activity_selected()
    ui._add_quick_boost(0.25)
    assert float(ui.log_val_in.value or 0) > 0
    ui._add_quick_boost(1.0)
    assert float(ui.log_val_in.value or 0) == 15.0

    fake_slider_evt = MagicMock()
    fake_slider_evt.control.value = 18.0
    ui._on_slider_change(fake_slider_evt)
    assert float(ui.log_val_in.value or 0) == 18.0

    ui.log_date_in.value = "2026-11-07"
    ui.log_notes_in.value = "Fast ride"
    ui._on_log_progress()
    assert "Check-in saved" in ui.last_message

    # Render Weekly Report tab with active data
    ui.render_tab(2)
    assert len(ui.body_container.controls) >= 3

    # Export and Restore Backup via UI handlers
    backup_file = tmp_path / "ui_backup.json"
    ui.backup_path_in.value = str(backup_file)
    ui._on_export_backup()
    assert "Exported" in ui.last_message

    ui._on_delete_activity(1)
    assert "deleted" in ui.last_message

    ui._on_restore_backup()
    assert "Restored" in ui.last_message


def test_mobile_ui_error_handling() -> None:
    """Verify UI handlers catch TrackerError and trigger red SnackBar alerts."""
    fake_page = MagicMock(spec=ft.Page)
    db = connect(":memory:")
    ui = ActivityTrackerUI(fake_page, db)

    ui.title_in.value = ""
    ui._on_add_activity()
    assert ui.last_error and ui.last_message.startswith("Error:")

    ui.log_act_dd.value = None
    ui._on_log_progress()
    assert ui.last_error and ui.last_message.startswith("Error:")

    ui._on_delete_activity(999)
    assert ui.last_error and ui.last_message.startswith("Error:")

    ui.backup_path_in.value = "invalid.txt"
    ui._on_export_backup()
    assert ui.last_error and ui.last_message.startswith("Error:")

    ui.backup_path_in.value = "missing_file.json"
    ui._on_restore_backup()
    assert ui.last_error and ui.last_message.startswith("Error:")


def test_language_and_theme_switching() -> None:
    """Verify switching languages (KZ, RU, EN) and toggling Light/Dark themes."""
    fake_page = MagicMock(spec=ft.Page)
    fake_page.navigation_bar = ft.NavigationBar(
        destinations=[
            ft.NavigationBarDestination(icon=ft.Icons.HOME, label="1"),
            ft.NavigationBarDestination(icon=ft.Icons.CHECK, label="2"),
            ft.NavigationBarDestination(icon=ft.Icons.BAR_CHART, label="3"),
            ft.NavigationBarDestination(icon=ft.Icons.BACKUP, label="4"),
            ft.NavigationBarDestination(icon=ft.Icons.PERSON, label="5"),
        ]
    )
    db = connect(":memory:")
    ui = ActivityTrackerUI(fake_page, db)
    ui._on_guest_login()

    # Initial state
    assert ui.lang == "en"
    assert not ui.is_dark

    # Switch to Kazakh
    ui.set_language("kz")
    assert ui.lang == "kz"
    assert fake_page.update.called

    # Switch to Russian
    ui.set_language("ru")
    assert ui.lang == "ru"
    assert fake_page.update.called

    # Switch back to English
    ui.set_language("en")
    assert ui.lang == "en"

    # Toggle to Dark mode
    ui.toggle_theme()
    assert ui.is_dark is True
    assert fake_page.theme_mode == ft.ThemeMode.DARK

    # Toggle back to Light mode
    ui.toggle_theme()
    assert ui.is_dark is False
    assert fake_page.theme_mode == ft.ThemeMode.LIGHT


def test_auth_and_profile_workflows() -> None:
    """Verify registration, login, profile updates, BMI calculation, and logout."""
    fake_page = MagicMock(spec=ft.Page)
    fake_page.navigation_bar = ft.NavigationBar(
        destinations=[
            ft.NavigationBarDestination(icon=ft.Icons.HOME, label="1"),
            ft.NavigationBarDestination(icon=ft.Icons.CHECK, label="2"),
            ft.NavigationBarDestination(icon=ft.Icons.BAR_CHART, label="3"),
            ft.NavigationBarDestination(icon=ft.Icons.BACKUP, label="4"),
            ft.NavigationBarDestination(icon=ft.Icons.PERSON, label="5"),
        ]
    )
    db = connect(":memory:")
    ui = ActivityTrackerUI(fake_page, db)

    # 1. Switch auth modes
    ui._on_switch_auth_mode("register")
    assert ui.auth_mode == "register"
    assert ui.auth_name_in.visible is True

    ui._on_switch_auth_mode("login")
    assert ui.auth_mode == "login"
    assert ui.auth_name_in.visible is False

    # 2. Registration validation failure
    ui.auth_user_in.value = "ab"  # Too short
    ui.auth_pass_in.value = "123"  # Too short
    ui._on_register()
    assert ui.last_error is True

    # 3. Successful registration
    ui.auth_user_in.value = "athlete_john"
    ui.auth_pass_in.value = "secure2026"
    ui.auth_name_in.value = "John Doe"
    ui._on_register()
    assert ui.current_user is not None
    assert ui.current_user["username"] == "athlete_john"
    assert "John" in ui.last_message

    # 4. View and update profile
    ui.render_tab(4)
    ui.profile_name_in.value = "John Champion"
    ui.profile_age_in.value = "24"
    ui.profile_weight_in.value = "78.0"
    ui.profile_height_in.value = "182.0"
    ui.profile_goals_in.value = "Run 15km weekly and achieve 90% score"
    ui._on_save_profile()
    assert ui.last_error is False
    assert ui.current_user["full_name"] == "John Champion"
    assert ui.current_user["age"] == 24

    # 5. Profile validation error handling
    ui.profile_age_in.value = "invalid_age"
    ui._on_save_profile()
    assert ui.last_error is True

    # 6. Logout workflow
    ui._on_logout()
    assert ui.current_user is None
    assert fake_page.navigation_bar.visible is False

    # 7. Login with bad credentials
    ui.auth_user_in.value = "athlete_john"
    ui.auth_pass_in.value = "wrong_password"
    ui._on_login()
    assert ui.current_user is None
    assert ui.last_error is True

    # 8. Successful login
    ui.auth_pass_in.value = "secure2026"
    ui._on_login()
    assert ui.current_user is not None
    assert ui.current_user["username"] == "athlete_john"


