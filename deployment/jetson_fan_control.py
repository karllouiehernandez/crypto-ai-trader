#!/usr/bin/env python3
"""Simple hysteresis fan control for Jetson Nano."""

from __future__ import annotations

import logging
import signal
import sys
import time
from pathlib import Path


TARGET_PWM_PATH = Path("/sys/devices/pwm-fan/target_pwm")
THERMAL_ROOT = Path("/sys/class/thermal")
POLL_SECONDS = 5.0

MEDIUM_ON_C = 50.0
MEDIUM_OFF_C = 42.0
HIGH_ON_C = 58.0
HIGH_OFF_C = 52.0

PWM_OFF = 0
PWM_MEDIUM = 160
PWM_HIGH = 255

CONTROL_SENSOR_PRIORITY = (
    "thermal-fan-est",
    "CPU-therm",
    "GPU-therm",
    "PLL-therm",
    "AO-therm",
)

log = logging.getLogger("jetson_fan_control")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

_RUNNING = True


def _handle_signal(signum, _frame) -> None:
    global _RUNNING
    log.info("Received signal %s; shutting down fan controller", signum)
    _RUNNING = False


def discover_thermal_zones(root: Path = THERMAL_ROOT) -> dict[str, Path]:
    """Return a mapping of thermal zone type name -> temp file path."""
    zones: dict[str, Path] = {}
    for zone_dir in sorted(root.glob("thermal_zone*")):
        try:
            zone_type = (zone_dir / "type").read_text(encoding="utf-8").strip()
            temp_path = zone_dir / "temp"
            if zone_type and temp_path.exists():
                zones[zone_type] = temp_path
        except OSError:
            continue
    return zones


def read_temp_c(temp_path: Path) -> float:
    """Return a thermal zone temperature in Celsius."""
    return float(temp_path.read_text(encoding="utf-8").strip()) / 1000.0


def select_control_temp_c(zone_paths: dict[str, Path]) -> tuple[float, str]:
    """Return the preferred control temperature and its sensor label."""
    for zone_name in CONTROL_SENSOR_PRIORITY:
        temp_path = zone_paths.get(zone_name)
        if temp_path is not None:
            return read_temp_c(temp_path), zone_name

    if not zone_paths:
        raise RuntimeError("No thermal zones discovered")

    samples = [(read_temp_c(path), name) for name, path in zone_paths.items()]
    return max(samples, key=lambda item: item[0])


def next_fan_state(temp_c: float, current_state: str) -> str:
    """Apply hysteresis so the fan does not flap around threshold edges."""
    state = current_state if current_state in {"off", "medium", "high"} else "off"

    if state == "off":
        if temp_c >= HIGH_ON_C:
            return "high"
        if temp_c >= MEDIUM_ON_C:
            return "medium"
        return "off"

    if state == "medium":
        if temp_c >= HIGH_ON_C:
            return "high"
        if temp_c <= MEDIUM_OFF_C:
            return "off"
        return "medium"

    if temp_c <= MEDIUM_OFF_C:
        return "off"
    if temp_c <= HIGH_OFF_C:
        return "medium"
    return "high"


def pwm_for_state(state: str) -> int:
    """Map a state label to the actual PWM value."""
    if state == "high":
        return PWM_HIGH
    if state == "medium":
        return PWM_MEDIUM
    return PWM_OFF


def write_pwm(pwm: int, target_path: Path = TARGET_PWM_PATH) -> None:
    """Write a target PWM value."""
    target_path.write_text(f"{int(pwm)}\n", encoding="utf-8")


def run() -> int:
    """Run the continuous fan control loop."""
    if not TARGET_PWM_PATH.exists():
        log.error("Fan PWM path is missing: %s", TARGET_PWM_PATH)
        return 1

    zone_paths = discover_thermal_zones()
    if not zone_paths:
        log.error("No thermal zones discovered under %s", THERMAL_ROOT)
        return 1

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    current_state = "off"
    current_pwm = None
    log.info(
        "Jetson fan control started | sensor_priority=%s thresholds=medium_on:%s medium_off:%s high_on:%s high_off:%s",
        ",".join(CONTROL_SENSOR_PRIORITY),
        MEDIUM_ON_C,
        MEDIUM_OFF_C,
        HIGH_ON_C,
        HIGH_OFF_C,
    )

    while _RUNNING:
        try:
            temp_c, sensor_name = select_control_temp_c(zone_paths)
            desired_state = next_fan_state(temp_c, current_state)
            desired_pwm = pwm_for_state(desired_state)
            if desired_pwm != current_pwm:
                write_pwm(desired_pwm)
                log.info(
                    "Fan state change | sensor=%s temp=%.1fC state=%s pwm=%s",
                    sensor_name,
                    temp_c,
                    desired_state,
                    desired_pwm,
                )
                current_pwm = desired_pwm
                current_state = desired_state
            time.sleep(POLL_SECONDS)
        except Exception as exc:  # pragma: no cover - runtime guard
            log.exception("Fan control loop failed: %s", exc)
            time.sleep(POLL_SECONDS)

    try:
        write_pwm(PWM_OFF)
    except Exception:
        log.exception("Failed to turn fan off on shutdown")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
