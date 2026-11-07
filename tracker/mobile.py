"""Duolingo-inspired Flet mobile UI for Physical Activity Tracker (Option 28)."""

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

# Duolingo "Flat Design 2.0" Color Palette
DUO_BG = "#F7F7F7"
DUO_WHITE = "#FFFFFF"
DUO_GREEN = "#58CC02"
DUO_GREEN_LIGHT = "#E5F8D3"
DUO_ORANGE = "#FF9600"
DUO_ORANGE_LIGHT = "#FFF0D6"
DUO_BLUE = "#1CB0F6"
DUO_BLUE_LIGHT = "#DDF4FF"
DUO_PURPLE = "#CE82FF"
DUO_PURPLE_LIGHT = "#F3E5FF"
DUO_RED = "#FF4B4B"
DUO_RED_LIGHT = "#FFDFE0"
DUO_GOLD = "#FFC800"
DUO_GOLD_LIGHT = "#FFF5D6"
DUO_GREY = "#E5E5E5"
DUO_GREY_TEXT = "#777777"
DUO_DARK_TEXT = "#3C3C3C"

CATEGORY_STYLE: dict[str, tuple[Any, str, str]] = {
    "Cardio": (ft.Icons.DIRECTIONS_RUN, DUO_BLUE, DUO_BLUE_LIGHT),
    "Steps": (ft.Icons.DIRECTIONS_WALK, DUO_GREEN, DUO_GREEN_LIGHT),
    "Strength": (ft.Icons.FITNESS_CENTER, DUO_RED, DUO_RED_LIGHT),
    "Hydration": (ft.Icons.WATER_DROP, DUO_BLUE, DUO_BLUE_LIGHT),
    "Flexibility": (ft.Icons.SELF_IMPROVEMENT, DUO_PURPLE, DUO_PURPLE_LIGHT),
    "Sport": (ft.Icons.EMOJI_EVENTS, DUO_GOLD, DUO_GOLD_LIGHT),
}


def _resolve_app_path(rel_path: str) -> Path:
    """Resolve relative paths against project root when running inside .flet."""
    candidate = Path(rel_path)
    if candidate.is_absolute():
        return candidate
    if ".flet" in str(Path.cwd()):
        return PROJECT_ROOT / candidate
    return candidate


def _duo_card(content: ft.Control, padding: int = 18, bg: str = DUO_WHITE) -> ft.Container:
    """Create a bubble-style Duolingo card with 24px border radius and soft shadow."""
    return ft.Container(
        border_radius=24,
        bgcolor=bg,
        padding=padding,
        shadow=ft.BoxShadow(
            spread_radius=1,
            blur_radius=10,
            color=DUO_GREY,
            offset=ft.Offset(0, 4),
        ),
        content=content,
    )


def _duo_button(
    label: str,
    on_click: Any,
    icon: Any = None,
    bg: str = DUO_GREEN,
    fg: str = DUO_WHITE,
    expand: bool = False,
) -> ft.FilledButton:
    """Create a tactile Duolingo-style rounded button."""
    return ft.FilledButton(
        content=label,
        icon=icon,
        bgcolor=bg,
        color=fg,
        height=48,
        expand=expand,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=20),
            elevation=3,
        ),
        on_click=on_click,
    )


