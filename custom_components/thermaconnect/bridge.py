"""MQTT subscription manager for ThermaConnect devices."""

from __future__ import annotations

import logging
from typing import Callable

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from .const import (
    CONF_AUTO_DISCOVER,
    CONF_DEVICE_IDS,
    CONF_TOPIC_PREFIX,
    DEFAULT_TOPIC_PREFIX,
    PROBE_PREFIX,
    TOPIC_CONFIG,
    TOPIC_EVENTS_WILDCARD,
    TOPIC_PROBE_EVENTS_WILDCARD,
    TOPIC_STATE_WILDCARD,
)
from .models import ThermaConnectDevice

_LOGGER = logging.getLogger(__name__)

type DeviceListener = Callable[[ThermaConnectDevice], None]


class ThermaConnectBridge:
    """Owns all MQTT subscriptions and the device snapshot cache.

    The firmware pushes on wake; we cannot poll it, so this bridge is the
    single source of truth that entities subscribe to for updates.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        prefix = (entry.data.get(CONF_TOPIC_PREFIX) or DEFAULT_TOPIC_PREFIX).rstrip("/")
        if not prefix.startswith("/"):
            prefix = "/" + prefix
        self.prefix = prefix
        self.auto_discover = bool(entry.data.get(CONF_AUTO_DISCOVER, True))

        self.devices: dict[str, ThermaConnectDevice] = {}
        self._listeners: list[DeviceListener] = []
        self._unsubs: list[Callable[[], None]] = []

    # ------------------------------------------------------------- lifecycle
    async def async_setup(self) -> None:
        for serial in _parse_ids(self.entry.data.get(CONF_DEVICE_IDS, "")):
            self._ensure_device(serial)

        self._unsubs.append(
            await mqtt.async_subscribe(
                self.hass,
                TOPIC_STATE_WILDCARD.format(prefix=self.prefix),
                self._on_state,
                1,
            )
        )
        self._unsubs.append(
            await mqtt.async_subscribe(
                self.hass,
                TOPIC_EVENTS_WILDCARD.format(prefix=self.prefix),
                self._on_events,
                1,
            )
        )
        # Config is retained; subscribing gives us the current config per device.
        self._unsubs.append(
            await mqtt.async_subscribe(
                self.hass,
                f"{self.prefix}/+/config",
                self._on_config,
                1,
            )
        )
        self._unsubs.append(
            await mqtt.async_subscribe(
                self.hass,
                TOPIC_PROBE_EVENTS_WILDCARD.format(prefix=PROBE_PREFIX),
                self._on_probe_events,
                1,
            )
        )

    async def async_close(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()

    # --------------------------------------------------------------- devices
    def _ensure_device(self, device_id: str) -> ThermaConnectDevice:
        if device_id not in self.devices:
            self.devices[device_id] = ThermaConnectDevice(
                device_id=device_id, name=device_id
            )
        return self.devices[device_id]

    def listen(self, listener: DeviceListener) -> Callable[[], None]:
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    def _notify(self, device: ThermaConnectDevice) -> None:
        for listener in list(self._listeners):
            try:
                listener(device)
            except Exception:  # noqa: BLE001 - one bad entity must not stop others
                _LOGGER.exception("ThermaConnect listener failed for %s", device.device_id)

    def _device_from_topic(self, topic: str, create: bool) -> ThermaConnectDevice | None:
        parts = topic.strip("/").split("/")
        # devices/<id>/<kind>
        if len(parts) >= 3 and parts[0] == self.prefix.strip("/"):
            device_id = parts[1]
            if create or device_id in self.devices:
                return self._ensure_device(device_id)
        return None

    # ------------------------------------------------------------- handlers
    @callback
    def _on_state(self, msg: mqtt.Message) -> None:
        payload = _json(msg)
        if payload is None:
            return
        device = self._device_from_topic(msg.topic, create=self.auto_discover)
        if device is None:
            return
        device.apply_state(payload)
        device.touch()
        self._notify(device)

    @callback
    def _on_events(self, msg: mqtt.Message) -> None:
        payload = _json(msg)
        if payload is None:
            return
        device = self._device_from_topic(msg.topic, create=self.auto_discover)
        if device is None:
            return
        device.apply_telemetry(payload)
        device.touch()
        self._notify(device)

    @callback
    def _on_config(self, msg: mqtt.Message) -> None:
        payload = _json(msg)
        if payload is None:
            return
        device = self._device_from_topic(msg.topic, create=self.auto_discover)
        if device is None:
            return
        device.apply_config(payload)
        self._notify(device)

    @callback
    def _on_probe_events(self, msg: mqtt.Message) -> None:
        """RFX probes report under /probes/<id>/events.

        We surface them as channels on a synthetic gateway device keyed by the
        probe id so they appear in HA without extra config.
        """
        payload = _json(msg)
        if payload is None:
            return
        parts = msg.topic.strip("/").split("/")
        if len(parts) < 3:
            return
        probe_id = parts[1]
        gateway_id = payload.get("gatewayId") or probe_id
        device = self._ensure_device(gateway_id)
        device.apply_telemetry(payload)
        device.touch()
        self._notify(device)

    # ------------------------------------------------------------ publishing
    async def async_publish_config(self, device: ThermaConnectDevice) -> None:
        if not device.state_received and not device.channels:
            # The firmware REPLACES its entire config with whatever we send.
            # Publishing a snapshot built from nothing would wipe channels and
            # options this integration does not model (Billows fan, RFX probes).
            _LOGGER.warning(
                "Refusing to publish config for %s: no state received yet. Wait for "
                "the device's first transmit so its real config is cached.",
                device.device_id,
            )
            return
        topic = TOPIC_CONFIG.format(prefix=self.prefix, device_id=device.device_id)
        payload = device.build_config_payload()
        await mqtt.async_publish(self.hass, topic, _dumps(payload), qos=1, retain=True)
        _LOGGER.debug("Published retained config to %s", topic)


def _parse_ids(raw: str | list[str]) -> list[str]:
    if isinstance(raw, list):
        return [s.strip() for s in raw if s.strip()]
    return [s.strip() for s in str(raw).replace(";", ",").split(",") if s.strip()]


def _json(msg: mqtt.Message) -> dict | None:
    import json

    try:
        data = json.loads(msg.payload)
    except (ValueError, TypeError):
        _LOGGER.debug("Non-JSON payload on %s", msg.topic)
        return None
    return data if isinstance(data, dict) else None


def _dumps(obj: dict) -> str:
    import json

    return json.dumps(obj, separators=(",", ":"))
