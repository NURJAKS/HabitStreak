"""Python Flet Service wrapper for the hybrid Health Connect + Pedometer extension."""

from dataclasses import dataclass
from typing import Any

from flet.controls.base_control import control
from flet.controls.control_event import Event, EventHandler
from flet.controls.services.service import Service

__all__ = [
    "FletHealthSteps",
    "PedestrianStatusEvent",
    "SensorErrorEvent",
    "SensorStepEvent",
]


@dataclass
class SensorStepEvent(Event["FletHealthSteps"]):
    """Event emitted when the hardware step sensor counts new steps."""

    raw_steps: int
    timestamp: str


@dataclass
class PedestrianStatusEvent(Event["FletHealthSteps"]):
    """Event emitted when pedestrian movement status changes."""

    status: str
    timestamp: str


@dataclass
class SensorErrorEvent(Event["FletHealthSteps"]):
    """Event emitted when the hardware pedometer sensor reports an error."""

    message: str


@control("FletHealthSteps")
class FletHealthSteps(Service):
    """Hybrid Google Health Connect and hardware pedometer service."""

    on_sensor_step: EventHandler[SensorStepEvent] | None = None
    on_pedestrian_status: EventHandler[PedestrianStatusEvent] | None = None
    on_sensor_error: EventHandler[SensorErrorEvent] | None = None

    async def is_supported(self) -> dict[str, Any]:
        """Check whether the current client supports native mobile step sensors."""
        return await self._invoke_method("is_supported")

    async def check_health_connect_status(self) -> dict[str, Any]:
        """Check Android Health Connect SDK availability."""
        return await self._invoke_method("check_health_connect_status")

    async def install_health_connect(self) -> bool:
        """Open Google Play / installer prompt for Health Connect on Android."""
        return bool(await self._invoke_method("install_health_connect"))

    async def request_permissions(self) -> dict[str, Any]:
        """Request ACTIVITY_RECOGNITION and Health Connect READ_STEPS permissions."""
        return await self._invoke_method("request_permissions")

    async def get_steps_range(self, dates: list[str]) -> dict[str, Any]:
        """Fetch daily step totals from Health Connect for each YYYY-MM-DD date."""
        return await self._invoke_method("get_steps_range", {"dates": dates})

    async def start_pedometer(self) -> dict[str, Any]:
        """Start listening to the device hardware step counter stream."""
        return await self._invoke_method("start_pedometer")

    async def stop_pedometer(self) -> bool:
        """Stop listening to the device hardware step counter stream."""
        return bool(await self._invoke_method("stop_pedometer"))

    async def get_latest_raw_steps(self) -> dict[str, Any]:
        """Return the latest cached raw hardware step counter reading."""
        return await self._invoke_method("get_latest_raw_steps")
