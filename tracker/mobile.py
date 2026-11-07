"""Flet mobile application UI for Physical Activity Tracker (Option 28)."""

from __future__ import annotations

import os
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

MOBILE_WIDTH = 430
MOBILE_HEIGHT = 900
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BACKUP_PATH = "backups/tracker_backup.json"


def _resolve_app_path(rel_path: str) -> Path:
    """Resolve relative paths against project root when running inside .flet."""
    candidate = Path(rel_path)
    if candidate.is_absolute():
        return candidate
    if ".flet" in str(Path.cwd()):
        return PROJECT_ROOT / candidate
    return candidate


def _make_badge(text: str, bg: str, fg: str) -> ft.Container:
    """Create a rounded pill badge for streak or status metrics."""
    return ft.Container(
        content=ft.Text(text, size=12, weight=ft.FontWeight.BOLD, color=fg),
        bgcolor=bg,
        padding=ft.Padding.symmetric(horizontal=10, vertical=5),
        border_radius=16,
    )


class ActivityTrackerUI:
    """Controller for the 4-tab Flet mobile interface."""

    def __init__(self, page: ft.Page, db: sqlite3.Connection) -> None:
        """Initialize UI controls and bind event handlers."""
        self.page = page
        self.db = db
        self.status_banner = ft.Text(value="", weight=ft.FontWeight.BOLD, size=13)
        self.banner_box = ft.Container(
            content=self.status_banner,
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            border_radius=10,
            visible=False,
        )
        self.body_container = ft.Column(
            expand=True, scroll=ft.ScrollMode.AUTO, spacing=10
        )
        self._init_inputs()

    def _init_inputs(self) -> None:
        """Create input controls used across the mobile tabs."""
        self.title_in = ft.TextField(
            label="Goal Title (e.g. Morning Run)",
            expand=True,
            dense=True,
        )
        self.cat_dd = ft.Dropdown(
            label="Category",
            value=VALID_CATEGORIES[0],
            options=[ft.DropdownOption(key=c, text=c) for c in VALID_CATEGORIES],
            width=165,
            dense=True,
        )
        self.target_in = ft.TextField(
            label="Target (e.g. 5)",
            expand=True,
            dense=True,
        )
        self.unit_in = ft.TextField(
            label="Unit (km, reps)",
            expand=True,
            dense=True,
        )

        self.log_act_dd = ft.Dropdown(
            label="Select Activity", width=350, dense=True
        )
        self.log_date_in = ft.TextField(
            label="Date (YYYY-MM-DD)",
            value=date.today().strftime(DATE_FMT),
            expand=True,
            dense=True,
        )
        self.log_val_in = ft.TextField(
            label="Achieved Value",
            expand=True,
            dense=True,
        )
        self.log_notes_in = ft.TextField(
            label="Notes (optional)",
            expand=True,
            dense=True,
        )
        self.backup_path_in = ft.TextField(
            label="Backup File (.json)",
            value=DEFAULT_BACKUP_PATH,
            expand=True,
            dense=True,
        )

    def notify(self, message: str, is_error: bool = False) -> None:
        """Update status feedback banner and refresh the page."""
        self.status_banner.value = message
        self.status_banner.color = ft.Colors.RED_900 if is_error else ft.Colors.GREEN_900
        self.banner_box.bgcolor = ft.Colors.RED_50 if is_error else ft.Colors.GREEN_50
        self.banner_box.visible = bool(message)
        self.page.update()

    def _make_habit_card(self, item: dict[str, Any]) -> ft.Card:
        """Create a styled mobile card showing an activity goal and its streaks."""
        act_id = item["id"]
        badges = ft.Row(
            [
                _make_badge(
                    f"🔥 {item['current_streak']}d streak",
                    ft.Colors.DEEP_ORANGE_50,
                    ft.Colors.DEEP_ORANGE_900,
                ),
                _make_badge(
                    f"🏆 Best: {item['longest_streak']}d",
                    ft.Colors.AMBER_50,
                    ft.Colors.AMBER_900,
                ),
                _make_badge(
                    f"✅ {item['total_completed']}d total",
                    ft.Colors.TEAL_50,
                    ft.Colors.TEAL_900,
                ),
            ],
            spacing=6,
            wrap=True,
        )
        return ft.Card(
            elevation=1,
            content=ft.Container(
                padding=12,
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Column(
                                    [
                                        ft.Text(
                                            item["title"],
                                            weight=ft.FontWeight.BOLD,
                                            size=15,
                                        ),
                                        ft.Text(
                                            f"{item['category']} • Daily Goal: "
                                            f"{item['target_value']} {item['unit']}",
                                            size=12,
                                            color=ft.Colors.BLUE_GREY_700,
                                        ),
                                    ],
                                    spacing=2,
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.DELETE_OUTLINE,
                                    icon_color=ft.Colors.RED_400,
                                    tooltip="Delete activity",
                                    on_click=lambda _, i=act_id: self._on_delete_activity(i),
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        badges,
                    ],
                    spacing=8,
                ),
            ),
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
            self.notify("Activity goal added successfully!")
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
        best_now = max((a["current_streak"] for a in activities), default=0)
        summary_row = ft.Row(
            [
                _make_badge(
                    f"🎯 {len(activities)} Active Goals",
                    ft.Colors.INDIGO_50,
                    ft.Colors.INDIGO_900,
                ),
                _make_badge(
                    f"🔥 Top Current Streak: {best_now} days",
                    ft.Colors.DEEP_ORANGE_50,
                    ft.Colors.DEEP_ORANGE_900,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
        form_card = ft.Card(
            elevation=1,
            content=ft.Container(
                padding=12,
                content=ft.Column(
                    [
                        ft.Text(
                            "Create New Habit Goal",
                            weight=ft.FontWeight.BOLD,
                            size=15,
                        ),
                        ft.Row([self.title_in]),
                        ft.Row([self.cat_dd, self.target_in], spacing=10),
                        ft.Row(
                            [
                                self.unit_in,
                                ft.FilledButton(
                                    content="Add Goal",
                                    icon=ft.Icons.ADD_TASK,
                                    on_click=self._on_add_activity,
                                ),
                            ],
                            spacing=10,
                        ),
                    ],
                    spacing=8,
                ),
            ),
        )
        cards = [self._make_habit_card(a) for a in activities] or [
            ft.Text("No habits yet. Add your first activity goal above!")
        ]
        return [
            summary_row,
            form_card,
            ft.Text("Your Activity Streaks", size=16, weight=ft.FontWeight.BOLD),
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
                text=f"{a['title']} (goal: {a['target_value']} {a['unit']})",
            )
            for a in activities
        ]
        if activities and not self.log_act_dd.value:
            self.log_act_dd.value = str(activities[0]["id"])

        logs = get_activity_logs(self.db)[:10]
        log_cards = [
            ft.Card(
                elevation=1,
                content=ft.Container(
                    padding=10,
                    content=ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Text(
                                        f"{r['activity_title']} — {r['log_date']}",
                                        weight=ft.FontWeight.BOLD,
                                        size=14,
                                    ),
                                    ft.Text(
                                        f"{r['actual_value']} / {r['target_value']} "
                                        f"{r['unit']}"
                                        + (f" • {r['notes']}" if r["notes"] else ""),
                                        size=12,
                                        color=ft.Colors.BLUE_GREY_700,
                                    ),
                                ],
                                spacing=2,
                            ),
                            _make_badge(
                                "✅ Met" if r["is_completed"] else "⏳ Partial",
                                ft.Colors.GREEN_50
                                if r["is_completed"]
                                else ft.Colors.AMBER_50,
                                ft.Colors.GREEN_900
                                if r["is_completed"]
                                else ft.Colors.AMBER_900,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                ),
            )
            for r in logs
        ]
        return [
            ft.Card(
                elevation=1,
                content=ft.Container(
                    padding=12,
                    content=ft.Column(
                        [
                            ft.Text(
                                "Record Daily Check-In",
                                size=15,
                                weight=ft.FontWeight.BOLD,
                            ),
                            self.log_act_dd,
                            ft.Row([self.log_date_in, self.log_val_in], spacing=10),
                            ft.Row([self.log_notes_in]),
                            ft.FilledButton(
                                content="Save Check-In",
                                icon=ft.Icons.CHECK_CIRCLE_OUTLINE,
                                on_click=self._on_log_progress,
                            ),
                        ],
                        spacing=8,
                    ),
                ),
            ),
            ft.Text("Recent Check-In History", size=16, weight=ft.FontWeight.BOLD),
            *(log_cards or [ft.Text("No check-ins recorded yet.")]),
        ]

    def _build_report_tab(self) -> list[ft.Control]:
        """Build the 7-Day Weekly Analytics Report tab controls."""
        rep = get_weekly_report(self.db)
        day_bars = [
            ft.Row(
                [
                    ft.Text(d["date"], width=90, size=12),
                    ft.ProgressBar(
                        value=(
                            d["completed_count"] / rep["total_activities"]
                            if rep["total_activities"]
                            else 0
                        ),
                        width=160,
                        color=ft.Colors.INDIGO_600,
                        bgcolor=ft.Colors.INDIGO_50,
                    ),
                    ft.Text(
                        f"{d['completed_count']}/{rep['total_activities']} goals",
                        size=12,
                        weight=ft.FontWeight.BOLD,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            )
            for d in rep["daily_breakdown"]
        ]
        act_cards = [
            ft.Card(
                elevation=1,
                content=ft.Container(
                    padding=10,
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Text(
                                        s["title"],
                                        weight=ft.FontWeight.BOLD,
                                        size=14,
                                    ),
                                    _make_badge(
                                        f"{s['completed_days']}/7d ({s['completion_rate']}%)",
                                        ft.Colors.INDIGO_50,
                                        ft.Colors.INDIGO_900,
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            ft.Text(
                                f"7-Day Cumulative Volume: {s['total_value']} {s['unit']}",
                                size=12,
                                color=ft.Colors.BLUE_GREY_700,
                            ),
                        ],
                        spacing=4,
                    ),
                ),
            )
            for s in rep["activity_summaries"]
        ]
        return [
            ft.Card(
                elevation=2,
                content=ft.Container(
                    padding=12,
                    bgcolor=ft.Colors.INDIGO_50,
                    border_radius=12,
                    content=ft.Column(
                        [
                            ft.Text(
                                f"7-Day Report ({rep['start_date']} → {rep['end_date']})",
                                size=12,
                                color=ft.Colors.INDIGO_900,
                            ),
                            ft.Text(
                                f"Overall Completion: {rep['completion_rate']}%",
                                size=19,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.INDIGO_900,
                            ),
                            ft.ProgressBar(
                                value=rep["completion_rate"] / 100.0,
                                color=ft.Colors.INDIGO_700,
                                bgcolor=ft.Colors.WHITE,
                            ),
                            ft.Text(
                                f"Completed {rep['completed_checkins']} of "
                                f"{rep['possible_checkins']} scheduled daily goals",
                                size=12,
                            ),
                        ],
                        spacing=5,
                    ),
                ),
            ),
            ft.Card(
                elevation=1,
                content=ft.Container(
                    padding=12,
                    content=ft.Column(
                        [
                            ft.Text(
                                "Daily Goal Breakdown",
                                weight=ft.FontWeight.BOLD,
                                size=14,
                            ),
                            *day_bars,
                        ],
                        spacing=6,
                    ),
                ),
            ),
            ft.Text("Per-Activity Weekly Volume", size=16, weight=ft.FontWeight.BOLD),
            *(act_cards or [ft.Text("Add activities to view weekly analytics.")]),
        ]

    def _on_export_backup(self, _: Any = None) -> None:
        """Handle exporting database state to JSON."""
        try:
            target = _resolve_app_path(self.backup_path_in.value or "")
            meta = export_backup(self.db, target)
            self.notify(
                f"Exported {meta['activities_count']} goals and "
                f"{meta['logs_count']} logs!"
            )
            self.render_tab(3)
        except TrackerError as exc:
            self.notify(f"Error: {exc}", is_error=True)

    def _on_restore_backup(self, _: Any = None) -> None:
        """Handle restoring database state from JSON."""
        try:
            source = _resolve_app_path(self.backup_path_in.value or "")
            meta = restore_backup(self.db, source)
            self.notify(
                f"Restored {meta['activities_count']} goals and "
                f"{meta['logs_count']} logs!"
            )
            self.render_tab(3)
        except TrackerError as exc:
            self.notify(f"Error: {exc}", is_error=True)

    def _build_backup_tab(self) -> list[ft.Control]:
        """Build the Data Backup & Restore tab controls."""
        history = get_backup_history(self.db)[:8]
        hist_cards = [
            ft.Card(
                elevation=1,
                content=ft.Container(
                    padding=10,
                    content=ft.Row(
                        [
                            _make_badge(
                                h["action"],
                                ft.Colors.INDIGO_50
                                if h["action"] == "EXPORT"
                                else ft.Colors.TEAL_50,
                                ft.Colors.INDIGO_900
                                if h["action"] == "EXPORT"
                                else ft.Colors.TEAL_900,
                            ),
                            ft.Column(
                                [
                                    ft.Text(
                                        Path(h["file_path"]).name,
                                        weight=ft.FontWeight.BOLD,
                                        size=13,
                                    ),
                                    ft.Text(
                                        f"{h['created_at']} • {h['activities_count']} "
                                        f"goals, {h['logs_count']} logs",
                                        size=12,
                                        color=ft.Colors.BLUE_GREY_700,
                                    ),
                                ],
                                spacing=2,
                            ),
                        ],
                        spacing=10,
                    ),
                ),
            )
            for h in history
        ]
        return [
            ft.Card(
                elevation=1,
                content=ft.Container(
                    padding=12,
                    content=ft.Column(
                        [
                            ft.Text(
                                "Offline JSON Backup & Restore",
                                size=15,
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.Text(
                                "Export all habits and streak logs to a portable JSON "
                                "snapshot or restore atomically.",
                                size=12,
                                color=ft.Colors.BLUE_GREY_700,
                            ),
                            ft.Row([self.backup_path_in]),
                            ft.Row(
                                [
                                    ft.FilledButton(
                                        content="Export Backup",
                                        icon=ft.Icons.UPLOAD_FILE,
                                        on_click=self._on_export_backup,
                                    ),
                                    ft.OutlinedButton(
                                        content="Restore Backup",
                                        icon=ft.Icons.RESTORE,
                                        on_click=self._on_restore_backup,
                                    ),
                                ],
                                spacing=10,
                            ),
                        ],
                        spacing=8,
                    ),
                ),
            ),
            ft.Text("Backup Audit History", size=16, weight=ft.FontWeight.BOLD),
            *(hist_cards or [ft.Text("No backup operations performed yet.")]),
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
    """Configure mobile page theme, header, and bottom navigation bar."""
    page.title = "HabitStreak — Physical Activity Tracker"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = ft.Theme(color_scheme_seed=ft.Colors.INDIGO)
    page.bgcolor = ft.Colors.GREY_50
    page.window.width = MOBILE_WIDTH
    page.window.height = MOBILE_HEIGHT
    page.padding = 12

    db_path = _resolve_app_path(DEFAULT_DB_NAME)
    db = connect(db_path)
    controller = ActivityTrackerUI(page, db)
    route_map = {"/0": 0, "/1": 1, "/2": 2, "/3": 3}
    initial_tab = route_map.get(
        page.route, int(os.environ.get("TRACKER_INITIAL_TAB", "0"))
    )

    def _on_route(e: Any) -> None:
        tab_idx = route_map.get(page.route, 0)
        if page.navigation_bar:
            page.navigation_bar.selected_index = tab_idx
        controller.render_tab(tab_idx)

    page.on_route_change = _on_route

    header = ft.Container(
        padding=ft.Padding.symmetric(horizontal=14, vertical=10),
        bgcolor=ft.Colors.INDIGO_700,
        border_radius=12,
        content=ft.Row(
            [
                ft.Icon(
                    ft.Icons.LOCAL_FIRE_DEPARTMENT,
                    color=ft.Colors.ORANGE_300,
                    size=26,
                ),
                ft.Column(
                    [
                        ft.Text(
                            "HabitStreak Tracker",
                            size=18,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.WHITE,
                        ),
                        ft.Text(
                            "Daily Activity Goals • Streaks • Analytics",
                            size=11,
                            color=ft.Colors.INDIGO_100,
                        ),
                    ],
                    spacing=1,
                ),
            ],
            spacing=10,
        ),
    )

    page.navigation_bar = ft.NavigationBar(
        selected_index=initial_tab,
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
    page.add(header, controller.banner_box, controller.body_container)
    controller.render_tab(initial_tab)


if __name__ == "__main__":
    ft.run(main)
