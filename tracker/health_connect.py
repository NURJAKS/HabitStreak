"""Hybrid Google Health Connect & Hardware Pedometer service for HabitStreak.

Provides a unified cross-platform pedometer interface:
- On Android / iOS (when FletHealthSteps native service is attached):
  1. Primary: reads daily & 7-day aggregated steps from Google Health Connect.
  2. Fallback / Live: streams real-time steps from the hardware TYPE_STEP_COUNTER
     sensor via `pedometer` and converts boot-cumulative counts into daily totals.
- On Desktop / Web / Tests: provides a deterministic step simulator so developers
  and reviewers can verify sync, streak completion, and 7-day analytics anywhere.
"""

from __future__ import annotations

import logging
import os
import platform
import sqlite3
from datetime import date, datetime, timedelta
from typing import Any

from tracker.service import (
    DATE_FMT,
    TIMESTAMP_FMT,
    TrackerError,
    get_activity,
    get_hardware_sensor_steps,
    get_health_sync_config,
    get_or_create_steps_activity,
    record_hardware_sensor_steps,
    sync_health_connect_range,
    sync_health_connect_steps,
    update_health_sync_config,
)

PLAY_STORE_HEALTH_CONNECT_URL = (
    "https://play.google.com/store/apps/details?id=com.google.android.apps.healthdata"
)

PRIVACY_RATIONALE = (
    "HabitStreak uses Google Health Connect and your phone's low-power step sensor "
    "to track daily steps. Your fitness data stays 100% private inside your local "
    "SQLite database and is never uploaded to any remote server."
)


def is_android() -> bool:
    """Detect whether the current process is running on Android."""
    if os.environ.get("ANDROID_ARGUMENT") or os.environ.get("ANDROID_ROOT"):
        return True
    return "android" in platform.platform().lower()


