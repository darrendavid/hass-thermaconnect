"""Shared device/coordinator models for ThermaConnect.

A ThermaConnect device is *push-only*: it wakes, connects to the broker,
subscribes to its retained ``config`` topic, publishes ``state`` then one or
more ``events`` (telemetry) messages, and disconnects (battery NODEs sleep;
RFX gateways stay connected). There is no request/response channel, so all
entities read from a cached snapshot that the MQTT handlers update.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from .const import (
    CHANNEL_STATUS,
    DEFAULT_OFFLINE_GRACE_MULTIPLIER,
    MIN_OFFLINE_GRACE_SECONDS,
)


def _as_int(value: Any, default: int | None = None) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


@dataclass
class ChannelSnapshot:
    """Merged state for one channel (config + latest state + telemetry)."""

    number: int
    label: str | None = None
    enabled: bool = True
    unit: str | None = None          # "F" | "C" | "RH" from state/config
    sensor_type: int | None = None   # channel type code (config/BLE)
    status: int | None = None        # 0..4 see CHANNEL_STATUS

    value: float | None = None       # latest temperature reading
    humidity: float | None = None    # latest humidity reading
    reading_ts: float | None = None  # epoch seconds of the latest reading

    high_alarm_value: float | None = None
    low_alarm_value: float | None = None
    high_alarm_enabled: bool | None = None
    low_alarm_enabled: bool | None = None
    high_alarm_muted: bool | None = None
    low_alarm_muted: bool | None = None
    high_alarming: bool | None = None
    low_alarming: bool | None = None

    trim_value: float | None = None
    trim_unit: str | None = None

    def update_from_config(self, cfg: dict[str, Any]) -> None:
        self.label = cfg.get("label", self.label)
        if "enabled" in cfg:
            self.enabled = bool(cfg["enabled"])
        for key in ("units", "displayUnits"):
            if cfg.get(key):
                self.unit = cfg[key]
                break
        high = cfg.get("alarmHigh") or {}
        low = cfg.get("alarmLow") or {}
        if "value" in high:
            self.high_alarm_value = _to_float(high.get("value"))
        if "value" in low:
            self.low_alarm_value = _to_float(low.get("value"))
        if "enabled" in high:
            self.high_alarm_enabled = bool(high["enabled"])
        if "enabled" in low:
            self.low_alarm_enabled = bool(low["enabled"])
        if "muted" in high:
            self.high_alarm_muted = bool(high["muted"])
        if "muted" in low:
            self.low_alarm_muted = bool(low["muted"])
        trim = cfg.get("trim") or {}
        if "value" in trim:
            self.trim_value = _to_float(trim.get("value"))
            self.trim_unit = trim.get("units", self.trim_unit)

    def update_from_state(self, ch: dict[str, Any]) -> None:
        reading = ch.get("reading") or {}
        value = _to_float(reading.get("value"))
        if value is not None:
            rtype = (reading.get("type") or "T").upper()
            if rtype == READING_HUMIDITY_KEY:
                self.humidity = value
            else:
                self.value = value
            ts = _to_float(reading.get("ts"))
            if ts is not None:
                self.reading_ts = ts / 1000.0 if ts > 1e11 else ts
        high = ch.get("highAlarm") or {}
        low = ch.get("lowAlarm") or {}
        if "alarming" in high:
            self.high_alarming = bool(high["alarming"])
        if "alarming" in low:
            self.low_alarming = bool(low["alarming"])

    def update_from_telemetry(self, ch: dict[str, Any]) -> None:
        ts = _to_float(ch.get("ts"))
        if ts is not None:
            self.reading_ts = ts / 1000.0 if ts > 1e11 else ts
        for reading in ch.get("readings") or []:
            value = _to_float(reading.get("value"))
            if value is None:
                continue
            rtype = (reading.get("type") or "T").upper()
            if rtype == READING_HUMIDITY_KEY:
                self.humidity = value
            else:
                self.value = value


READING_HUMIDITY_KEY = "H"


def _to_float(value: Any) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


@dataclass
class ThermaConnectDevice:
    """One physical device (NODE / Signals / RFX gateway)."""

    device_id: str  # serial, e.g. T10061CE92E24
    name: str
    channels: dict[int, ChannelSnapshot] = field(default_factory=dict)

    # state object fields
    model: str | None = None       # "device" field e.g. "signals"
    kind: str | None = None        # "type" field e.g. "bbq"
    firmware: str | None = None
    wifi_strength: int | None = None
    battery: str | None = None     # letter code, e.g. "C"
    connected_ssid: str | None = None
    display_units: str | None = None
    transmit_interval: int | None = None
    recording_interval: int | None = None

    last_seen: float = 0.0         # epoch seconds of last message
    state_received: bool = False   # at least one state payload seen

    # ------------------------------------------------------------------ util
    @property
    def online(self) -> bool:
        if not self.last_seen:
            return False
        grace = max(
            MIN_OFFLINE_GRACE_SECONDS,
            (self.transmit_interval or 0) * DEFAULT_OFFLINE_GRACE_MULTIPLIER,
        )
        return (time.time() - self.last_seen) <= grace

    def touch(self) -> None:
        self.last_seen = time.time()

    def channel(self, number: int) -> ChannelSnapshot:
        if number not in self.channels:
            self.channels[number] = ChannelSnapshot(number=number)
        return self.channels[number]

    # ------------------------------------------------------------- payloads
    def apply_config(self, payload: dict[str, Any]) -> None:
        """Config is authoritative for labels/alarms; merge into channels."""
        self.name = payload.get("label") or self.name
        self.display_units = payload.get("displayUnits", self.display_units)
        self.transmit_interval = _as_int(
            payload.get("transmitIntervalInSeconds"), self.transmit_interval
        )
        for cfg in payload.get("channels") or []:
            number = _as_int(cfg.get("number"))
            if number is None:
                continue
            self.channel(number).update_from_config(cfg)

    def apply_state(self, payload: dict[str, Any]) -> None:
        self.model = payload.get("device", self.model)
        self.kind = payload.get("type", self.kind)
        self.firmware = payload.get("firmware", self.firmware)
        self.wifi_strength = _as_int(payload.get("wifi_strength"), self.wifi_strength)
        self.battery = payload.get("battery", self.battery)
        self.connected_ssid = payload.get("connectedSSID", self.connected_ssid)
        self.display_units = payload.get("displayUnits", self.display_units)
        self.transmit_interval = _as_int(
            payload.get("transmitIntervalInSeconds"), self.transmit_interval
        )
        self.recording_interval = _as_int(
            payload.get("recordingIntervalInSeconds"), self.recording_interval
        )
        label = payload.get("label")
        if label:
            self.name = label
        for ch in payload.get("channels") or []:
            number = _as_int(ch.get("number"))
            if number is None:
                continue
            self.channel(number).update_from_state(ch)
        self.state_received = True

    def apply_telemetry(self, payload: dict[str, Any]) -> None:
        for ch in payload.get("channels") or []:
            number = _as_int(ch.get("number"))
            if number is None:
                continue
            self.channel(number).update_from_telemetry(ch)

    # ------------------------------------------------------- config builder
    def build_config_payload(self) -> dict[str, Any]:
        """Full config object (device replaces its *entire* config on receipt)."""
        channels = []
        for number in sorted(self.channels):
            ch = self.channels[number]
            entry: dict[str, Any] = {
                "number": number,
                "label": ch.label or f"Channel {number}",
                "enabled": ch.enabled,
                "displayUnits": ch.unit or self.display_units or "F",
                "alarmHigh": {
                    "value": ch.high_alarm_value if ch.high_alarm_value is not None else 0,
                    "units": ch.unit or "F",
                    "enabled": bool(ch.high_alarm_enabled),
                    "muted": bool(ch.high_alarm_muted),
                },
                "alarmLow": {
                    "value": ch.low_alarm_value if ch.low_alarm_value is not None else 0,
                    "units": ch.unit or "F",
                    "enabled": bool(ch.low_alarm_enabled),
                    "muted": bool(ch.low_alarm_muted),
                },
                "trim": {
                    "value": ch.trim_value if ch.trim_value is not None else 0,
                    "units": ch.trim_unit or "F",
                },
            }
            channels.append(entry)
        return {
            "label": self.name,
            "actionLabel": "",
            "units": self.display_units or "F",
            "displayUnits": self.display_units or "F",
            "transmitIntervalInSeconds": self.transmit_interval or 1800,
            "recordingIntervalInSeconds": self.recording_interval or 60,
            "channels": channels,
        }
