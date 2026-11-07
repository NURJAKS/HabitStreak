"""Root entry point for Flet mobile build (`flet run` / `flet build apk`)."""

from __future__ import annotations

import flet as ft

from tracker.mobile import main

if __name__ == "__main__":
    ft.run(main)