class HealthConnectManager:
    """Manager for hybrid Health Connect + hardware pedometer synchronization."""

    def __init__(
        self,
        db: sqlite3.Connection,
        initial_simulated_steps: int = 7450,
        native_service: Any = None,
    ) -> None:
        self.db = db
        self.native_service = native_service
        self._simulated_steps = initial_simulated_steps
        self._last_source = "Health Connect + Sensor" if native_service else "Demo Simulator"
        self._last_hc_steps: int | None = None
        self._last_raw_sensor_steps: int | None = None
        self._last_pedestrian_status: str = ""
        self._last_perms: dict[str, Any] = {}
        today = date.today()
        self._simulated_history: dict[str, int] = {
            (today - timedelta(days=6)).strftime(DATE_FMT): 8200,
            (today - timedelta(days=5)).strftime(DATE_FMT): 10450,
            (today - timedelta(days=4)).strftime(DATE_FMT): 9800,
            (today - timedelta(days=3)).strftime(DATE_FMT): 11200,
            (today - timedelta(days=2)).strftime(DATE_FMT): 7600,
            (today - timedelta(days=1)).strftime(DATE_FMT): 10150,
            today.strftime(DATE_FMT): self._simulated_steps,
        }

    def set_native_service(self, native_service: Any) -> None:
        """Attach the FletHealthSteps native Flutter service."""
        self.native_service = native_service
        if native_service is not None:
            self._last_source = "Health Connect + Sensor"

    def set_pedestrian_status(self, status: str) -> None:
        """Store latest live pedestrian status ('walking', 'stopped', etc.)."""
        self._last_pedestrian_status = (status or "").strip()

    @property
    def is_on_android(self) -> bool:
        """Return True if executing on a native Android device."""
        return is_android()

    @property
    def is_native(self) -> bool:
        """Return True when backed by the live mobile FletHealthSteps bridge."""
        return self.native_service is not None

    def is_available(self) -> bool:
        """Check if step tracking is supported on this platform/device."""
        return True

    def is_connected(self) -> bool:
        """Return whether the user has authorized step tracking."""
        cfg = get_health_sync_config(self.db)
        return bool(cfg.get("is_connected", 0))

    def is_auto_sync_enabled(self) -> bool:
        """Return whether auto-sync on launch/resume is enabled."""
        cfg = get_health_sync_config(self.db)
        return bool(cfg.get("auto_sync", 1))

    def set_auto_sync(self, enabled: bool) -> None:
        """Toggle auto-sync on application launch."""
        update_health_sync_config(self.db, auto_sync=enabled)

    def connect(self) -> bool:
        """Mark step tracking as connected in local SQLite settings."""
        now_str = datetime.now().strftime(TIMESTAMP_FMT)
        steps_act = get_or_create_steps_activity(self.db)
        update_health_sync_config(
            self.db,
            is_connected=True,
            last_synced_at=now_str,
            last_sync_status="CONNECTED",
            target_activity_id=steps_act["id"],
        )
        return True

    def disconnect(self) -> None:
        """Revoke step sync authorization in HabitStreak."""
        update_health_sync_config(
            self.db,
            is_connected=False,
            last_sync_status="DISCONNECTED",
        )

    def _get_persisted_today_steps(self) -> int:
        """Read today's logged step total (or hardware sensor total) from SQLite."""
        today_str = date.today().strftime(DATE_FMT)
        cfg = get_health_sync_config(self.db)
        act_id = cfg.get("target_activity_id")
        logged = 0
        if act_id:
            row = self.db.execute(
                "SELECT actual_value FROM activity_logs "
                "WHERE activity_id = ? AND log_date = ?",
                (act_id, today_str),
            ).fetchone()
            if row:
                logged = int(float(row["actual_value"]))
        sensor = get_hardware_sensor_steps(self.db, today_str)
        return max(logged, sensor)

    def fetch_today_steps(self) -> int:
        """Fetch today's cumulative step count (real on mobile, simulated on desktop)."""
        if self.is_native:
            return self._get_persisted_today_steps()
        today_str = date.today().strftime(DATE_FMT)
        return self._simulated_history.get(today_str, self._simulated_steps)

    def fetch_recent_steps(self, days: int = 7) -> dict[str, int]:
        """Fetch step counts for the past N days (used by desktop/demo sync)."""
        result: dict[str, int] = {}
        today = date.today()
        for idx in range(days - 1, -1, -1):
            d_str = (today - timedelta(days=idx)).strftime(DATE_FMT)
            result[d_str] = self._simulated_history.get(d_str, 8000)
        return result

    def simulate_walk(self, added_steps: int = 1000) -> int:
        """Simulate taking steps (for desktop/web demo, testing, and presentation)."""
        today_str = date.today().strftime(DATE_FMT)
        current = self.fetch_today_steps()
        new_val = current + max(0, added_steps)
        self._simulated_steps = new_val
        self._simulated_history[today_str] = new_val
        return new_val

    def handle_sensor_step_event(self, raw_steps: int) -> dict[str, Any]:
        """Process a live TYPE_STEP_COUNTER reading from the hardware pedometer."""
        self._last_raw_sensor_steps = int(raw_steps)
        today_str = date.today().strftime(DATE_FMT)
        sensor_state = record_hardware_sensor_steps(self.db, raw_steps, log_date=today_str)
        sensor_today = int(sensor_state["today_sensor_steps"])

        existing_logged = self._get_persisted_today_steps()
        effective = max(sensor_today, existing_logged)
        updated = False

        if self.is_connected() and sensor_today > 0 and sensor_today >= existing_logged:
            self._last_source = "Hardware Pedometer"
            sync_health_connect_steps(
                self.db,
                steps=effective,
                log_date=today_str,
                notes=f"Live Hardware Pedometer ({effective:,} steps)",
            )
            updated = True

        return {
            "updated": updated,
            "sensor_steps": sensor_today,
            "today_steps": effective,
        }

    def sync_now(self, backfill_days: int = 7) -> dict[str, Any]:
        """Perform synchronous step synchronization (desktop/simulator/SQLite)."""
        if not self.is_connected():
            self.connect()

        today_str = date.today().strftime(DATE_FMT)
        past_days: dict[str, int] = {}

        if not self.is_native:
            history = self.fetch_recent_steps(days=backfill_days)
            past_days = {k: v for k, v in history.items() if k != today_str}
            if past_days:
                sync_health_connect_range(self.db, past_days)

        today_steps = self.fetch_today_steps()
        res = sync_health_connect_steps(self.db, steps=today_steps, log_date=today_str)

        return {
            "status": "SUCCESS",
            "source": self._last_source,
            "synced_steps": today_steps,
            "log_date": today_str,
            "activity_id": res["activity_id"],
            "activity_title": res["activity_title"],
            "target_value": res["target_value"],
            "is_completed": res["is_completed"],
            "current_streak": res["current_streak"],
            "longest_streak": res["longest_streak"],
            "backfilled_days": len(past_days),
        }

    async def connect_native_async(self) -> dict[str, Any]:
        """Request mobile permissions, start live pedometer, and perform hybrid sync."""
        if self.native_service is not None:
            perms = await self.native_service.request_permissions()
            if isinstance(perms, dict):
                self._last_perms = perms
            hc_status = await self.native_service.check_health_connect_status()
            self.connect()
            sync_res = await self.sync_hybrid_async()
            sync_res["permissions"] = perms
            sync_res["health_connect_status"] = hc_status
            return sync_res
        self.connect()
        return self.sync_now()

    async def sync_hybrid_async(self, backfill_days: int = 7) -> dict[str, Any]:
        """Hybrid mobile sync: Health Connect primary + hardware pedometer fallback."""
        if self.native_service is None:
            return self.sync_now(backfill_days=backfill_days)

        if not self.is_connected():
            self.connect()

        today = date.today()
        today_str = today.strftime(DATE_FMT)
        dates = [
            (today - timedelta(days=idx)).strftime(DATE_FMT)
            for idx in range(backfill_days - 1, -1, -1)
        ]

        # 1. Query Google Health Connect for today + recent history
        hc_steps_map: dict[str, int] = {}
        hc_ok = False
        try:
            hc_res = await self.native_service.get_steps_range(dates)
            if isinstance(hc_res, dict) and hc_res.get("ok"):
                hc_ok = True
                raw_map = hc_res.get("steps") or {}
                hc_steps_map = {str(k): int(v) for k, v in raw_map.items()}
        except (RuntimeError, ValueError, TypeError, TimeoutError, OSError) as exc:
            logging.getLogger(__name__).debug("Health Connect query fallback: %s", exc)
            hc_ok = False

        # 2. Ensure hardware pedometer stream is active & capture latest raw reading
        try:
            raw_info = await self.native_service.get_latest_raw_steps()
            if isinstance(raw_info, dict) and not raw_info.get("active"):
                await self.native_service.start_pedometer()
                raw_info = await self.native_service.get_latest_raw_steps()
            if isinstance(raw_info, dict) and raw_info.get("raw_steps") is not None:
                self._last_raw_sensor_steps = int(raw_info["raw_steps"])
                record_hardware_sensor_steps(
                    self.db, int(raw_info["raw_steps"]), log_date=today_str
                )
            if isinstance(raw_info, dict) and raw_info.get("pedestrian_status"):
                self._last_pedestrian_status = str(raw_info["pedestrian_status"])
        except (RuntimeError, ValueError, TypeError, TimeoutError, OSError, TrackerError) as exc:
            logging.getLogger(__name__).debug("Hardware pedometer query skipped: %s", exc)

        # 3. Backfill past days when Health Connect provided historical counts
        past_days = {
            k: v for k, v in hc_steps_map.items() if k != today_str and v > 0
        }
        if past_days:
            sync_health_connect_range(self.db, past_days)

        # 4. Merge today's Health Connect count with hardware sensor & existing log
        hc_today = hc_steps_map.get(today_str, 0) if hc_ok else 0
        self._last_hc_steps = hc_today if hc_ok else None
        sensor_today = get_hardware_sensor_steps(self.db, today_str)
        existing_today = self._get_persisted_today_steps()
        merged_today = max(hc_today, sensor_today, existing_today)

        if hc_today > 0 and hc_today >= sensor_today:
            source = "Google Health Connect"
        elif sensor_today > 0:
            source = "Hardware Pedometer"
        elif hc_ok:
            source = "Google Health Connect"
        else:
            source = "Hardware Pedometer"
        self._last_source = source

        res = sync_health_connect_steps(
            self.db,
            steps=merged_today,
            log_date=today_str,
            notes=f"Synced via {source} ({merged_today:,} steps)",
        )

        return {
            "status": "SUCCESS",
            "source": source,
            "hc_steps": hc_today,
            "sensor_steps": sensor_today,
            "synced_steps": merged_today,
            "log_date": today_str,
            "activity_id": res["activity_id"],
            "activity_title": res["activity_title"],
            "target_value": res["target_value"],
            "is_completed": res["is_completed"],
            "current_streak": res["current_streak"],
            "longest_streak": res["longest_streak"],
            "backfilled_days": len(past_days),
        }

    def get_status_summary(self) -> dict[str, Any]:
        """Return a structured summary dictionary for UI display."""
        cfg = get_health_sync_config(self.db)
        is_conn = bool(cfg.get("is_connected", 0))
        today_steps = self.fetch_today_steps()

        target = 10000.0
        act_id = cfg.get("target_activity_id")
        if act_id:
            try:
                row = get_activity(self.db, act_id)
                target = float(row["target_value"])
            except TrackerError:
                pass
        else:
            row = self.db.execute(
                "SELECT target_value FROM activities WHERE category = 'Steps' LIMIT 1"
            ).fetchone()
            if row:
                target = float(row["target_value"])
            elif is_conn:
                act = get_or_create_steps_activity(self.db)
                target = float(act["target_value"])

        pct = min(1.0, round(today_steps / target, 3)) if target > 0 else 0.0
        provider = (
            "Health Connect + Sensor"
            if (self.is_native or self.is_on_android)
            else "Health Connect (Demo Simulator)"
        )

        return {
            "is_connected": is_conn,
            "is_native": self.is_native,
            "auto_sync": bool(cfg.get("auto_sync", 1)),
            "last_synced_at": cfg.get("last_synced_at"),
            "last_sync_status": cfg.get("last_sync_status", "IDLE"),
            "today_steps": today_steps,
            "target_steps": int(target),
            "progress_ratio": pct,
            "goal_reached": today_steps >= target,
            "provider_name": provider,
            "source_label": self._last_source if self.is_native else "Demo Simulator",
            "hc_steps": self._last_hc_steps,
            "raw_sensor_steps": self._last_raw_sensor_steps,
            "pedestrian_status": self._last_pedestrian_status,
            "permissions": self._last_perms,
            "play_store_url": PLAY_STORE_HEALTH_CONNECT_URL,
            "privacy_rationale": PRIVACY_RATIONALE,
        }
