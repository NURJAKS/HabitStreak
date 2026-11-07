"""Root entry point for Flet mobile build (`flet run` / `flet build apk`)."""

from __future__ import annotations

from pathlib import Path
import flet as ft

from tracker.mobile import main

if __name__ == "__main__":
    assets_dir = str(Path(__file__).resolve().parent / "assets")
    ft.run(main, assets_dir=assets_dir)
