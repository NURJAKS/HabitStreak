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
    """Verify all 4 mobile UI tabs, BottomSheet, Slider, Boosts, and Backup."""
    fake_page = MagicMock(spec=ft.Page)
    db = connect(":memory:")
    ui = ActivityTrackerUI(fake_page, db)

    # Render empty states across all 4 tabs
    for tab_idx in range(4):
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
