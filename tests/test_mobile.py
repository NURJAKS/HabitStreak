"""Unit tests for the Flet mobile UI controller (ActivityTrackerUI)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import flet as ft

from tracker.db import connect
from tracker.mobile import ActivityTrackerUI


def test_mobile_ui_controller_workflow(tmp_path: Path) -> None:
    """Verify all 4 mobile UI tabs and action handlers operate without errors."""
    fake_page = MagicMock(spec=ft.Page)
    db = connect(":memory:")
    ui = ActivityTrackerUI(fake_page, db)

    # Render empty tabs
    for tab_idx in range(4):
        ui.render_tab(tab_idx)
    assert fake_page.update.called

    # Add an activity via UI handler
    ui.title_in.value = "Evening Cycling"
    ui.cat_dd.value = "Cardio"
    ui.target_in.value = "15"
    ui.unit_in.value = "km"
    ui._on_add_activity()
    assert "added" in (ui.status_banner.value or "")

    # Log progress via UI handler
    ui.render_tab(1)
    ui.log_act_dd.value = "1"
    ui.log_date_in.value = "2026-11-07"
    ui.log_val_in.value = "18"
    ui.log_notes_in.value = "Fast ride"
    ui._on_log_progress()
    assert "logged" in (ui.status_banner.value or "")

    # Render Weekly Report tab with active data
    ui.render_tab(2)
    assert len(ui.body_container.controls) > 3

    # Export and Restore Backup via UI handlers
    backup_file = tmp_path / "ui_backup.json"
    ui.backup_path_in.value = str(backup_file)
    ui._on_export_backup()
    assert "Exported" in (ui.status_banner.value or "")

    ui._on_delete_activity(1)
    assert "deleted" in (ui.status_banner.value or "")

    ui._on_restore_backup()
    assert "Restored" in (ui.status_banner.value or "")


def test_mobile_ui_error_handling() -> None:
    """Verify UI handlers catch TrackerError and display red error banners."""
    fake_page = MagicMock(spec=ft.Page)
    db = connect(":memory:")
    ui = ActivityTrackerUI(fake_page, db)

    # Empty activity title triggers error banner
    ui.title_in.value = ""
    ui._on_add_activity()
    assert (ui.status_banner.value or "").startswith("Error:")

    # Logging without selected activity triggers error banner
    ui.log_act_dd.value = None
    ui._on_log_progress()
    assert (ui.status_banner.value or "").startswith("Error:")

    # Deleting non-existent activity triggers error banner
    ui._on_delete_activity(999)
    assert (ui.status_banner.value or "").startswith("Error:")

    # Invalid backup extension triggers error banner
    ui.backup_path_in.value = "invalid.txt"
    ui._on_export_backup()
    assert (ui.status_banner.value or "").startswith("Error:")

    # Missing backup file on restore triggers error banner
    ui.backup_path_in.value = "missing_file.json"
    ui._on_restore_backup()
    assert (ui.status_banner.value or "").startswith("Error:")
