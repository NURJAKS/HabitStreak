"""Duolingo-inspired Flet mobile UI for Physical Activity Tracker (Option 28).

Supports 3 languages (Kazakh, Russian, English), Dark/Light themes,
custom athletic color identity (Kinetic Indigo & Radiant Flame), and tactile 3D tiles.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

import flet as ft

from tracker.auth import (
    calculate_bmi,
    ensure_guest_user,
    get_active_user,
    login_user,
    logout_user,
    register_user,
    update_profile,
)
from tracker.db import DEFAULT_DB_NAME, connect
from tracker.i18n import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES, tr
from tracker.service import (
    DATE_FMT,
    VALID_CATEGORIES,
    TrackerError,
    add_activity,
    calculate_streak,
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

# HabitStreak Athletic Identity Palette (Kinetic Indigo & Radiant Flame)
BRAND_PRIMARY = "#4F46E5"        # Kinetic Indigo / Royal Cobalt (App identity, Primary actions)
BRAND_PRIMARY_BEVEL = "#3730A3"  # 3D Tactile Bottom Lip
COLOR_FLAME = "#FF5722"          # Radiant Ember Flame (Streaks, Fire badges, 100% Goal)
COLOR_FLAME_BEVEL = "#C23000"    # 3D Flame Bottom Lip
COLOR_SKY = "#0284C7"            # Electric Sky Blue (Cardio, Secondary actions)
COLOR_SKY_BEVEL = "#035388"
COLOR_CORAL = "#F43F5E"          # Vivid Coral Red (Strength, Delete/Logout)
COLOR_CORAL_BEVEL = "#BE123C"
COLOR_CYAN = "#06B6D4"           # Cyan Aquamarine (Hydration)
COLOR_CYAN_BEVEL = "#0891B2"
COLOR_PURPLE = "#8B5CF6"         # Amethyst Purple (Flexibility)
COLOR_PURPLE_BEVEL = "#6D28D9"
COLOR_AMBER = "#F59E0B"          # Sunburst Amber (Sport, League trophies)
COLOR_AMBER_BEVEL = "#B45309"
COLOR_MINT = "#10B981"           # Athletic Mint (Completed checks, health goals)
COLOR_MINT_BEVEL = "#059669"
COLOR_WHITE = "#FFFFFF"

# Semantic / Legacy Aliases
DUO_GREEN = BRAND_PRIMARY
DUO_GREEN_DARK = BRAND_PRIMARY_BEVEL
DUO_ORANGE = COLOR_FLAME
DUO_BLUE = COLOR_SKY
DUO_PURPLE = COLOR_PURPLE
DUO_RED = COLOR_CORAL
DUO_GOLD = COLOR_AMBER
DUO_WHITE = COLOR_WHITE

BUTTON_BEVELS: dict[str, str] = {
    BRAND_PRIMARY: BRAND_PRIMARY_BEVEL,
    COLOR_FLAME: COLOR_FLAME_BEVEL,
    COLOR_SKY: COLOR_SKY_BEVEL,
    COLOR_CORAL: COLOR_CORAL_BEVEL,
    COLOR_CYAN: COLOR_CYAN_BEVEL,
    COLOR_PURPLE: COLOR_PURPLE_BEVEL,
    COLOR_AMBER: COLOR_AMBER_BEVEL,
    COLOR_MINT: COLOR_MINT_BEVEL,
}

# Light Theme Palette (Athletic Studio — Ultra-clean, crisp, and high-clarity)
LIGHT_THEME: dict[str, str] = {
    "bg": "#F8FAFC",                  # Slate 50 canvas
    "card_bg": "#FFFFFF",             # Crisp pure white
    "card_border_side": "#E2E8F0",    # Slate 200 (1.5px side borders)
    "card_border_bottom": "#CBD5E1",  # Slate 300 (4.0px tactile 3D bottom bevel)
    "text": "#0F172A",                # Slate 900 (ultra crisp, bold text)
    "subtext": "#64748B",             # Slate 500 (smooth secondary text)
    "shadow": "#E2E8F0",
    "nav_bg": "#FFFFFF",
    "border": "#E2E8F0",
    "input_bg": "#FFFFFF",
    "primary_light": "#EEF2FF",
    "flame_light": "#FFF1EB",
    "sky_light": "#E0F2FE",
    "coral_light": "#FFE4E6",
    "cyan_light": "#CFFAFE",
    "purple_light": "#EDE9FE",
    "amber_light": "#FEF3C7",
    "mint_light": "#D1FAE5",
    "grey_bar": "#E2E8F0",
}

# Dark Theme Palette (Obsidian Arena — Deep, futuristic, vivid contrast)
DARK_THEME: dict[str, str] = {
    "bg": "#0B0F19",                  # Deep Obsidian / Midnight Space
    "card_bg": "#131B2E",             # Rich Indigo-Slate tile
    "card_border_side": "#1E293B",    # Slate 800
    "card_border_bottom": "#26354D",  # Tactile 3D bottom bevel
    "text": "#F8FAFC",                # Crisp bright white
    "subtext": "#94A3B8",             # Slate 400
    "shadow": "#05070D",
    "nav_bg": "#0E1524",
    "border": "#1E293B",
    "input_bg": "#0B0F19",
    "primary_light": "#1E1B4B",
    "flame_light": "#3B1406",
    "sky_light": "#082F49",
    "coral_light": "#3D0A14",
    "cyan_light": "#062E38",
    "purple_light": "#2E1065",
    "amber_light": "#451A03",
    "mint_light": "#064E3B",
    "grey_bar": "#1E293B",
}

CATEGORY_STYLE_KEYS: dict[str, tuple[Any, str, str]] = {
    "Cardio": (ft.Icons.DIRECTIONS_RUN, COLOR_SKY, "sky_light"),
    "Steps": (ft.Icons.DIRECTIONS_WALK, BRAND_PRIMARY, "primary_light"),
    "Strength": (ft.Icons.FITNESS_CENTER, COLOR_CORAL, "coral_light"),
    "Hydration": (ft.Icons.WATER_DROP, COLOR_CYAN, "cyan_light"),
    "Flexibility": (ft.Icons.SELF_IMPROVEMENT, COLOR_PURPLE, "purple_light"),
    "Sport": (ft.Icons.EMOJI_EVENTS, COLOR_AMBER, "amber_light"),
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
    bg: str = BRAND_PRIMARY,
    bevel: str | None = None,
    fg: str = COLOR_WHITE,
    expand: bool = False,
    height: int = 48,
) -> ft.Container:
    """Create a tactile Duolingo-style 3D button with a physical bottom bevel."""
    lip_color = bevel or BUTTON_BEVELS.get(bg, BRAND_PRIMARY_BEVEL)
    items: list[ft.Control] = []
    if icon is not None:
        items.append(ft.Icon(icon, size=20, color=fg))
    items.append(
        ft.Text(
            label,
            size=14,
            weight=ft.FontWeight.BOLD,
            color=fg,
        )
    )
    return ft.Container(
        content=ft.Row(
            items,
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
            tight=True,
        ),
        bgcolor=bg,
        border_radius=18,
        border=ft.Border.all(1.0, ft.Colors.with_opacity(0.18, ft.Colors.WHITE)),
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=0,
            color=lip_color,
            offset=ft.Offset(0, 4),
        ),
        height=height,
        expand=expand,
        alignment=ft.Alignment(0, 0),
        on_click=on_click,
    )


class ActivityTrackerUI:
    """Controller for the 5-tab Duolingo-style Flet mobile interface."""

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
        self.current_user: dict[str, Any] | None = get_active_user(self.db)
        self.auth_mode = "login"

        self.body_container = ft.Column(
            expand=True, scroll=ft.ScrollMode.AUTO, spacing=14
        )
        self.header_container = ft.Container()

        self._init_inputs()
        self.add_sheet = self._build_add_bottom_sheet()
        self.fab = ft.FloatingActionButton(
            icon=ft.Icons.ADD,
            bgcolor=COLOR_FLAME,
            foreground_color=COLOR_WHITE,
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
        """Create a tactile Duolingo 3D tile respecting active theme."""
        t = self.theme
        return ft.Container(
            border_radius=22,
            bgcolor=bg or t["card_bg"],
            padding=padding,
            border=ft.Border.all(1.5, t["card_border_side"]),
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=0,
                color=t["card_border_bottom"],
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
                        content=ft.Icon(icon, size=52, color=BRAND_PRIMARY),
                        bgcolor=t["primary_light"],
                        padding=20,
                        border_radius=28,
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
            category, (ft.Icons.STAR, BRAND_PRIMARY, "primary_light")
        )
        return icon, fg, t[bg_key]

    def _init_inputs(self) -> None:
        """Create rounded input controls for BottomSheet, Check-In, and Backup."""
        t = self.theme
        rounded = ft.OutlineInputBorder(border_radius=18)
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
            width=134,
            height=134,
            stroke_width=14,
            color=COLOR_FLAME,
            bgcolor=t["grey_bar"],
        )
        self.ring_label = ft.Text(
            "0%", size=24, weight=ft.FontWeight.BOLD, color=t["text"]
        )
        self.ring_sub = ft.Text("0 / 0", size=13, color=t["subtext"])
        self.val_slider = ft.Slider(
            min=0,
            max=100,
            value=0,
            active_color=COLOR_FLAME,
            inactive_color=t["grey_bar"],
            thumb_color=COLOR_FLAME,
            on_change=self._on_slider_change,
        )
        self.backup_path_in = ft.TextField(
            label=tr("field_backup_file", self.lang),
            value=DEFAULT_BACKUP_PATH,
            border=rounded,
        )

        # Auth Screen Inputs
        self.auth_user_in = ft.TextField(
            label=tr("field_username", self.lang),
            prefix_icon=ft.Icons.PERSON,
            border=rounded,
        )
        self.auth_pass_in = ft.TextField(
            label=tr("field_password", self.lang),
            prefix_icon=ft.Icons.LOCK,
            password=True,
            can_reveal_password=True,
            border=rounded,
        )
        self.auth_name_in = ft.TextField(
            label=tr("field_full_name", self.lang),
            prefix_icon=ft.Icons.BADGE,
            border=rounded,
            visible=False,
        )

        # Profile Tab Inputs
        self.profile_name_in = ft.TextField(
            label=tr("field_full_name", self.lang),
            prefix_icon=ft.Icons.PERSON,
            border=rounded,
        )
        self.profile_age_in = ft.TextField(
            label=tr("profile_field_age", self.lang),
            border=rounded,
        )
        self.profile_weight_in = ft.TextField(
            label=tr("profile_field_weight", self.lang),
            border=rounded,
        )
        self.profile_height_in = ft.TextField(
            label=tr("profile_field_height", self.lang),
            border=rounded,
        )
        self.profile_goals_in = ft.TextField(
            label=tr("profile_field_goals", self.lang),
            hint_text=tr("profile_goals_hint", self.lang),
            multiline=True,
            min_lines=2,
            max_lines=4,
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

        self.auth_user_in.label = tr("field_username", self.lang)
        self.auth_pass_in.label = tr("field_password", self.lang)
        self.auth_name_in.label = tr("field_full_name", self.lang)

        self.profile_name_in.label = tr("field_full_name", self.lang)
        self.profile_age_in.label = tr("profile_field_age", self.lang)
        self.profile_weight_in.label = tr("profile_field_weight", self.lang)
        self.profile_height_in.label = tr("profile_field_height", self.lang)
        self.profile_goals_in.label = tr("profile_field_goals", self.lang)
        self.profile_goals_in.hint_text = tr("profile_goals_hint", self.lang)

        self.ring_bar.bgcolor = t["grey_bar"]
        self.ring_label.color = t["text"]
        self.ring_sub.color = t["subtext"]
        self.val_slider.inactive_color = t["grey_bar"]

        self.fab.tooltip = tr("fab_tooltip", self.lang)
        self.add_sheet = self._build_add_bottom_sheet()
        self._update_header()

        if self.page.navigation_bar:
            self.page.navigation_bar.bgcolor = t["nav_bg"]
            self.page.navigation_bar.indicator_color = t["primary_light"]
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
                ft.NavigationBarDestination(
                    icon=ft.Icons.PERSON,
                    label=tr("tab_profile", self.lang),
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
            icon_color=COLOR_WHITE,
            icon_size=20,
            tooltip=theme_tooltip,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.with_opacity(0.20, ft.Colors.BLACK),
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
                    color=BRAND_PRIMARY if is_active else COLOR_WHITE,
                ),
                bgcolor=COLOR_WHITE if is_active else ft.Colors.TRANSPARENT,
                padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                border_radius=10,
                on_click=lambda _, c=code: self.set_language(c),
            )

        lang_capsule = ft.Container(
            bgcolor=ft.Colors.with_opacity(0.22, ft.Colors.BLACK),
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
            width=46,
            height=46,
            fit=ft.BoxFit.CONTAIN,
            border_radius=14,
            error_content=ft.Icon(
                ft.Icons.LOCAL_FIRE_DEPARTMENT,
                color=COLOR_FLAME,
                size=28,
            ),
        )

        header_bg = BRAND_PRIMARY if not self.is_dark else "#131B2E"
        header_lip = BRAND_PRIMARY_BEVEL if not self.is_dark else "#0B0F19"

        self.header_container.content = ft.Container(
            padding=ft.Padding.symmetric(horizontal=16, vertical=12),
            bgcolor=header_bg,
            border_radius=22,
            border=ft.Border.all(1.0, ft.Colors.with_opacity(0.20, ft.Colors.WHITE)),
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=0,
                color=header_lip,
                offset=ft.Offset(0, 4),
            ),
            content=ft.Row(
                [
                    ft.Row(
                        [
                            ft.Container(
                                content=icon_widget,
                                bgcolor=COLOR_WHITE,
                                padding=2,
                                border_radius=16,
                            ),
                            ft.Column(
                                [
                                    ft.Text(
                                        tr("app_title", self.lang),
                                        size=19,
                                        weight=ft.FontWeight.BOLD,
                                        color=COLOR_WHITE,
                                    ),
                                    ft.Text(
                                        tr("app_subtitle", self.lang),
                                        size=11,
                                        color=ft.Colors.with_opacity(0.85, ft.Colors.WHITE),
                                        no_wrap=True,
                                        max_lines=1,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                ],
                                spacing=1,
                                expand=True,
                            ),
                        ],
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        expand=True,
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
        """Toggle between Athletic Studio Light mode and Obsidian Arena Dark mode."""
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
                message, color=COLOR_WHITE, weight=ft.FontWeight.BOLD, size=14
            ),
            bgcolor=COLOR_CORAL if is_error else BRAND_PRIMARY,
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
            content=ft.Container(
                padding=24,
                border_radius=ft.BorderRadius(top_left=24, top_right=24, bottom_left=0, bottom_right=0),
                content=ft.Column(
                    [
                        ft.Container(
                            width=40,
                            height=4,
                            bgcolor=t["border"],
                            border_radius=2,
                            alignment=ft.Alignment(0, 0),
                        ),
                        ft.Text(
                            tr("modal_new_habit", self.lang),
                            size=20,
                            weight=ft.FontWeight.BOLD,
                            color=t["text"],
                        ),
                        self.title_in,
                        self.cat_dd,
                        ft.Row([self.target_in, self.unit_in], spacing=10),
                        ft.Container(height=6),
                        _duo_button(
                            tr("btn_create_habit", self.lang),
                            on_click=self._on_add_activity,
                            icon=ft.Icons.CHECK,
                            bg=BRAND_PRIMARY,
                            height=50,
                        ),
                    ],
                    spacing=12,
                    tight=True,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ),
        )

    def open_add_sheet(self, _: Any = None) -> None:
        """Open the BottomSheet form to add a new habit goal."""
        self.page.show_dialog(self.add_sheet)

    def _make_streak_badge(self, streak: int) -> ft.Container:
        """Build a radiant flame streak badge when active, or theme muted pill when 0."""
        t = self.theme
        active = streak > 0
        bg_color = t["flame_light"] if active else t["border"]
        fg_color = COLOR_FLAME if active else t["subtext"]
        border_color = ft.Colors.with_opacity(0.35, COLOR_FLAME) if active else t["card_border_bottom"]

        return ft.Container(
            bgcolor=bg_color,
            padding=ft.Padding.symmetric(horizontal=12, vertical=6),
            border_radius=14,
            border=ft.Border.all(1.5, border_color),
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=0,
                color=COLOR_FLAME_BEVEL if active else t["card_border_bottom"],
                offset=ft.Offset(0, 2.5),
            ),
            content=ft.Row(
                [
                    ft.Icon(
                        ft.Icons.LOCAL_FIRE_DEPARTMENT, color=fg_color, size=18
                    ),
                    ft.Text(
                        f"{streak}d",
                        weight=ft.FontWeight.BOLD,
                        size=14,
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
        bar_color = COLOR_MINT if progress_val >= 1.0 else BRAND_PRIMARY

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
                        border_radius=18,
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
        """Build the tactile Duolingo Habits & Streaks home screen."""
        t = self.theme
        activities = list_activities(self.db)
        best_now = max((a["current_streak"] for a in activities), default=0)
        completed_today = sum(
            1 for a in activities if float(a.get("today_progress", 0.0)) >= 1.0
        )

        streak_kpi_card = ft.Container(
            expand=True,
            padding=14,
            bgcolor=t["flame_light"],
            border_radius=20,
            border=ft.Border.all(1.5, ft.Colors.with_opacity(0.35, COLOR_FLAME)),
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=0,
                color=COLOR_FLAME_BEVEL,
                offset=ft.Offset(0, 3.5),
            ),
            content=ft.Row(
                [
                    ft.Icon(
                        ft.Icons.LOCAL_FIRE_DEPARTMENT,
                        color=COLOR_FLAME,
                        size=28,
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
        )

        done_kpi_card = ft.Container(
            expand=True,
            padding=14,
            bgcolor=t["primary_light"],
            border_radius=20,
            border=ft.Border.all(1.5, ft.Colors.with_opacity(0.35, BRAND_PRIMARY)),
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=0,
                color=BRAND_PRIMARY_BEVEL,
                offset=ft.Offset(0, 3.5),
            ),
            content=ft.Row(
                [
                    ft.Icon(
                        ft.Icons.CHECK_CIRCLE, color=BRAND_PRIMARY, size=28
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
        )

        kpi_bar = ft.Row([streak_kpi_card, done_kpi_card], spacing=10)

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
        self.ring_bar.color = COLOR_FLAME if ratio >= 1.0 else BRAND_PRIMARY
        self.ring_bar.bgcolor = t["grey_bar"]
        self.ring_label.value = f"{int(ratio * 100)}%"
        self.ring_label.color = t["text"]
        self.ring_sub.value = f"{current:g} / {target:g} {act['unit']}"
        self.ring_sub.color = t["subtext"]

    def _on_activity_selected(self, _: Any = None) -> None:
        """Handle dropdown selection change on Check-In tab."""
        activities = list_activities(self.db)
        if not activities or not self.log_act_dd.value:
            return
        act = next((a for a in activities if a["id"] == int(self.log_act_dd.value)), None)
        if act:
            self.log_val_in.value = str(act.get("today_value", 0.0))
            self._sync_checkin_dial(activities)
            self.page.update()

    def _on_slider_change(self, e: Any) -> None:
        """Handle interactive value adjustment via Slider control."""
        val = round(float(e.control.value), 1)
        self.log_val_in.value = str(val)
        activities = list_activities(self.db)
        if activities and self.log_act_dd.value:
            act = next((a for a in activities if a["id"] == int(self.log_act_dd.value)), None)
            if act:
                target = float(act["target_value"])
                ratio = min(1.0, val / target) if target > 0 else 0.0
                self.ring_bar.value = ratio
                self.ring_bar.color = COLOR_FLAME if ratio >= 1.0 else BRAND_PRIMARY
                self.ring_label.value = f"{int(ratio * 100)}%"
                self.ring_sub.value = f"{val:g} / {target:g} {act['unit']}"
                self.page.update()

    def _add_quick_boost(self, multiplier: float) -> None:
        """Add percentage of target value to current log amount."""
        activities = list_activities(self.db)
        if not activities or not self.log_act_dd.value:
            return
        act = next((a for a in activities if a["id"] == int(self.log_act_dd.value)), None)
        if not act:
            return
        target = float(act["target_value"])
        if multiplier >= 1.0:
            new_val = target
        else:
            current = float(self.log_val_in.value or 0.0)
            new_val = round(current + target * multiplier, 1)

        self.log_val_in.value = str(new_val)
        self._sync_checkin_dial(activities)
        self.page.update()

    def _on_log_progress(self, _: Any = None) -> None:
        """Handle recording workout progress for the selected activity."""
        if not self.log_act_dd.value:
            self.notify(f"Error: {tr('err_select_activity', self.lang)}", is_error=True)
            return
        try:
            val = float(self.log_val_in.value or 0.0)
            log_progress(
                self.db,
                int(self.log_act_dd.value),
                self.log_date_in.value or date.today().strftime(DATE_FMT),
                val,
                self.log_notes_in.value or "",
            )
            self.log_notes_in.value = ""
            self.notify(tr("msg_checkin_saved", self.lang))
            self.render_tab(1)
        except (TrackerError, ValueError) as exc:
            self.notify(f"Error: {exc}", is_error=True)

    def _build_checkin_tab(self) -> list[ft.Control]:
        """Build the interactive Duolingo Check-In tab with circular ring dial."""
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
            ft.DropdownOption(key=str(a["id"]), text=f"{a['title']} ({a['category']})")
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
                    alignment=ft.Alignment(0, 0),
                    content=ft.Column(
                        [self.ring_label, self.ring_sub],
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=2,
                    ),
                ),
            ],
            width=134,
            height=134,
        )

        boost_row = ft.Row(
            [
                _duo_button(
                    tr("btn_boost_25", self.lang),
                    on_click=lambda _: self._add_quick_boost(0.25),
                    bg=COLOR_SKY,
                    expand=True,
                ),
                _duo_button(
                    tr("btn_boost_50", self.lang),
                    on_click=lambda _: self._add_quick_boost(0.50),
                    bg=BRAND_PRIMARY,
                    expand=True,
                ),
                _duo_button(
                    tr("btn_boost_100", self.lang),
                    on_click=lambda _: self._add_quick_boost(1.0),
                    icon=ft.Icons.LOCAL_FIRE_DEPARTMENT,
                    bg=COLOR_FLAME,
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
                            color=COLOR_MINT if r["is_completed"] else COLOR_FLAME,
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
                        _duo_button(
                            tr("btn_complete_checkin", self.lang),
                            on_click=self._on_log_progress,
                            icon=ft.Icons.CHECK_CIRCLE,
                            bg=COLOR_FLAME,
                            height=50,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=14,
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
        """Build the Duolingo-styled 7-day League Report with awards and bars."""
        t = self.theme
        rep = get_weekly_report(self.db)
        if not rep["total_activities"]:
            return [
                self._empty_state(
                    ft.Icons.LEADERBOARD_OUTLINED,
                    tr("empty_weekly_title", self.lang),
                    tr("empty_weekly_sub", self.lang),
                )
            ]

        day_chain_rows = [
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
                        color=COLOR_FLAME if d["completed_count"] == rep["total_activities"] else BRAND_PRIMARY,
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
                                    bgcolor=t["primary_light"],
                                    padding=ft.Padding.symmetric(
                                        horizontal=10, vertical=4
                                    ),
                                    border_radius=14,
                                    content=ft.Text(
                                        f"{s['completed_days']}/7d ({s['completion_rate']}%)",
                                        size=12,
                                        weight=ft.FontWeight.BOLD,
                                        color=BRAND_PRIMARY,
                                    ),
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        ft.ProgressBar(
                            value=s["completion_rate"] / 100.0,
                            color=COLOR_FLAME if s["completion_rate"] >= 100 else BRAND_PRIMARY,
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

        score_card = ft.Container(
            padding=18,
            bgcolor=t["amber_light"],
            border_radius=22,
            border=ft.Border.all(1.5, ft.Colors.with_opacity(0.35, COLOR_AMBER)),
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=0,
                color=COLOR_AMBER_BEVEL,
                offset=ft.Offset(0, 4.0),
            ),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.EMOJI_EVENTS, color=COLOR_AMBER, size=36),
                            ft.Column(
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
                                ],
                                spacing=1,
                            ),
                        ],
                        spacing=12,
                    ),
                    ft.ProgressBar(
                        value=rep["completion_rate"] / 100.0,
                        color=COLOR_AMBER,
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
                spacing=10,
            ),
        )

        return [
            score_card,
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
                        *day_chain_rows,
                    ],
                    spacing=12,
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
                                t["sky_light"]
                                if h["action"] == "EXPORT"
                                else t["primary_light"]
                            ),
                            padding=10,
                            border_radius=16,
                            content=ft.Icon(
                                ft.Icons.UPLOAD_FILE
                                if h["action"] == "EXPORT"
                                else ft.Icons.RESTORE,
                                color=(
                                    COLOR_SKY
                                    if h["action"] == "EXPORT"
                                    else BRAND_PRIMARY
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
                                    bg=COLOR_SKY,
                                    expand=True,
                                ),
                                _duo_button(
                                    tr("btn_restore", self.lang),
                                    on_click=self._on_restore_backup,
                                    icon=ft.Icons.RESTORE,
                                    bg=BRAND_PRIMARY,
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

    def _on_switch_auth_mode(self, mode: str) -> None:
        self.auth_mode = mode
        self.auth_name_in.visible = mode == "register"
        self.body_container.controls = self._build_auth_view()
        self.page.update()

    def _on_login(self, _evt: Any = None) -> None:
        try:
            user = login_user(
                self.db,
                self.auth_user_in.value or "",
                self.auth_pass_in.value or "",
            )
            self.current_user = user
            self.auth_pass_in.value = ""
            if self.page.navigation_bar:
                self.page.navigation_bar.visible = True
            self.notify(
                tr(
                    "msg_logged_in",
                    self.lang,
                    name=user.get("full_name") or user.get("username", ""),
                )
            )
            self.render_tab(0)
        except TrackerError:
            self.notify(tr("err_invalid_credentials", self.lang), is_error=True)

    def _on_register(self, _evt: Any = None) -> None:
        try:
            user = register_user(
                self.db,
                username=self.auth_user_in.value or "",
                password=self.auth_pass_in.value or "",
                full_name=self.auth_name_in.value or "",
            )
            self.current_user = user
            self.auth_pass_in.value = ""
            if self.page.navigation_bar:
                self.page.navigation_bar.visible = True
            self.notify(
                tr(
                    "msg_registered",
                    self.lang,
                    name=user.get("full_name") or user.get("username", ""),
                )
            )
            self.render_tab(4)
        except TrackerError as exc:
            err_map = {
                "Username must be at least 3 characters": tr(
                    "err_username_short", self.lang
                ),
                "Username already taken": tr("err_username_exists", self.lang),
                "Password must be at least 4 characters": tr(
                    "err_password_short", self.lang
                ),
            }
            msg = err_map.get(str(exc), str(exc))
            self.notify(msg, is_error=True)

    def _on_guest_login(self, _evt: Any = None) -> None:
        user = ensure_guest_user(self.db)
        self.current_user = user
        if self.page.navigation_bar:
            self.page.navigation_bar.visible = True
        self.notify(
            tr(
                "msg_logged_in",
                self.lang,
                name=user.get("full_name") or user.get("username", ""),
            )
        )
        self.render_tab(0)

    def _on_logout(self, _evt: Any = None) -> None:
        logout_user(self.db)
        self.current_user = None
        if self.page.navigation_bar:
            self.page.navigation_bar.visible = False
        self.fab.visible = False
        self.notify(tr("msg_logged_out", self.lang))
        self.body_container.controls = self._build_auth_view()
        self.page.update()

    def _on_save_profile(self, _evt: Any = None) -> None:
        if not self.current_user:
            return
        try:
            raw_age = (self.profile_age_in.value or "").strip()
            raw_weight = (self.profile_weight_in.value or "").strip()
            raw_height = (self.profile_height_in.value or "").strip()
            age_val = int(raw_age) if raw_age else None
            weight_val = float(raw_weight) if raw_weight else None
            height_val = float(raw_height) if raw_height else None
            updated = update_profile(
                self.db,
                user_id=int(self.current_user["id"]),
                full_name=self.profile_name_in.value or "",
                age=age_val,
                weight=weight_val,
                height=height_val,
                personal_goals=self.profile_goals_in.value or "",
            )
            self.current_user = updated
            self.notify(tr("profile_msg_saved", self.lang))
            self.render_tab(4)
        except TrackerError as exc:
            self.notify(f"Error: {exc}", is_error=True)
        except ValueError:
            self.notify(
                "Error: Invalid numeric value for age, weight, or height", is_error=True
            )

    def _build_auth_view(self) -> list[ft.Control]:
        """Render the Duolingo-styled Login and Registration authentication screen."""
        t = self.theme
        is_login = self.auth_mode == "login"
        self.auth_name_in.visible = not is_login

        def _mode_tab(label: str, mode: str) -> ft.Container:
            active = self.auth_mode == mode
            return ft.Container(
                content=ft.Text(
                    label,
                    size=13,
                    weight=ft.FontWeight.BOLD if active else ft.FontWeight.NORMAL,
                    color=COLOR_WHITE if active else t["subtext"],
                ),
                bgcolor=BRAND_PRIMARY if active else ft.Colors.TRANSPARENT,
                padding=ft.Padding.symmetric(horizontal=18, vertical=8),
                border_radius=16,
                on_click=lambda _, m=mode: self._on_switch_auth_mode(m),
            )

        mode_switcher = ft.Container(
            bgcolor=t["border"],
            border_radius=18,
            padding=3,
            content=ft.Row(
                [
                    _mode_tab(tr("auth_tab_login", self.lang), "login"),
                    _mode_tab(tr("auth_tab_register", self.lang), "register"),
                ],
                tight=True,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
        )

        icon_widget = ft.Image(
            src="/icon.png",
            width=76,
            height=76,
            fit=ft.BoxFit.CONTAIN,
            border_radius=22,
            error_content=ft.Icon(
                ft.Icons.LOCAL_FIRE_DEPARTMENT,
                color=COLOR_FLAME,
                size=52,
            ),
        )

        main_btn_label = (
            tr("btn_login", self.lang) if is_login else tr("btn_register", self.lang)
        )
        main_btn_handler = self._on_login if is_login else self._on_register

        card_content = ft.Column(
            [
                ft.Container(
                    content=icon_widget,
                    bgcolor=COLOR_WHITE if self.is_dark else t["primary_light"],
                    padding=10,
                    border_radius=26,
                    border=ft.Border.all(1.5, ft.Colors.with_opacity(0.3, BRAND_PRIMARY)),
                    shadow=ft.BoxShadow(
                        spread_radius=0,
                        blur_radius=0,
                        color=BRAND_PRIMARY_BEVEL,
                        offset=ft.Offset(0, 3.0),
                    ),
                ),
                ft.Text(
                    tr("auth_welcome_title", self.lang),
                    size=22,
                    weight=ft.FontWeight.BOLD,
                    color=t["text"],
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Text(
                    tr("auth_welcome_sub", self.lang),
                    size=13,
                    color=t["subtext"],
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Container(height=6),
                mode_switcher,
                ft.Container(height=10),
                self.auth_name_in,
                self.auth_user_in,
                self.auth_pass_in,
                ft.Container(height=10),
                _duo_button(
                    main_btn_label,
                    on_click=main_btn_handler,
                    icon=ft.Icons.LOGIN if is_login else ft.Icons.PERSON_ADD,
                    bg=BRAND_PRIMARY,
                    height=50,
                ),
                _duo_button(
                    tr("btn_guest_mode", self.lang),
                    on_click=self._on_guest_login,
                    icon=ft.Icons.PLAY_ARROW_ROUNDED,
                    bg=COLOR_SKY,
                    height=46,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
        )

        return [self._card(card_content, padding=24)]

    def _build_profile_tab(self) -> list[ft.Control]:
        """Render the user profile tab with metrics, goals, BMI, and logout."""
        t = self.theme
        u = self.current_user or {}

        # Sync input fields
        self.profile_name_in.value = u.get("full_name") or u.get("username") or ""
        self.profile_age_in.value = (
            str(u.get("age")) if u.get("age") is not None else ""
        )
        self.profile_weight_in.value = (
            str(u.get("weight")) if u.get("weight") is not None else ""
        )
        self.profile_height_in.value = (
            str(u.get("height")) if u.get("height") is not None else ""
        )
        self.profile_goals_in.value = u.get("personal_goals") or ""

        # Calculate high level stats
        activities = list_activities(self.db)
        best_streak = 0
        for act in activities:
            st = calculate_streak(self.db, int(act["id"]))
            best_streak = max(best_streak, st["longest_streak"])

        log_cnt_row = self.db.execute(
            "SELECT COUNT(*) AS cnt FROM activity_logs"
        ).fetchone()
        total_logs = int(log_cnt_row["cnt"]) if log_cnt_row else 0

        # Avatar Banner Card
        created_date = (u.get("created_at") or "")[:10]
        banner_card = self._card(
            ft.Row(
                [
                    ft.Container(
                        content=ft.Icon(ft.Icons.PERSON, size=38, color=COLOR_WHITE),
                        bgcolor=BRAND_PRIMARY,
                        padding=14,
                        border_radius=28,
                        shadow=ft.BoxShadow(
                            spread_radius=0,
                            blur_radius=0,
                            color=BRAND_PRIMARY_BEVEL,
                            offset=ft.Offset(0, 3.5),
                        ),
                    ),
                    ft.Column(
                        [
                            ft.Text(
                                u.get("full_name") or u.get("username", "Athlete"),
                                size=20,
                                weight=ft.FontWeight.BOLD,
                                color=t["text"],
                            ),
                            ft.Text(
                                f"@{u.get('username', 'athlete')}",
                                size=13,
                                color=COLOR_SKY,
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.Text(
                                tr(
                                    "profile_member_since",
                                    self.lang,
                                    date=created_date or "2026",
                                ),
                                size=11,
                                color=t["subtext"],
                            ),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                ],
                spacing=14,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=18,
        )

        # Quick KPI Row
        def _mini_stat(
            icon: Any, icon_color: str, val: str, label: str
        ) -> ft.Container:
            return ft.Container(
                expand=True,
                padding=12,
                border_radius=18,
                bgcolor=t["border"],
                border=ft.Border.all(1.5, t["card_border_side"]),
                shadow=ft.BoxShadow(
                    spread_radius=0,
                    blur_radius=0,
                    color=t["card_border_bottom"],
                    offset=ft.Offset(0, 3.0),
                ),
                content=ft.Column(
                    [
                        ft.Icon(icon, size=24, color=icon_color),
                        ft.Text(
                            val, size=18, weight=ft.FontWeight.BOLD, color=t["text"]
                        ),
                        ft.Text(
                            label,
                            size=11,
                            color=t["subtext"],
                            no_wrap=True,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=2,
                ),
            )

        kpi_row = ft.Row(
            [
                _mini_stat(
                    ft.Icons.FITNESS_CENTER,
                    COLOR_SKY,
                    str(len(activities)),
                    tr("stat_total_habits", self.lang),
                ),
                _mini_stat(
                    ft.Icons.LOCAL_FIRE_DEPARTMENT,
                    COLOR_FLAME,
                    f"{best_streak}d",
                    tr("stat_best_streak", self.lang),
                ),
                _mini_stat(
                    ft.Icons.CHECK_CIRCLE,
                    COLOR_MINT,
                    str(total_logs),
                    tr("stat_total_checkins", self.lang),
                ),
            ],
            spacing=10,
        )

        # BMI Metric Pill
        bmi_result = calculate_bmi(u.get("weight"), u.get("height"))
        if bmi_result:
            bmi_val, cat_key = bmi_result
            bmi_styles = {
                "bmi_underweight": (COLOR_SKY, t["sky_light"], COLOR_SKY_BEVEL),
                "bmi_normal": (COLOR_MINT, t["mint_light"], COLOR_MINT_BEVEL),
                "bmi_overweight": (COLOR_AMBER, t["amber_light"], COLOR_AMBER_BEVEL),
                "bmi_obese": (COLOR_CORAL, t["coral_light"], COLOR_CORAL_BEVEL),
            }
            badge_fg, badge_bg, badge_lip = bmi_styles.get(
                cat_key, (BRAND_PRIMARY, t["primary_light"], BRAND_PRIMARY_BEVEL)
            )
            bmi_control = ft.Container(
                bgcolor=badge_bg,
                border_radius=16,
                border=ft.Border.all(1.5, ft.Colors.with_opacity(0.4, badge_fg)),
                shadow=ft.BoxShadow(
                    spread_radius=0,
                    blur_radius=0,
                    color=badge_lip,
                    offset=ft.Offset(0, 2.5),
                ),
                padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.SPEED, size=22, color=badge_fg),
                        ft.Text(
                            tr(
                                "bmi_title",
                                self.lang,
                                val=bmi_val,
                                cat=tr(cat_key, self.lang),
                            ),
                            size=14,
                            weight=ft.FontWeight.BOLD,
                            color=badge_fg,
                        ),
                    ],
                    spacing=8,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
            )
        else:
            bmi_control = ft.Text(
                tr("bmi_hint", self.lang),
                size=12,
                color=t["subtext"],
                italic=True,
            )

        # Form Card: Body Metrics & Goals
        metrics_card = self._card(
            ft.Column(
                [
                    ft.Text(
                        tr("profile_metrics_title", self.lang),
                        size=17,
                        weight=ft.FontWeight.BOLD,
                        color=t["text"],
                    ),
                    bmi_control,
                    self.profile_name_in,
                    ft.Row(
                        [
                            ft.Container(content=self.profile_age_in, expand=1),
                            ft.Container(content=self.profile_weight_in, expand=1),
                            ft.Container(content=self.profile_height_in, expand=1),
                        ],
                        spacing=8,
                    ),
                    self.profile_goals_in,
                    ft.Container(height=6),
                    _duo_button(
                        tr("profile_btn_save", self.lang),
                        on_click=self._on_save_profile,
                        icon=ft.Icons.SAVE,
                        bg=BRAND_PRIMARY,
                        height=50,
                    ),
                ],
                spacing=12,
            ),
            padding=20,
        )

        # Logout Button
        logout_btn = _duo_button(
            tr("profile_btn_logout", self.lang),
            on_click=self._on_logout,
            icon=ft.Icons.LOGOUT,
            bg=COLOR_CORAL,
            height=46,
        )

        return [
            banner_card,
            kpi_row,
            metrics_card,
            logout_btn,
        ]

    def render_tab(self, index: int) -> None:
        """Render the selected tab view or gate on the auth screen."""
        if self.current_user is None:
            if self.page.navigation_bar:
                self.page.navigation_bar.visible = False
            self.fab.visible = False
            self.body_container.controls = self._build_auth_view()
            self.page.update()
            return

        if self.page.navigation_bar:
            self.page.navigation_bar.visible = True
            self.page.navigation_bar.selected_index = index

        self.current_tab = index
        builders = {
            0: self._build_habits_tab,
            1: self._build_checkin_tab,
            2: self._build_report_tab,
            3: self._build_backup_tab,
            4: self._build_profile_tab,
        }
        self.fab.visible = index == 0
        self.body_container.controls = builders.get(index, self._build_habits_tab)()
        self.page.update()


def main(page: ft.Page) -> None:
    """Configure Duolingo mobile theme, Nunito font, FAB, and bottom navigation."""
    init_lang = os.environ.get("TRACKER_INITIAL_LANG", DEFAULT_LANGUAGE)
    init_dark = os.environ.get("TRACKER_INITIAL_DARK", "0") == "1"

    page.title = "HabitStreak — Physical Activity Tracker"
    page.theme_mode = ft.ThemeMode.DARK if init_dark else ft.ThemeMode.LIGHT
    page.fonts = {
        "Nunito": "https://fonts.gstatic.com/s/nunito/v26/XRXV3I6Li01BKofINeaB.ttf"
    }
    page.theme = ft.Theme(font_family="Nunito", color_scheme_seed=BRAND_PRIMARY)
    page.window.width = MOBILE_WIDTH
    page.window.height = MOBILE_HEIGHT
    page.padding = 16

    db_path = _resolve_app_path(DEFAULT_DB_NAME)
    db = connect(db_path)
    controller = ActivityTrackerUI(
        page, db, initial_lang=init_lang, is_dark=init_dark
    )
    page.bgcolor = controller.theme["bg"]
    page.floating_action_button = controller.fab

    route_map = {"/0": 0, "/1": 1, "/2": 2, "/3": 3, "/4": 4}
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
        bgcolor=controller.theme["nav_bg"],
        indicator_color=controller.theme["primary_light"],
        visible=controller.current_user is not None,
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
            ft.NavigationBarDestination(
                icon=ft.Icons.PERSON,
                label=tr("tab_profile", controller.lang),
            ),
        ],
    )
    page.add(controller.header_container, controller.body_container)
    controller.render_tab(initial_tab)


if __name__ == "__main__":
    assets_path = str(PROJECT_ROOT / "assets")
    ft.run(main, assets_dir=assets_path)
