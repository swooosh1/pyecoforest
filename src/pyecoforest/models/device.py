"""Device model for pyecoforest (Patched for Hydro & Missing Ambient Probe)."""

from dataclasses import dataclass
from enum import Enum
import logging
from typing import Self

_LOGGER = logging.getLogger(__name__)


class State(Enum):
    """State of the Ecoforest device."""

    OFF = "off"
    STARTING = "starting"
    PRE_HEATING = "pre_heating"
    ON = "on"
    SHUTTING_DOWN = "shutting_down"
    STAND_BY = "stand_by"
    ALARM = "alarm"


STATE_MAPPING = {
    0: State.OFF,
    1: State.STARTING,
    2: State.PRE_HEATING,
    3: State.ON,
    4: State.ON,
    5: State.STARTING,
    6: State.STARTING,
    7: State.ON,
    8: State.SHUTTING_DOWN,
    9: State.SHUTTING_DOWN,
    10: State.STAND_BY,
    11: State.ALARM,
    -2: State.ALARM,
    20: State.STAND_BY,
}


class Alarm(Enum):
    """Alarms of the Ecoforest device."""

    AIR_DEPRESSION = "air_depression"
    PELLETS = "pellets"
    CPU_OVERHEATING = "cpu_overheating"
    UNKNOWN = "unknown"


ALARM_MAPPING = {
    "A01": Alarm.AIR_DEPRESSION,
    "A02": Alarm.AIR_DEPRESSION,
    "A12": Alarm.CPU_OVERHEATING,
    "A99": Alarm.PELLETS,
}

FUEL_MAPPING = {
    "00": "Pellet",
    "01": "Orujo",
    "02": "Pellet",
    "03": "Casca de amêndoa",
    "04": "Lenha",
}


def _safe_float(val: str | None, default: float | None = 0.0) -> float | None:
    """Safely parse float strings from Ecoforest API (handles '--.-' and '---.-')."""
    if val is None:
        return default
    val_clean = val.strip()
    if val_clean in ("--.-", "---.-", ""):
        return default
    try:
        return float(val_clean)
    except ValueError:
        return default


@dataclass
class Device:
    """Ecoforest Device."""

    model_name: str
    serial_number: str
    firmware: str

    on: bool
    state: State
    power: int  # Target power setpoint (consigna_potencia)
    temperature: float  # Target temperature setpoint (consigna_temperatura)
    environment_temperature: float
    cpu_temperature: float
    gas_temperature: float
    ntc_temperature: float

    depression: float
    working_hours: float
    ignitions: int
    live_pulse: float
    pulse_offset: float
    extractor: float
    working_state: int
    working_level: int
    convecto_air_flow: float

    alarm: Alarm | None = None

    # Extended Hydro / 1020 Dashboard Fields
    return_temperature: float | None = None
    water_pressure: float | None = None
    first_level_air_depression: float | None = None
    igniter: int | None = None
    control_mode: str | None = None
    fuel_type: str | None = None

    @classmethod
    def build(cls, data: dict[str, dict[str, str]]) -> Self:
        """Build Device object from API response."""
        information = data["information"]
        status = data["status"]

        state = STATE_MAPPING.get(int(status["estado"]), State.OFF)
        alarm = (
            ALARM_MAPPING.get(information["Am"], Alarm.UNKNOWN)
            if state == State.ALARM
            else None
        )

        # Fallback to Ta from 1020 if status["temperatura"] is "--.-"
        env_temp = _safe_float(status.get("temperatura"), None)
        if env_temp is None:
            env_temp = _safe_float(information.get("Ta"), 0.0)

        raw_fuel = information.get("Fu", "").strip()
        fuel_str = FUEL_MAPPING.get(raw_fuel, raw_fuel if raw_fuel else None)

        return Device(
            # Device info
            model_name=information["Me"].strip(),
            serial_number=information["Ns"].strip(),
            firmware=information["Vs"].strip(),
            # States
            on=bool(int(status["on_off"])),
            state=state,
            alarm=alarm,
            # Targets
            power=int(status["consigna_potencia"]),
            temperature=_safe_float(status.get("consigna_temperatura"), 0.0),
            # Temperatures
            environment_temperature=env_temp,
            cpu_temperature=_safe_float(information.get("Tp"), 0.0),
            gas_temperature=_safe_float(information.get("Th"), 0.0),
            ntc_temperature=_safe_float(information.get("Tn"), 0.0),
            # Other sensors
            depression=_safe_float(information.get("Da"), 0.0),
            working_hours=_safe_float(information.get("Nh"), 0.0),
            ignitions=int(information.get("Ne", 0)),
            live_pulse=_safe_float(information.get("Pn"), 0.0),
            pulse_offset=_safe_float(information.get("Pf"), 0.0),
            extractor=_safe_float(information.get("Ex"), 0.0),
            working_state=int(information.get("Es", 0)),
            working_level=int(information.get("Ni", 0)),
            convecto_air_flow=_safe_float(information.get("Co"), 0.0),
            # Extended Hydro / 1020 Dashboard Fields
            return_temperature=_safe_float(information.get("Rt"), None),
            water_pressure=_safe_float(information.get("Pa"), None),
            first_level_air_depression=_safe_float(information.get("Dp"), None),
            igniter=int(information["Re"]) if "Re" in information else None,
            control_mode=information.get("pC", "").strip() or None,
            fuel_type=fuel_str,
        )
