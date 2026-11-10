"""Duolingo-inspired Flet mobile UI for Physical Activity Tracker (Option 28).

Supports 3 languages (Kazakh, Russian, English) and Dark/Light themes.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

import flet as ft

from tracker.db import DEFAULT_DB_NAME, connect
from tracker.i18n import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES, tr
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

# Duolingo Core Brand Colors
DUO_GREEN = "#58CC02"
DUO_GREEN_DARK = "#46A302"
DUO_ORANGE = "#FF9600"
DUO_BLUE = "#1CB0F6"
DUO_PURPLE = "#CE82FF"
DUO_RED = "#FF4B4B"
DUO_GOLD = "#FFC800"
DUO_WHITE = "#FFFFFF"

# Light Theme Palette
LIGHT_THEME: dict[str, str] = {
    "bg": "#F7F7F7",
    "card_bg": "#FFFFFF",
    "text": "#3C3C3C",
    "subtext": "#777777",
    "shadow": "#E5E5E5",
    "nav_bg": "#FFFFFF",
    "border": "#E5E5E5",
    "input_bg": "#FFFFFF",
    "green_light": "#E5F8D3",
    "blue_light": "#DDF4FF",
    "orange_light": "#FFF0D6",
    "purple_light": "#F3E5FF",
    "gold_light": "#FFF5D6",
    "red_light": "#FFDFE0",
    "grey_bar": "#E5E5E5",
}

# Dark Theme Palette (Duolingo Obsidian Slate Aesthetic)
DARK_THEME: dict[str, str] = {
    "bg": "#131F24",
    "card_bg": "#202F36",
    "text": "#FFFFFF",
    "subtext": "#9CA3AF",
    "shadow": "#0A1014",
    "nav_bg": "#18252C",
    "border": "#2C3D45",
    "input_bg": "#18252C",
    "green_light": "#1B3B22",
    "blue_light": "#153347",
    "orange_light": "#3D2B14",
    "purple_light": "#331E42",
    "gold_light": "#3D3514",
    "red_light": "#3D1B1E",
    "grey_bar": "#2C3D45",
}

CATEGORY_STYLE_KEYS: dict[str, tuple[Any, str, str]] = {
    "Cardio": (ft.Icons.DIRECTIONS_RUN, DUO_BLUE, "blue_light"),
    "Steps": (ft.Icons.DIRECTIONS_WALK, DUO_GREEN, "green_light"),
    "Strength": (ft.Icons.FITNESS_CENTER, DUO_RED, "red_light"),
    "Hydration": (ft.Icons.WATER_DROP, DUO_BLUE, "blue_light"),
    "Flexibility": (ft.Icons.SELF_IMPROVEMENT, DUO_PURPLE, "purple_light"),
    "Sport": (ft.Icons.EMOJI_EVENTS, DUO_GOLD, "gold_light"),
}


def _resolve_app_path(rel_path: str) -> Path:
    """Resolve relative paths against project root when running inside .flet."""
    candidate = Path(rel_path)
    if candidate.is_absolute():
        return candidate
    if ".flet" in str(Path.cwd()):
        return PROJECT_ROOT / candidate
    return candidate


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


class ActivityTrackerUI:
    """Controller for the 4-tab Duolingo-style Flet mobile interface."""

    def __init__(
        self,
        page: ft.Page,
        db: sqlite3.Connection,
        initial_lang: str = DEFAULT_LANGUAGE,
        is_dark: bool = False,
    ) -> None:
        """Initialize UI state, localization, themes, and interactive controls."""
        self.page = page
        self.db = db
        self.lang = initial_lang if initial_lang in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
        self.is_dark = is_dark
        self.current_tab = 0
        self.last_message = ""
        self.last_error = False

        self.body_container = ft.Column(
            expand=True, scroll=ft.ScrollMode.AUTO, spacing=14
        )
        self.header_container = ft.Container()

        self._init_inputs()
        self.add_sheet = self._build_add_bottom_sheet()
        self.fab = ft.FloatingActionButton(
            icon=ft.Icons.ADD,
            bgcolor=DUO_GREEN,
            foreground_color=DUO_WHITE,
            shape=ft.CircleBorder(),
            tooltip=tr("fab_tooltip", self.lang),
            on_click=self.open_add_sheet,
        )
        self._update_header()

    @property
    def theme(self) -> dict[str, str]:
        """Return the active color dictionary for the current theme mode."""
        return DARK_THEME if self.is_dark else LIGHT_THEME

    def _card(
        self,
        content: ft.Control,
        padding: int = 18,
        bg: str | None = None,
    ) -> ft.Container:
        """Create a bubble-style Duolingo card respecting active theme."""
        t = self.theme
        return ft.Container(
            border_radius=24,
            bgcolor=bg or t["card_bg"],
            padding=padding,
            border=ft.Border.all(1, t["border"]) if self.is_dark else None,
            shadow=ft.BoxShadow(
                spread_radius=1,
                blur_radius=10,
                color=t["shadow"],
                offset=ft.Offset(0, 4),
            ),
            content=content,
        )

    def _empty_state(self, icon: Any, title: str, subtitle: str) -> ft.Container:
        """Render a friendly gamified empty state card respecting active theme."""
        t = self.theme
        return self._card(
            padding=28,
            content=ft.Column(
                [
                    ft.Container(
                        content=ft.Icon(icon, size=56, color=DUO_BLUE),
                        bgcolor=t["blue_light"],
                        padding=20,
                        border_radius=32,
                    ),
                    ft.Text(
                        title,
                        size=18,
                        weight=ft.FontWeight.BOLD,
                        color=t["text"],
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Text(
                        subtitle,
                        size=13,
                        color=t["subtext"],
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
            ),
        )

    def get_category_style(self, category: str) -> tuple[Any, str, str]:
        """Return icon, foreground color, and theme-adapted light background."""
        t = self.theme
        icon, fg, bg_key = CATEGORY_STYLE_KEYS.get(
            category, (ft.Icons.STAR, DUO_BLUE, "blue_light")
        )
        return icon, fg, t[bg_key]

    def _init_inputs(self) -> None:
        """Create rounded input controls for BottomSheet, Check-In, and Backup."""
        t = self.theme
        rounded = ft.OutlineInputBorder(border_radius=20)
        self.title_in = ft.TextField(
            label=tr("field_habit_name", self.lang), border=rounded
        )
        self.cat_dd = ft.Dropdown(
            label=tr("field_category", self.lang),
            value=VALID_CATEGORIES[0],
            options=[
                ft.DropdownOption(key=c, text=tr(f"cat_{c}", self.lang))
                for c in VALID_CATEGORIES
            ],
            width=340,
        )
        self.target_in = ft.TextField(
            label=tr("field_target", self.lang), border=rounded
        )
        self.unit_in = ft.TextField(
            label=tr("field_unit", self.lang), border=rounded
        )

        self.log_act_dd = ft.Dropdown(
            label=tr("field_choose_habit", self.lang),
            width=350,
            on_select=self._on_activity_selected,
        )
        self.log_date_in = ft.TextField(
            label=tr("field_date", self.lang),
            value=date.today().strftime(DATE_FMT),
            border=rounded,
        )
        self.log_val_in = ft.TextField(
            label="Value", value="0", border=rounded, visible=False
        )
        self.log_notes_in = ft.TextField(
            label=tr("field_workout_note", self.lang), border=rounded
        )
        self.ring_bar = ft.ProgressRing(
            value=0.0,
            width=130,
            height=130,
            stroke_width=14,
            color=DUO_GREEN,
            bgcolor=t["grey_bar"],
        )
        self.ring_label = ft.Text(
            "0%", size=22, weight=ft.FontWeight.BOLD, color=t["text"]
        )
        self.ring_sub = ft.Text("0 / 0", size=13, color=t["subtext"])
        self.val_slider = ft.Slider(
            min=0,
            max=100,
            value=0,
            active_color=DUO_GREEN,
            inactive_color=t["grey_bar"],
            thumb_color=DUO_GREEN,
            on_change=self._on_slider_change,
        )
        self.backup_path_in = ft.TextField(
            label=tr("field_backup_file", self.lang),
            value=DEFAULT_BACKUP_PATH,
            border=rounded,
        )

    def _update_localized_controls(self) -> None:
        """Update labels of all inputs, modals, navigation bar, and FAB on language/theme change."""
        t = self.theme
        self.title_in.label = tr("field_habit_name", self.lang)
        self.cat_dd.label = tr("field_category", self.lang)
        self.cat_dd.options = [
            ft.DropdownOption(key=c, text=tr(f"cat_{c}", self.lang))
            for c in VALID_CATEGORIES
        ]
        self.target_in.label = tr("field_target", self.lang)
        self.unit_in.label = tr("field_unit", self.lang)

        self.log_act_dd.label = tr("field_choose_habit", self.lang)
        self.log_date_in.label = tr("field_date", self.lang)
        self.log_notes_in.label = tr("field_workout_note", self.lang)
        self.backup_path_in.label = tr("field_backup_file", self.lang)

        self.ring_bar.bgcolor = t["grey_bar"]
        self.ring_label.color = t["text"]
        self.ring_sub.color = t["subtext"]
        self.val_slider.inactive_color = t["grey_bar"]

        self.fab.tooltip = tr("fab_tooltip", self.lang)
        self.add_sheet = self._build_add_bottom_sheet()
        self._update_header()

        if self.page.navigation_bar:
            self.page.navigation_bar.bgcolor = t["nav_bg"]
            self.page.navigation_bar.indicator_color = t["green_light"]
            self.page.navigation_bar.destinations = [
                ft.NavigationBarDestination(
                    icon=ft.Icons.LOCAL_FIRE_DEPARTMENT,
                    label=tr("tab_habits", self.lang),
                ),
                ft.NavigationBarDestination(
                    icon=ft.Icons.CHECK_CIRCLE,
                    label=tr("tab_checkin", self.lang),
                ),
                ft.NavigationBarDestination(
                    icon=ft.Icons.BAR_CHART,
                    label=tr("tab_weekly", self.lang),
                ),
                ft.NavigationBarDestination(
                    icon=ft.Icons.BACKUP,
                    label=tr("tab_backup", self.lang),
                ),
            ]

    def _update_header(self) -> None:
        """Render the top persistent header with mascot, title, theme toggle, and language switcher."""
        theme_icon = ft.Icons.LIGHT_MODE if self.is_dark else ft.Icons.DARK_MODE
        theme_tooltip = (
            tr("theme_toggle_dark", self.lang)
            if self.is_dark
            else tr("theme_toggle_light", self.lang)
        )

        theme_btn = ft.IconButton(
            icon=theme_icon,
            icon_color=DUO_WHITE,
            icon_size=20,
            tooltip=theme_tooltip,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.with_opacity(0.22, ft.Colors.BLACK),
                shape=ft.CircleBorder(),
            ),
            on_click=lambda _: self.toggle_theme(),
        )

        def _lang_chip(code: str, label: str) -> ft.Container:
            is_active = self.lang == code
            return ft.Container(
                content=ft.Text(
                    label,
                    size=11,
                    weight=ft.FontWeight.BOLD if is_active else ft.FontWeight.NORMAL,
                    color=DUO_GREEN_DARK if is_active else DUO_WHITE,
                ),
                bgcolor=DUO_WHITE if is_active else ft.Colors.TRANSPARENT,
                padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                border_radius=10,
                on_click=lambda _, c=code: self.set_language(c),
            )

        lang_capsule = ft.Container(
            bgcolor=ft.Colors.with_opacity(0.24, ft.Colors.BLACK),
            border_radius=12,
            padding=2,
            content=ft.Row(
                [
                    _lang_chip("kz", "KZ"),
                    _lang_chip("ru", "RU"),
                    _lang_chip("en", "EN"),
                ],
                spacing=2,
                tight=True,
            ),
        )

        icon_widget = ft.Image(
            src="/icon.png",
            width=44,
            height=44,
            fit=ft.BoxFit.CONTAIN,
            border_radius=12,
            error_content=ft.Icon(
                ft.Icons.LOCAL_FIRE_DEPARTMENT,
                color=DUO_ORANGE,
                size=26,
            ),
        )

        self.header_container.content = ft.Container(
            padding=ft.Padding.symmetric(horizontal=16, vertical=12),
            bgcolor=DUO_GREEN,
            border_radius=24,
            shadow=ft.BoxShadow(
                spread_radius=1,
                blur_radius=10,
                color=self.theme["shadow"],
                offset=ft.Offset(0, 4),
            ),
            content=ft.Row(
                [
                    ft.Row(
                        [
                            ft.Container(
                                content=icon_widget,
                                bgcolor=DUO_WHITE,
                                padding=2,
                                border_radius=14,
                            ),
                            ft.Column(
                                [
                                    ft.Text(
                                        tr("app_title", self.lang),
                                        size=18,
                                        weight=ft.FontWeight.BOLD,
                                        color=DUO_WHITE,
                                    ),
                                    ft.Text(
                                        tr("app_subtitle", self.lang),
                                        size=11,
                                        color=DUO_WHITE,
                                        opacity=0.9,
                                        no_wrap=True,
                                        max_lines=1,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                ],
                                spacing=1,
                                expand=True,
                            ),
                        ],
                        spacing=10,
                        expand=True,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Row(
                        [
                            theme_btn,
                            lang_capsule,
                        ],
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    def set_language(self, lang: str) -> None:
        """Switch language between kz, ru, and en, updating all views immediately."""
        if lang not in SUPPORTED_LANGUAGES or lang == self.lang:
            return
        self.lang = lang
        self._update_localized_controls()
        self.render_tab(self.current_tab)
        self.page.update()

    def toggle_theme(self) -> None:
        """Toggle between Duolingo Flat Light mode and Obsidian Dark mode."""
        self.is_dark = not self.is_dark
        self.page.theme_mode = (
            ft.ThemeMode.DARK if self.is_dark else ft.ThemeMode.LIGHT
        )
        self.page.bgcolor = self.theme["bg"]
        self._update_localized_controls()
        self.render_tab(self.current_tab)
        self.page.update()

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
        t = self.theme
        return ft.BottomSheet(
            bgcolor=t["card_bg"],
            show_drag_handle=True,
            shape=ft.RoundedRectangleBorder(radius=24),
            content=ft.Container(
                padding=22,
                content=ft.Column(
                    [
                        ft.Text(
                            tr("modal_new_habit", self.lang),
                            size=20,
                            weight=ft.FontWeight.BOLD,
                            color=t["text"],
                        ),
                        self.title_in,
                        self.cat_dd,
                        self.target_in,
                        self.unit_in,
                        ft.Row(
                            [
                                _duo_button(
                                    tr("btn_create_habit", self.lang),
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
        """Build a vibrant orange streak badge when active, or theme grey when 0."""
        t = self.theme
        active = streak > 0
        bg_color = DUO_ORANGE if active else t["border"]
        fg_color = DUO_WHITE if active else t["subtext"]
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
        t = self.theme
        act_id = item["id"]
        icon_data, icon_fg, icon_bg = self.get_category_style(item["category"])
        progress_val = float(item.get("today_progress", 0.0))
        today_val = float(item.get("today_value", 0.0))
        bar_color = DUO_GREEN if progress_val >= 1.0 else DUO_BLUE

        progress_text = tr(
            "today_progress_sub",
            self.lang,
            today=f"{today_val:g}",
            target=f"{item['target_value']:g}",
            unit=item["unit"],
            best=item["longest_streak"],
        )

        return self._card(
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
                                color=t["text"],
                            ),
                            ft.ProgressBar(
                                value=progress_val,
                                color=bar_color,
                                bgcolor=t["grey_bar"],
                                bar_height=10,
                                border_radius=8,
                            ),
                            ft.Text(
                                progress_text,
                                size=12,
                                color=t["subtext"],
                            ),
                        ],
                        expand=True,
                        spacing=6,
                    ),
                    self._make_streak_badge(int(item["current_streak"])),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        icon_color=t["subtext"],
                        icon_size=20,
                        tooltip=tr("delete_habit_tooltip", self.lang),
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
            self.notify(tr("msg_habit_created", self.lang))
            self.render_tab(0)
        except (TrackerError, ValueError) as exc:
            self.notify(f"Error: {exc}", is_error=True)

    def _on_delete_activity(self, activity_id: int) -> None:
        """Handle deleting an activity habit."""
        try:
            delete_activity(self.db, activity_id)
            self.notify(tr("msg_habit_deleted", self.lang))
            self.render_tab(0)
        except TrackerError as exc:
            self.notify(f"Error: {exc}", is_error=True)

    def _build_habits_tab(self) -> list[ft.Control]:
        """Build the de-cluttered Duolingo Habits & Streaks home screen."""
        t = self.theme
        activities = list_activities(self.db)
        best_now = max((a["current_streak"] for a in activities), default=0)
        completed_today = sum(
            1 for a in activities if float(a.get("today_progress", 0.0)) >= 1.0
        )

        kpi_bar = self._card(
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
                                        tr("streak_kpi", self.lang, count=best_now),
                                        weight=ft.FontWeight.BOLD,
                                        size=15,
                                        color=t["text"],
                                    ),
                                    ft.Text(
                                        tr("streak_kpi_sub", self.lang),
                                        size=11,
                                        color=t["subtext"],
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
                                        tr(
                                            "done_kpi",
                                            self.lang,
                                            done=completed_today,
                                            total=len(activities),
                                        ),
                                        weight=ft.FontWeight.BOLD,
                                        size=15,
                                        color=t["text"],
                                    ),
                                    ft.Text(
                                        tr("done_kpi_sub", self.lang),
                                        size=11,
                                        color=t["subtext"],
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
                self._empty_state(
                    ft.Icons.ROCKET_LAUNCH,
                    tr("empty_habits_title", self.lang),
                    tr("empty_habits_sub", self.lang),
                ),
            ]
        return [
            kpi_bar,
            ft.Text(
                tr("todays_habits_title", self.lang),
                size=18,
                weight=ft.FontWeight.BOLD,
                color=t["text"],
            ),
            *[self._make_habit_card(a) for a in activities],
        ]

    def _sync_checkin_dial(self, activities: list[dict[str, Any]]) -> None:
        """Synchronize the ProgressRing and Slider with the selected activity."""
        if not activities:
            return
        t = self.theme
        selected_id = int(self.log_act_dd.value or activities[0]["id"])
        act = next((a for a in activities if a["id"] == selected_id), activities[0])
        target = float(act["target_value"])
        current = float(self.log_val_in.value or act.get("today_value", 0.0))
        ratio = min(1.0, current / target) if target > 0 else 0.0

        self.val_slider.max = max(target * 1.5, 10.0)
        self.val_slider.value = min(current, self.val_slider.max)
        self.ring_bar.value = ratio
        self.ring_bar.color = DUO_GREEN if ratio >= 1.0 else DUO_BLUE
        self.ring_bar.bgcolor = t["grey_bar"]
        self.ring_label.value = f"{int(ratio * 100)}%"
        self.ring_label.color = t["text"]
        self.ring_sub.value = f"{current:g} / {target:g} {act['unit']}"
        self.ring_sub.color = t["subtext"]

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
                raise TrackerError(tr("err_select_activity", self.lang))
            log_progress(
                self.db,
                int(self.log_act_dd.value),
                self.log_date_in.value or "",
                float(self.log_val_in.value or -1),
                self.log_notes_in.value or "",
            )
            self.log_notes_in.value = ""
            self.notify(tr("msg_checkin_saved", self.lang))
            self.render_tab(1)
        except (TrackerError, ValueError) as exc:
            self.notify(f"Error: {exc}", is_error=True)

    def _build_checkin_tab(self) -> list[ft.Control]:
        """Build the interactive Duolingo Check-In tab with ProgressRing and Slider."""
        t = self.theme
        activities = list_activities(self.db)
        if not activities:
            return [
                self._empty_state(
                    ft.Icons.CHECK_CIRCLE_OUTLINE,
                    tr("empty_checkin_title", self.lang),
                    tr("empty_checkin_sub", self.lang),
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
                    tr("btn_boost_25", self.lang),
                    on_click=lambda _: self._add_quick_boost(0.25),
                    bg=DUO_BLUE,
                    expand=True,
                ),
                _duo_button(
                    tr("btn_boost_50", self.lang),
                    on_click=lambda _: self._add_quick_boost(0.50),
                    bg=DUO_BLUE,
                    expand=True,
                ),
                _duo_button(
                    tr("btn_boost_100", self.lang),
                    on_click=lambda _: self._add_quick_boost(1.0),
                    bg=DUO_ORANGE,
                    expand=True,
                ),
            ],
            spacing=8,
        )

        logs = get_activity_logs(self.db)[:6]
        log_cards = [
            self._card(
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
                                    color=t["text"],
                                ),
                                ft.Text(
                                    f"{r['actual_value']:g} / {r['target_value']:g} "
                                    f"{r['unit']}"
                                    + (f" — {r['notes']}" if r["notes"] else ""),
                                    size=12,
                                    color=t["subtext"],
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
            self._card(
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
                                    tr("btn_complete_checkin", self.lang),
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
                tr("recent_checkins_title", self.lang),
                size=17,
                weight=ft.FontWeight.BOLD,
                color=t["text"],
            ),
            *log_cards,
        ]

    def _build_report_tab(self) -> list[ft.Control]:
        """Build the Duolingo-style 7-Day Weekly Analytics Report tab."""
        t = self.theme
        rep = get_weekly_report(self.db)
        if rep["total_activities"] == 0:
            return [
                self._empty_state(
                    ft.Icons.BAR_CHART,
                    tr("empty_weekly_title", self.lang),
                    tr("empty_weekly_sub", self.lang),
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
                        color=t["text"],
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
                        bgcolor=t["grey_bar"],
                    ),
                    ft.Text(
                        f"{d['completed_count']}/{rep['total_activities']}",
                        size=13,
                        weight=ft.FontWeight.BOLD,
                        color=t["text"],
                    ),
                ],
                spacing=10,
            )
            for d in rep["daily_breakdown"]
        ]
        act_cards = [
            self._card(
                padding=14,
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text(
                                    s["title"],
                                    weight=ft.FontWeight.BOLD,
                                    size=15,
                                    color=t["text"],
                                ),
                                ft.Container(
                                    bgcolor=t["green_light"],
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
                            bgcolor=t["grey_bar"],
                            bar_height=8,
                            border_radius=6,
                        ),
                        ft.Text(
                            tr(
                                "weekly_volume",
                                self.lang,
                                volume=f"{s['total_value']:g}",
                                unit=s["unit"],
                            ),
                            size=12,
                            color=t["subtext"],
                        ),
                    ],
                    spacing=6,
                ),
            )
            for s in rep["activity_summaries"]
        ]
        return [
            self._card(
                padding=18,
                bg=t["green_light"],
                content=ft.Column(
                    [
                        ft.Text(
                            tr(
                                "weekly_report_title",
                                self.lang,
                                start=rep["start_date"],
                                end=rep["end_date"],
                            ),
                            size=12,
                            weight=ft.FontWeight.BOLD,
                            color=t["text"],
                        ),
                        ft.Text(
                            tr("weekly_score", self.lang, rate=rep["completion_rate"]),
                            size=22,
                            weight=ft.FontWeight.BOLD,
                            color=t["text"],
                        ),
                        ft.ProgressBar(
                            value=rep["completion_rate"] / 100.0,
                            color=DUO_GREEN,
                            bgcolor=t["card_bg"],
                            bar_height=12,
                            border_radius=8,
                        ),
                        ft.Text(
                            tr(
                                "weekly_completed_summary",
                                self.lang,
                                done=rep["completed_checkins"],
                                total=rep["possible_checkins"],
                            ),
                            size=13,
                            color=t["text"],
                        ),
                    ],
                    spacing=8,
                ),
            ),
            self._card(
                padding=16,
                content=ft.Column(
                    [
                        ft.Text(
                            tr("chain_7day_title", self.lang),
                            size=16,
                            weight=ft.FontWeight.BOLD,
                            color=t["text"],
                        ),
                        *day_bars,
                    ],
                    spacing=10,
                ),
            ),
            ft.Text(
                tr("volume_breakdown_title", self.lang),
                size=17,
                weight=ft.FontWeight.BOLD,
                color=t["text"],
            ),
            *act_cards,
        ]

    def _on_export_backup(self, _: Any = None) -> None:
        """Handle exporting database state to JSON."""
        try:
            target = _resolve_app_path(self.backup_path_in.value or "")
            meta = export_backup(self.db, target)
            self.notify(
                tr(
                    "msg_exported",
                    self.lang,
                    activities=meta["activities_count"],
                    logs=meta["logs_count"],
                )
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
                tr(
                    "msg_restored",
                    self.lang,
                    activities=meta["activities_count"],
                    logs=meta["logs_count"],
                )
            )
            self.render_tab(3)
        except TrackerError as exc:
            self.notify(f"Error: {exc}", is_error=True)

    def _build_backup_tab(self) -> list[ft.Control]:
        """Build the Duolingo-styled Data Backup & Restore tab."""
        t = self.theme
        history = get_backup_history(self.db)[:8]
        hist_cards = [
            self._card(
                padding=14,
                content=ft.Row(
                    [
                        ft.Container(
                            bgcolor=(
                                t["blue_light"]
                                if h["action"] == "EXPORT"
                                else t["green_light"]
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
                                    color=t["text"],
                                ),
                                ft.Text(
                                    f"{h['created_at']} ({h['activities_count']} "
                                    f"goals, {h['logs_count']} logs)",
                                    size=12,
                                    color=t["subtext"],
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
            self._card(
                padding=18,
                content=ft.Column(
                    [
                        ft.Text(
                            tr("safe_vault_title", self.lang),
                            size=17,
                            weight=ft.FontWeight.BOLD,
                            color=t["text"],
                        ),
                        ft.Text(
                            tr("safe_vault_sub", self.lang),
                            size=13,
                            color=t["subtext"],
                        ),
                        self.backup_path_in,
                        ft.Row(
                            [
                                _duo_button(
                                    tr("btn_export", self.lang),
                                    on_click=self._on_export_backup,
                                    icon=ft.Icons.UPLOAD_FILE,
                                    bg=DUO_BLUE,
                                    expand=True,
                                ),
                                _duo_button(
                                    tr("btn_restore", self.lang),
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
                tr("backup_audit_title", self.lang),
                size=17,
                weight=ft.FontWeight.BOLD,
                color=t["text"],
            ),
            *(
                hist_cards
                or [
                    self._empty_state(
                        ft.Icons.CLOUD_DONE_OUTLINED,
                        tr("empty_backup_title", self.lang),
                        tr("empty_backup_sub", self.lang),
                    )
                ]
            ),
        ]

    def render_tab(self, index: int) -> None:
        """Render the selected tab view and toggle the FAB on the Habits tab."""
        self.current_tab = index
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
    page.bgcolor = LIGHT_THEME["bg"]
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

    page.navigation_bar = ft.NavigationBar(
        selected_index=initial_tab,
        bgcolor=LIGHT_THEME["nav_bg"],
        indicator_color=LIGHT_THEME["green_light"],
        on_change=lambda e: controller.render_tab(int(e.control.selected_index or 0)),
        destinations=[
            ft.NavigationBarDestination(
                icon=ft.Icons.LOCAL_FIRE_DEPARTMENT,
                label=tr("tab_habits", controller.lang),
            ),
            ft.NavigationBarDestination(
                icon=ft.Icons.CHECK_CIRCLE,
                label=tr("tab_checkin", controller.lang),
            ),
            ft.NavigationBarDestination(
                icon=ft.Icons.BAR_CHART,
                label=tr("tab_weekly", controller.lang),
            ),
            ft.NavigationBarDestination(
                icon=ft.Icons.BACKUP,
                label=tr("tab_backup", controller.lang),
            ),
        ],
    )
    page.add(controller.header_container, controller.body_container)
    controller.render_tab(initial_tab)


if __name__ == "__main__":
    assets_path = str(PROJECT_ROOT / "assets")
    ft.run(main, assets_dir=assets_path)