def _empty_state(icon: Any, title: str, subtitle: str) -> ft.Container:
    """Render a friendly gamified empty state card."""
    return _duo_card(
        padding=28,
        content=ft.Column(
            [
                ft.Container(
                    content=ft.Icon(icon, size=56, color=DUO_BLUE),
                    bgcolor=DUO_BLUE_LIGHT,
                    padding=20,
                    border_radius=32,
                ),
                ft.Text(
                    title,
                    size=18,
                    weight=ft.FontWeight.BOLD,
                    color=DUO_DARK_TEXT,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Text(
                    subtitle,
                    size=13,
                    color=DUO_GREY_TEXT,
                    text_align=ft.TextAlign.CENTER,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
        ),
    )


class ActivityTrackerUI:
    """Controller for the 4-tab Duolingo-style Flet mobile interface."""

    def __init__(self, page: ft.Page, db: sqlite3.Connection) -> None:
        """Initialize UI state, modal sheets, and interactive controls."""
        self.page = page
        self.db = db
        self.last_message = ""
        self.last_error = False
        self.body_container = ft.Column(
            expand=True, scroll=ft.ScrollMode.AUTO, spacing=14
        )
        self._init_inputs()
        self.add_sheet = self._build_add_bottom_sheet()
        self.fab = ft.FloatingActionButton(
            icon=ft.Icons.ADD,
            bgcolor=DUO_GREEN,
            foreground_color=DUO_WHITE,
            shape=ft.CircleBorder(),
            tooltip="Add New Habit Goal",
            on_click=self.open_add_sheet,
        )

    def _init_inputs(self) -> None:
        """Create rounded input controls for BottomSheet, Check-In, and Backup."""
        rounded = ft.OutlineInputBorder(border_radius=20)
        self.title_in = ft.TextField(
            label="Habit Name (e.g. Morning Run)", border=rounded
        )
        self.cat_dd = ft.Dropdown(
            label="Category",
            value=VALID_CATEGORIES[0],
            options=[ft.DropdownOption(key=c, text=c) for c in VALID_CATEGORIES],
            width=340,
        )
        self.target_in = ft.TextField(
            label="Daily Target (e.g. 5.0)", border=rounded
        )
        self.unit_in = ft.TextField(
            label="Unit (km, steps, reps, mins, L)", border=rounded
        )

        self.log_act_dd = ft.Dropdown(
            label="Choose Habit to Log",
            width=350,
            on_select=self._on_activity_selected,
        )
        self.log_date_in = ft.TextField(
            label="Date (YYYY-MM-DD)",
            value=date.today().strftime(DATE_FMT),
            border=rounded,
        )
        self.log_val_in = ft.TextField(
            label="Value", value="0", border=rounded, visible=False
        )
        self.log_notes_in = ft.TextField(
            label="Workout Note (optional)", border=rounded
        )
        self.ring_bar = ft.ProgressRing(
            value=0.0,
            width=130,
            height=130,
            stroke_width=14,
            color=DUO_GREEN,
            bgcolor=DUO_GREY,
        )
        self.ring_label = ft.Text(
            "0%", size=22, weight=ft.FontWeight.BOLD, color=DUO_DARK_TEXT
        )
        self.ring_sub = ft.Text("0 / 0", size=13, color=DUO_GREY_TEXT)
        self.val_slider = ft.Slider(
            min=0,
            max=100,
            value=0,
            active_color=DUO_GREEN,
            inactive_color=DUO_GREY,
            thumb_color=DUO_GREEN,
            on_change=self._on_slider_change,
        )
        self.backup_path_in = ft.TextField(
            label="Backup File (.json)",
            value=DEFAULT_BACKUP_PATH,
            border=rounded,
        )

    def notify(self, message: str, is_error: bool = False) -> None:
        """Display a transient SnackBar popup at the bottom of the screen."""
        self.last_message = message
        self.last_error = is_error
        snack = ft.SnackBar(
            content=ft.Text(
                message, color=DUO_WHITE, weight=ft.FontWeight.BOLD, size=14
            ),
            bgcolor=DUO_RED if is_error else DUO_GREEN,
            behavior=ft.SnackBarBehavior.FLOATING,
            shape=ft.RoundedRectangleBorder(radius=18),
        )
        self.page.show_dialog(snack)
        self.page.update()

    def _build_add_bottom_sheet(self) -> ft.BottomSheet:
        """Build the slide-up BottomSheet modal for creating a new habit."""
        return ft.BottomSheet(
            bgcolor=DUO_WHITE,
            show_drag_handle=True,
            shape=ft.RoundedRectangleBorder(radius=24),
            content=ft.Container(
                padding=22,
                content=ft.Column(
                    [
                        ft.Text(
                            "New Daily Habit Goal",
                            size=20,
                            weight=ft.FontWeight.BOLD,
                            color=DUO_DARK_TEXT,
                        ),
                        self.title_in,
                        self.cat_dd,
                        self.target_in,
                        self.unit_in,
                        ft.Row(
                            [
                                _duo_button(
                                    "CREATE HABIT",
                                    on_click=self._on_add_activity,
                                    icon=ft.Icons.CHECK_CIRCLE,
                                    bg=DUO_GREEN,
                                    expand=True,
                                )
                            ]
                        ),
                    ],
                    tight=True,
                    spacing=12,
                ),
            ),
        )

    def open_add_sheet(self, _: Any = None) -> None:
        """Open the BottomSheet form to add a new habit goal."""
        self.page.show_dialog(self.add_sheet)

    def _make_streak_badge(self, streak: int) -> ft.Container:
        """Build a vibrant orange streak badge when active, or grey when 0."""
        active = streak > 0
        bg_color = DUO_ORANGE if active else DUO_GREY
        fg_color = DUO_WHITE if active else DUO_GREY_TEXT
        return ft.Container(
            bgcolor=bg_color,
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            border_radius=18,
            content=ft.Row(
                [
                    ft.Icon(
                        ft.Icons.LOCAL_FIRE_DEPARTMENT, color=fg_color, size=18
                    ),
                    ft.Text(
                        str(streak),
                        weight=ft.FontWeight.BOLD,
                        size=15,
                        color=fg_color,
                    ),
                ],
                spacing=4,
                tight=True,
            ),
        )

    def _make_habit_card(self, item: dict[str, Any]) -> ft.Container:
        """Create a Duolingo-style gamified habit card with icon, bar, and streak."""
        act_id = item["id"]
        icon_data, icon_fg, icon_bg = CATEGORY_STYLE.get(
            item["category"], (ft.Icons.STAR, DUO_BLUE, DUO_BLUE_LIGHT)
        )
        progress_val = float(item.get("today_progress", 0.0))
        today_val = float(item.get("today_value", 0.0))
        bar_color = DUO_GREEN if progress_val >= 1.0 else DUO_BLUE

        return _duo_card(
            padding=16,
            content=ft.Row(
                [
                    ft.Container(
                        content=ft.Icon(icon_data, color=icon_fg, size=28),
                        bgcolor=icon_bg,
                        padding=14,
                        border_radius=20,
                    ),
                    ft.Column(
                        [
                            ft.Text(
                                item["title"],
                                weight=ft.FontWeight.BOLD,
                                size=17,
                                color=DUO_DARK_TEXT,
                            ),
                            ft.ProgressBar(
                                value=progress_val,
                                color=bar_color,
                                bgcolor=DUO_GREY,
                                bar_height=10,
                                border_radius=8,
                            ),
                            ft.Text(
                                f"Today: {today_val:g} / {item['target_value']:g} "
                                f"{item['unit']}  •  Best: {item['longest_streak']}d",
                                size=12,
                                color=DUO_GREY_TEXT,
                            ),
                        ],
                        expand=True,
                        spacing=6,
                    ),
                    self._make_streak_badge(int(item["current_streak"])),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        icon_color=DUO_GREY_TEXT,
                        icon_size=20,
                        tooltip="Delete habit",
                        on_click=lambda _, i=act_id: self._on_delete_activity(i),
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    def _on_add_activity(self, _: Any = None) -> None:
        """Handle creating a new physical activity habit from BottomSheet."""
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
            self.add_sheet.open = False
            self.notify("Awesome! New habit goal created!")
            self.render_tab(0)
        except (TrackerError, ValueError) as exc:
            self.notify(f"Error: {exc}", is_error=True)

    def _on_delete_activity(self, activity_id: int) -> None:
        """Handle deleting an activity habit."""
        try:
            delete_activity(self.db, activity_id)
            self.notify("Habit deleted.")
            self.render_tab(0)
        except TrackerError as exc:
            self.notify(f"Error: {exc}", is_error=True)

    def _build_habits_tab(self) -> list[ft.Control]:
        """Build the de-cluttered Duolingo Habits & Streaks home screen."""
        activities = list_activities(self.db)
        best_now = max((a["current_streak"] for a in activities), default=0)
        completed_today = sum(
            1 for a in activities if float(a.get("today_progress", 0.0)) >= 1.0
        )

        kpi_bar = _duo_card(
            padding=14,
            content=ft.Row(
                [
                    ft.Row(
                        [
                            ft.Icon(
                                ft.Icons.LOCAL_FIRE_DEPARTMENT,
                                color=DUO_ORANGE,
                                size=26,
                            ),
                            ft.Column(
                                [
                                    ft.Text(
                                        f"{best_now} Day Streak",
                                        weight=ft.FontWeight.BOLD,
                                        size=15,
                                        color=DUO_DARK_TEXT,
                                    ),
                                    ft.Text(
                                        "Top active chain",
                                        size=11,
                                        color=DUO_GREY_TEXT,
                                    ),
                                ],
                                spacing=1,
                            ),
                        ],
                        spacing=8,
                    ),
                    ft.Row(
                        [
                            ft.Icon(
                                ft.Icons.CHECK_CIRCLE, color=DUO_GREEN, size=26
                            ),
                            ft.Column(
                                [
                                    ft.Text(
                                        f"{completed_today} / {len(activities)} Done",
                                        weight=ft.FontWeight.BOLD,
                                        size=15,
                                        color=DUO_DARK_TEXT,
                                    ),
                                    ft.Text(
                                        "Today's goals",
                                        size=11,
                                        color=DUO_GREY_TEXT,
                                    ),
                                ],
                                spacing=1,
                            ),
                        ],
                        spacing=8,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_AROUND,
            ),
        )

        if not activities:
            return [
                kpi_bar,
                _empty_state(
                    ft.Icons.ROCKET_LAUNCH,
                    "Time to build your first healthy habit!",
                    "Tap the green + button in the bottom right corner to start.",
                ),
            ]
        return [
            kpi_bar,
            ft.Text(
                "Today's Habits",
                size=18,
                weight=ft.FontWeight.BOLD,
                color=DUO_DARK_TEXT,
            ),
            *[self._make_habit_card(a) for a in activities],
        ]

    def _sync_checkin_dial(self, activities: list[dict[str, Any]]) -> None:
        """Synchronize the ProgressRing and Slider with the selected activity."""
        if not activities:
            return
        selected_id = int(self.log_act_dd.value or activities[0]["id"])
        act = next((a for a in activities if a["id"] == selected_id), activities[0])
        target = float(act["target_value"])
        current = float(self.log_val_in.value or act.get("today_value", 0.0))
        ratio = min(1.0, current / target) if target > 0 else 0.0

        self.val_slider.max = max(target * 1.5, 10.0)
        self.val_slider.value = min(current, self.val_slider.max)
        self.ring_bar.value = ratio
        self.ring_bar.color = DUO_GREEN if ratio >= 1.0 else DUO_BLUE
        self.ring_label.value = f"{int(ratio * 100)}%"
        self.ring_sub.value = f"{current:g} / {target:g} {act['unit']}"

    def _on_activity_selected(self, _: Any = None) -> None:
        """Reset dial to selected habit's current progress when dropdown changes."""
        activities = list_activities(self.db)
        if not activities or not self.log_act_dd.value:
            return
        selected_id = int(self.log_act_dd.value)
        act = next((a for a in activities if a["id"] == selected_id), activities[0])
        self.log_val_in.value = str(act.get("today_value", 0.0))
        self._sync_checkin_dial(activities)
        self.page.update()

    def _on_slider_change(self, e: Any) -> None:
        """Update ProgressRing live as the user drags the Slider."""
        val = round(float(e.control.value or 0.0), 1)
        self.log_val_in.value = str(val)
        self._sync_checkin_dial(list_activities(self.db))
        self.page.update()

    def _add_quick_boost(self, fraction: float) -> None:
        """Increment or complete the progress dial via tactile boost buttons."""
        activities = list_activities(self.db)
        if not activities or not self.log_act_dd.value:
            return
        selected_id = int(self.log_act_dd.value)
        act = next((a for a in activities if a["id"] == selected_id), activities[0])
        target = float(act["target_value"])
        if fraction >= 1.0:
            new_val = target
        else:
            curr = float(self.log_val_in.value or 0.0)
            new_val = round(curr + target * fraction, 1)
        self.log_val_in.value = str(new_val)
        self._sync_checkin_dial(activities)
        self.page.update()

    def _on_log_progress(self, _: Any = None) -> None:
        """Handle saving the daily check-in."""
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
            self.log_notes_in.value = ""
            self.notify("Check-in saved! Keep your streak alive!")
            self.render_tab(1)
        except (TrackerError, ValueError) as exc:
            self.notify(f"Error: {exc}", is_error=True)

    def _build_checkin_tab(self) -> list[ft.Control]:
        """Build the interactive Duolingo Check-In tab with ProgressRing and Slider."""
        activities = list_activities(self.db)
        if not activities:
            return [
                _empty_state(
                    ft.Icons.CHECK_CIRCLE_OUTLINE,
                    "No habits to check in yet!",
                    "Go to the Habits tab and tap + to create your first goal.",
                )
            ]
        self.log_act_dd.options = [
            ft.DropdownOption(
                key=str(a["id"]),
                text=f"{a['title']} ({a['target_value']:g} {a['unit']})",
            )
            for a in activities
        ]
        if not self.log_act_dd.value or not any(
            str(a["id"]) == self.log_act_dd.value for a in activities
        ):
            self.log_act_dd.value = str(activities[0]["id"])
            self.log_val_in.value = str(activities[0].get("today_value", 0.0))

        self._sync_checkin_dial(activities)

        ring_stack = ft.Stack(
            [
                self.ring_bar,
                ft.Container(
                    width=130,
                    height=130,
                    alignment=ft.Alignment(0, 0),
                    content=ft.Column(
                        [self.ring_label, self.ring_sub],
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=2,
                    ),
                ),
            ],
            width=130,
            height=130,
        )

        boost_row = ft.Row(
            [
                _duo_button(
                    "+25%",
                    on_click=lambda _: self._add_quick_boost(0.25),
                    bg=DUO_BLUE,
                    expand=True,
                ),
                _duo_button(
                    "+50%",
                    on_click=lambda _: self._add_quick_boost(0.50),
                    bg=DUO_BLUE,
                    expand=True,
                ),
                _duo_button(
                    "100% Goal",
                    on_click=lambda _: self._add_quick_boost(1.0),
                    bg=DUO_ORANGE,
                    expand=True,
                ),
            ],
            spacing=8,
        )

        logs = get_activity_logs(self.db)[:6]
        log_cards = [
            _duo_card(
                padding=12,
                content=ft.Row(
                    [
                        ft.Icon(
                            ft.Icons.CHECK_CIRCLE
                            if r["is_completed"]
                            else ft.Icons.TIMELAPSE,
                            color=DUO_GREEN if r["is_completed"] else DUO_ORANGE,
                            size=24,
                        ),
                        ft.Column(
                            [
                                ft.Text(
                                    f"{r['activity_title']} • {r['log_date']}",
                                    weight=ft.FontWeight.BOLD,
                                    size=14,
                                    color=DUO_DARK_TEXT,
                                ),
                                ft.Text(
                                    f"{r['actual_value']:g} / {r['target_value']:g} "
                                    f"{r['unit']}"
                                    + (f" — {r['notes']}" if r["notes"] else ""),
                                    size=12,
                                    color=DUO_GREY_TEXT,
                                ),
                            ],
                            expand=True,
                            spacing=2,
                        ),
                    ],
                    spacing=10,
                ),
            )
            for r in logs
        ]

        return [
            _duo_card(
                padding=18,
                content=ft.Column(
                    [
                        self.log_act_dd,
                        ft.Container(
                            alignment=ft.Alignment(0, 0),
                            padding=6,
                            content=ring_stack,
                        ),
                        self.val_slider,
                        boost_row,
                        self.log_notes_in,
                        ft.Row(
                            [
                                _duo_button(
                                    "COMPLETE CHECK-IN",
                                    on_click=self._on_log_progress,
                                    icon=ft.Icons.CHECK_CIRCLE,
                                    bg=DUO_GREEN,
                                    expand=True,
                                )
                            ]
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=10,
                ),
            ),
            ft.Text(
                "Recent Check-Ins",
                size=17,
                weight=ft.FontWeight.BOLD,
                color=DUO_DARK_TEXT,
            ),
            *log_cards,
        ]

    def _build_report_tab(self) -> list[ft.Control]:
        """Build the Duolingo-style 7-Day Weekly Analytics Report tab."""
        rep = get_weekly_report(self.db)
        if rep["total_activities"] == 0:
            return [
                _empty_state(
                    ft.Icons.BAR_CHART,
                    "No weekly stats yet!",
                    "Create a habit and log your daily workouts to unlock analytics.",
                )
            ]
        day_bars = [
            ft.Row(
                [
                    ft.Text(
                        d["date"][5:],
                        width=55,
                        size=13,
                        weight=ft.FontWeight.BOLD,
                        color=DUO_DARK_TEXT,
                    ),
                    ft.ProgressBar(
                        value=(
                            d["completed_count"] / rep["total_activities"]
                            if rep["total_activities"]
                            else 0
                        ),
                        expand=True,
                        bar_height=10,
                        border_radius=8,
                        color=DUO_GREEN,
                        bgcolor=DUO_GREY,
                    ),
                    ft.Text(
                        f"{d['completed_count']}/{rep['total_activities']}",
                        size=13,
                        weight=ft.FontWeight.BOLD,
                        color=DUO_DARK_TEXT,
                    ),
                ],
                spacing=10,
            )
            for d in rep["daily_breakdown"]
        ]
        act_cards = [
            _duo_card(
                padding=14,
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text(
                                    s["title"],
                                    weight=ft.FontWeight.BOLD,
                                    size=15,
                                    color=DUO_DARK_TEXT,
                                ),
                                ft.Container(
                                    bgcolor=DUO_GREEN_LIGHT,
                                    padding=ft.Padding.symmetric(
                                        horizontal=10, vertical=4
                                    ),
                                    border_radius=14,
                                    content=ft.Text(
                                        f"{s['completed_days']}/7d ({s['completion_rate']}%)",
                                        size=12,
                                        weight=ft.FontWeight.BOLD,
                                        color=DUO_GREEN,
                                    ),
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        ft.ProgressBar(
                            value=s["completion_rate"] / 100.0,
                            color=DUO_GREEN,
                            bgcolor=DUO_GREY,
                            bar_height=8,
                            border_radius=6,
                        ),
                        ft.Text(
                            f"Weekly Volume: {s['total_value']:g} {s['unit']}",
                            size=12,
                            color=DUO_GREY_TEXT,
                        ),
                    ],
                    spacing=6,
                ),
            )
            for s in rep["activity_summaries"]
        ]
        return [
            _duo_card(
                padding=18,
                bg=DUO_GREEN_LIGHT,
                content=ft.Column(
                    [
                        ft.Text(
                            f"7-Day League Report ({rep['start_date']} → {rep['end_date']})",
                            size=12,
                            weight=ft.FontWeight.BOLD,
                            color=DUO_DARK_TEXT,
                        ),
                        ft.Text(
                            f"Weekly Score: {rep['completion_rate']}%",
                            size=22,
                            weight=ft.FontWeight.BOLD,
                            color=DUO_DARK_TEXT,
                        ),
                        ft.ProgressBar(
                            value=rep["completion_rate"] / 100.0,
                            color=DUO_GREEN,
                            bgcolor=DUO_WHITE,
                            bar_height=12,
                            border_radius=8,
                        ),
                        ft.Text(
                            f"Completed {rep['completed_checkins']} of "
                            f"{rep['possible_checkins']} daily goals this week!",
                            size=13,
                            color=DUO_DARK_TEXT,
                        ),
                    ],
                    spacing=8,
                ),
            ),
            _duo_card(
                padding=16,
                content=ft.Column(
                    [
                        ft.Text(
                            "7-Day Consistency Chain",
                            size=16,
                            weight=ft.FontWeight.BOLD,
                            color=DUO_DARK_TEXT,
                        ),
                        *day_bars,
                    ],
                    spacing=10,
                ),
            ),
            ft.Text(
                "Habit Volume Breakdown",
                size=17,
                weight=ft.FontWeight.BOLD,
                color=DUO_DARK_TEXT,
            ),
            *act_cards,
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
        """Build the Duolingo-styled Data Backup & Restore tab."""
        history = get_backup_history(self.db)[:8]
        hist_cards = [
            _duo_card(
                padding=14,
                content=ft.Row(
                    [
                        ft.Container(
                            bgcolor=(
                                DUO_BLUE_LIGHT
                                if h["action"] == "EXPORT"
                                else DUO_GREEN_LIGHT
                            ),
                            padding=10,
                            border_radius=16,
                            content=ft.Icon(
                                ft.Icons.UPLOAD_FILE
                                if h["action"] == "EXPORT"
                                else ft.Icons.RESTORE,
                                color=(
                                    DUO_BLUE
                                    if h["action"] == "EXPORT"
                                    else DUO_GREEN
                                ),
                                size=22,
                            ),
                        ),
                        ft.Column(
                            [
                                ft.Text(
                                    f"{h['action']} • {Path(h['file_path']).name}",
                                    weight=ft.FontWeight.BOLD,
                                    size=14,
                                    color=DUO_DARK_TEXT,
                                ),
                                ft.Text(
                                    f"{h['created_at']} ({h['activities_count']} "
                                    f"goals, {h['logs_count']} logs)",
                                    size=12,
                                    color=DUO_GREY_TEXT,
                                ),
                            ],
                            expand=True,
                            spacing=2,
                        ),
                    ],
                    spacing=12,
                ),
            )
            for h in history
        ]
        return [
            _duo_card(
                padding=18,
                content=ft.Column(
                    [
                        ft.Text(
                            "Safe Vault: Backup & Restore",
                            size=17,
                            weight=ft.FontWeight.BOLD,
                            color=DUO_DARK_TEXT,
                        ),
                        ft.Text(
                            "Save your streaks to a local JSON file or restore "
                            "your progress atomically at any time.",
                            size=13,
                            color=DUO_GREY_TEXT,
                        ),
                        self.backup_path_in,
                        ft.Row(
                            [
                                _duo_button(
                                    "EXPORT",
                                    on_click=self._on_export_backup,
                                    icon=ft.Icons.UPLOAD_FILE,
                                    bg=DUO_BLUE,
                                    expand=True,
                                ),
                                _duo_button(
                                    "RESTORE",
                                    on_click=self._on_restore_backup,
                                    icon=ft.Icons.RESTORE,
                                    bg=DUO_GREEN,
                                    expand=True,
                                ),
                            ],
                            spacing=10,
                        ),
                    ],
                    spacing=12,
                ),
            ),
            ft.Text(
                "Backup Audit Log",
                size=17,
                weight=ft.FontWeight.BOLD,
                color=DUO_DARK_TEXT,
            ),
            *(
                hist_cards
                or [
                    _empty_state(
                        ft.Icons.CLOUD_DONE_OUTLINED,
                        "No backups recorded yet",
                        "Tap EXPORT above to create your first JSON snapshot.",
                    )
                ]
            ),
        ]

    def render_tab(self, index: int) -> None:
        """Render the selected tab view and toggle the FAB on the Habits tab."""
        builders = {
            0: self._build_habits_tab,
            1: self._build_checkin_tab,
            2: self._build_report_tab,
            3: self._build_backup_tab,
        }
        self.fab.visible = index == 0
        self.body_container.controls = builders.get(index, self._build_habits_tab)()
        self.page.update()


def main(page: ft.Page) -> None:
    """Configure Duolingo mobile theme, Nunito font, FAB, and bottom navigation."""
    page.title = "HabitStreak — Physical Activity Tracker"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.fonts = {
        "Nunito": "https://fonts.gstatic.com/s/nunito/v26/XRXV3I6Li01BKofINeaB.ttf"
    }
    page.theme = ft.Theme(font_family="Nunito", color_scheme_seed=DUO_GREEN)
    page.bgcolor = DUO_BG
    page.window.width = MOBILE_WIDTH
    page.window.height = MOBILE_HEIGHT
    page.padding = 16

    db_path = _resolve_app_path(DEFAULT_DB_NAME)
    db = connect(db_path)
    controller = ActivityTrackerUI(page, db)
    page.floating_action_button = controller.fab

    route_map = {"/0": 0, "/1": 1, "/2": 2, "/3": 3}
    initial_tab = route_map.get(
        page.route, int(os.environ.get("TRACKER_INITIAL_TAB", "0"))
    )

    def _on_route(_: Any) -> None:
        tab_idx = route_map.get(page.route, 0)
        if page.navigation_bar:
            page.navigation_bar.selected_index = tab_idx
        controller.render_tab(tab_idx)

    page.on_route_change = _on_route

    header = ft.Container(
        padding=ft.Padding.symmetric(horizontal=18, vertical=14),
        bgcolor=DUO_GREEN,
        border_radius=24,
        content=ft.Row(
            [
                ft.Container(
                    content=ft.Icon(
                        ft.Icons.LOCAL_FIRE_DEPARTMENT,
                        color=DUO_ORANGE,
                        size=28,
                    ),
                    bgcolor=DUO_WHITE,
                    padding=8,
                    border_radius=16,
                ),
                ft.Column(
                    [
                        ft.Text(
                            "HabitStreak",
                            size=20,
                            weight=ft.FontWeight.BOLD,
                            color=DUO_WHITE,
                        ),
                        ft.Text(
                            "Keep your daily activity chain alive!",
                            size=12,
                            color=DUO_GREEN_LIGHT,
                        ),
                    ],
                    spacing=1,
                ),
            ],
            spacing=12,
        ),
    )

    page.navigation_bar = ft.NavigationBar(
        selected_index=initial_tab,
        bgcolor=DUO_WHITE,
        indicator_color=DUO_GREEN_LIGHT,
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
    page.add(header, controller.body_container)
    controller.render_tab(initial_tab)


if __name__ == "__main__":
    ft.run(main)
