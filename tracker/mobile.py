"""Flet mobile application UI for Physical Activity Tracker (Option 28)."""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

import flet as ft

from tracker.db import DEFAULT_DB_NAME, connect
from tracker.service import (
    DATE_FMT,
    VALID_CATEGORIES,
    TrackerError,
    add_activity,
    delete_activity,
    export_backup,
    get_activity_logs,
    get_backup_history,
    get_weekly_report,
    list_activities,
    log_progress,
    restore_backup,
)

MOBILE_WIDTH = 420
MOBILE_HEIGHT = 860
DEFAULT_BACKUP_PATH = "backups/tracker_backup.json"


class ActivityTrackerUI:
    """Controller for the 4-tab Flet mobile interface."""

    def __init__(self, page: ft.Page, db: sqlite3.Connection) -> None:
        """Initialize UI controls and bind event handlers."""
        self.page = page
        self.db = db
        self.status_banner = ft.Text(value="", weight=ft.FontWeight.BOLD)
        self.body_container = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO)
        self._init_inputs()

    def _init_inputs(self) -> None:
        """Create input controls used across the mobile tabs."""
        self.title_in = ft.TextField(label="Goal Title (e.g. Morning Run)", expand=True)
        self.cat_dd = ft.Dropdown(
            label="Category",
            value=VALID_CATEGORIES[0],
            options=[ft.DropdownOption(key=c, text=c) for c in VALID_CATEGORIES],
            width=160,
        )
        self.target_in = ft.TextField(label="Daily Target (e.g. 5)", width=150)
        self.unit_in = ft.TextField(label="Unit (km, mins, reps)", width=160)

        self.log_act_dd = ft.Dropdown(label="Select Activity", width=360)
        self.log_date_in = ft.TextField(
            label="Date (YYYY-MM-DD)",
            value=date.today().strftime(DATE_FMT),
            width=180,
        )
        self.log_val_in = ft.TextField(label="Achieved Value", width=170)
        self.log_notes_in = ft.TextField(label="Notes (optional)")
        self.backup_path_in = ft.TextField(
            label="Backup File (.json)", value=DEFAULT_BACKUP_PATH
        )

    def notify(self, message: str, is_error: bool = False) -> None:
        """Update status feedback banner and refresh the page."""
        self.status_banner.value = message
        self.status_banner.color = ft.Colors.RED_700 if is_error else ft.Colors.GREEN_700
        self.page.update()

    def _make_habit_card(self, item: dict[str, Any]) -> ft.Card:
        """Create a mobile card showing an activity goal and its streaks."""
        act_id = item["id"]
        streak_badge = (
            f"🔥 Current: {item['current_streak']}d  |  "
            f"🏆 Best: {item['longest_streak']}d  |  "
            f"✅ Total: {item['total_completed']}d"
        )
        return ft.Card(
            content=ft.Container(
                padding=12,
                content=ft.Column([
                    ft.Row(
                        [
                            ft.Text(
                                f"{item['title']} ({item['category']})",
                                weight=ft.FontWeight.BOLD,
                                size=16,
                            ),
                            ft.TextButton(
                                content="Delete",
                                on_click=lambda _, i=act_id: self._on_delete_activity(i),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Text(f"Daily Target: {item['target_value']} {item['unit']}"),
                    ft.Text(streak_badge, color=ft.Colors.DEEP_ORANGE_700),
                ]),
            )
        )

    def _on_add_activity(self, _: Any = None) -> None:
        """Handle creating a new physical activity habit."""
        try:
            add_activity(
                self.db,
                self.title_in.value or "",
                self.cat_dd.value or VALID_CATEGORIES[0],
                float(self.target_in.value or 0),
                self.unit_in.value or "",
            )
            self.title_in.value = ""
            self.target_in.value = ""
            self.unit_in.value = ""
            self.notify("Activity goal added!")
            self.render_tab(0)
        except (TrackerError, ValueError) as exc:
            self.notify(f"Error: {exc}", is_error=True)

    def _on_delete_activity(self, activity_id: int) -> None:
        """Handle deleting an activity habit."""
        try:
            delete_activity(self.db, activity_id)
            self.notify("Activity deleted.")
            self.render_tab(0)
        except TrackerError as exc:
            self.notify(f"Error: {exc}", is_error=True)

    def _build_habits_tab(self) -> list[ft.Control]:
        """Build the Habits & Streaks tab controls."""
        activities = list_activities(self.db)
        cards = [self._make_habit_card(a) for a in activities]
        if not cards:
            cards = [ft.Text("No habits yet. Add your first activity goal above!")]
        return [
            ft.Text("New Activity Goal", size=18, weight=ft.FontWeight.BOLD),
            self.title_in,
            ft.Row([self.cat_dd, self.target_in]),
            ft.Row([
                self.unit_in,
                ft.FilledButton(content="Add Goal", on_click=self._on_add_activity),
            ]),
            ft.Divider(),
            ft.Text("Active Habits & Streaks", size=18, weight=ft.FontWeight.BOLD),
            *cards,
        ]

    def _on_log_progress(self, _: Any = None) -> None:
        """Handle recording daily workout progress."""
        try:
            if not self.log_act_dd.value:
                raise TrackerError("Please select an activity first")
            log_progress(
                self.db,
                int(self.log_act_dd.value),
                self.log_date_in.value or "",
                float(self.log_val_in.value or -1),
                self.log_notes_in.value or "",
            )
            self.log_val_in.value = ""
            self.log_notes_in.value = ""
            self.notify("Daily progress logged!")
            self.render_tab(1)
        except (TrackerError, ValueError) as exc:
            self.notify(f"Error: {exc}", is_error=True)

    def _build_checkin_tab(self) -> list[ft.Control]:
        """Build the Daily Check-In tab controls."""
        activities = list_activities(self.db)
        self.log_act_dd.options = [
            ft.DropdownOption(
                key=str(a["id"]),
                text=f"{a['title']} (target: {a['target_value']} {a['unit']})",
            )
            for a in activities
        ]
        if activities and not self.log_act_dd.value:
            self.log_act_dd.value = str(activities[0]["id"])

        logs = get_activity_logs(self.db)[:12]
        log_rows = [
            ft.Card(
                content=ft.Container(
                    padding=10,
                    content=ft.Text(
                        f"{'✅' if r['is_completed'] else '⏳'} {r['log_date']} | "
                        f"{r['activity_title']}: {r['actual_value']}/{r['target_value']} "
                        f"{r['unit']} {('(' + r['notes'] + ')') if r['notes'] else ''}"
                    ),
                )
            )
            for r in logs
        ]
        return [
            ft.Text("Daily Activity Check-In", size=18, weight=ft.FontWeight.BOLD),
            self.log_act_dd,
            ft.Row([self.log_date_in, self.log_val_in]),
            self.log_notes_in,
            ft.FilledButton(content="Save Check-In", on_click=self._on_log_progress),
            ft.Divider(),
            ft.Text("Recent Check-In History", size=16, weight=ft.FontWeight.BOLD),
            *(log_rows or [ft.Text("No check-ins recorded yet.")]),
        ]

    def _build_report_tab(self) -> list[ft.Control]:
        """Build the 7-Day Weekly Analytics Report tab controls."""
        rep = get_weekly_report(self.db)
        day_bars = [
            ft.Row([
                ft.Text(d["date"], width=100),
                ft.ProgressBar(
                    value=(
                        d["completed_count"] / rep["total_activities"]
                        if rep["total_activities"]
                        else 0
                    ),
                    width=160,
                ),
                ft.Text(f"{d['completed_count']}/{rep['total_activities']} goals"),
            ])
            for d in rep["daily_breakdown"]
        ]
        act_cards = [
            ft.Card(
                content=ft.Container(
                    padding=10,
                    content=ft.Text(
                        f"📊 {s['title']}: {s['completed_days']}/7 days "
                        f"({s['completion_rate']}%) — Total: {s['total_value']} {s['unit']}"
                    ),
                )
            )
            for s in rep["activity_summaries"]
        ]
        return [
            ft.Text("7-Day Weekly Report", size=18, weight=ft.FontWeight.BOLD),
            ft.Text(f"Period: {rep['start_date']} to {rep['end_date']}"),
            ft.Card(
                content=ft.Container(
                    padding=12,
                    content=ft.Column([
                        ft.Text(
                            f"Overall Completion Rate: {rep['completion_rate']}%",
                            size=16,
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.Text(
                            f"Completed Check-ins: {rep['completed_checkins']} / "
                            f"{rep['possible_checkins']}"
                        ),
                    ]),
                )
            ),
            ft.Text("Daily Goal Breakdown", weight=ft.FontWeight.BOLD),
            *day_bars,
            ft.Divider(),
            ft.Text("Per-Activity Weekly Volume", weight=ft.FontWeight.BOLD),
            *(act_cards or [ft.Text("Add activities to view weekly analytics.")]),
        ]

    def _on_export_backup(self, _: Any = None) -> None:
        """Handle exporting database state to JSON."""
        try:
            meta = export_backup(self.db, self.backup_path_in.value or "")
            self.notify(
                f"Exported {meta['activities_count']} goals and "
                f"{meta['logs_count']} logs to {meta['file_path']}"
            )
            self.render_tab(3)
        except TrackerError as exc:
            self.notify(f"Error: {exc}", is_error=True)

    def _on_restore_backup(self, _: Any = None) -> None:
        """Handle restoring database state from JSON."""
        try:
            meta = restore_backup(self.db, self.backup_path_in.value or "")
            self.notify(
                f"Restored {meta['activities_count']} goals and "
                f"{meta['logs_count']} logs from {meta['file_path']}"
            )
            self.render_tab(3)
        except TrackerError as exc:
            self.notify(f"Error: {exc}", is_error=True)

    def _build_backup_tab(self) -> list[ft.Control]:
        """Build the Data Backup & Restore tab controls."""
        history = get_backup_history(self.db)[:8]
        hist_rows = [
            ft.Text(
                f"[{h['action']}] {h['created_at']} — {h['file_path']} "
                f"({h['activities_count']} goals, {h['logs_count']} logs)"
            )
            for h in history
        ]
        return [
            ft.Text("Data Backup & Restore", size=18, weight=ft.FontWeight.BOLD),
            ft.Text("Export or restore your habit streaks and logs as JSON."),
            self.backup_path_in,
            ft.Row([
                ft.FilledButton(content="Export Backup", on_click=self._on_export_backup),
                ft.OutlinedButton(
                    content="Restore Backup", on_click=self._on_restore_backup
                ),
            ]),
            ft.Divider(),
            ft.Text("Backup Audit Log", weight=ft.FontWeight.BOLD),
            *(hist_rows or [ft.Text("No backup operations performed yet.")]),
        ]

    def render_tab(self, index: int) -> None:
        """Render the selected tab view inside the mobile container."""
        builders = {
            0: self._build_habits_tab,
            1: self._build_checkin_tab,
            2: self._build_report_tab,
            3: self._build_backup_tab,
        }
        self.body_container.controls = builders.get(index, self._build_habits_tab)()
        self.page.update()


def main(page: ft.Page) -> None:
    """Configure mobile page dimensions and launch ActivityTrackerUI."""
    page.title = "HabitStreak — Activity Tracker"
    page.window.width = MOBILE_WIDTH
    page.window.height = MOBILE_HEIGHT
    page.padding = 16

    db_path = Path(DEFAULT_DB_NAME)
    db = connect(db_path)
    controller = ActivityTrackerUI(page, db)

    page.navigation_bar = ft.NavigationBar(
        selected_index=0,
        on_change=lambda e: controller.render_tab(int(e.control.selected_index or 0)),
        destinations=[
            ft.NavigationBarDestination(
                icon=ft.Icons.LOCAL_FIRE_DEPARTMENT, label="Habits"
            ),
            ft.NavigationBarDestination(icon=ft.Icons.CHECK_CIRCLE, label="Check-In"),
            ft.NavigationBarDestination(icon=ft.Icons.BAR_CHART, label="Weekly"),
            ft.NavigationBarDestination(icon=ft.Icons.BACKUP, label="Backup"),
        ],
    )
    page.add(
        ft.Text("HabitStreak Tracker", size=22, weight=ft.FontWeight.BOLD),
        controller.status_banner,
        controller.body_container,
    )
    controller.render_tab(0)


if __name__ == "__main__":
    ft.run(main)
