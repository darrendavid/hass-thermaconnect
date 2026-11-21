"""Sensor platform: temperatures, humidity, Wi-Fi, battery, firmware."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfTemperature,
    EntityCategory,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .bridge import ThermaConnectBridge
from .const import CONF_NAME_PREFIX, DOMAIN
from .entity import ThermaConnectChannelEntity
from .models import ThermaConnectDevice

UNIT_MAP = {"F": UnitOfTemperature.FAHRENHEIT, "C": UnitOfTemperature.CELSIUS}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    bridge: ThermaConnectBridge = entry.runtime_data
    name_prefix = entry.data.get(CONF_NAME_PREFIX, "") or ""
    seen: set[str] = set()

    def _entities_for(device: ThermaConnectDevice) -> list[SensorEntity]:
        out: list[SensorEntity] = [
            DeviceSignalSensor(bridge, device),
            DeviceBatterySensor(bridge, device),
            DeviceFirmwareSensor(bridge, device),
        ]
        for number in device.channels:
            out.extend(
                [
                    ChannelTemperatureSensor(bridge, device, number),
                    ChannelHumiditySensor(bridge, device, number),
                ]
            )
        return out

    @callback
    def _discover(device: ThermaConnectDevice) -> None:
        new = [e for e in _entities_for(device) if e.unique_id not in seen]
        if not new:
            return
        for e in new:
            seen.add(e.unique_id)
        async_add_entities(new)

    # Existing configured/bootstrap devices now, plus anything seen later.
    for device in list(bridge.devices.values()):
        _discover(device)
    bridge.listen(_discover)


class ChannelTemperatureSensor(ThermaConnectChannelEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = None

    @property
    def uid_suffix(self) -> str:
        return "temperature"

    @property
    def name(self) -> str:
        ch = self.channel
        return ch.label or f"Channel {self._channel} Temperature"

    @property
    def native_value(self) -> float | None:
        return self.channel.value

    @property
    def native_unit_of_measurement(self) -> str | None:
        return UNIT_MAP.get(self.channel.unit or "F", UnitOfTemperature.FAHRENHEIT)

    def _restore_from_state(self, state) -> None:
        try:
            self._restored = float(state.state)
        except (TypeError, ValueError):
            self._restored = None

    @property
    def extra_state_attributes(self) -> dict:
        ch = self.channel
        return {
            "reading_ts": ch.reading_ts,
            "sensor_type": ch.sensor_type,
            "status": ch.status,
        }


class ChannelHumiditySensor(ThermaConnectChannelEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_entity_category = None

    @property
    def uid_suffix(self) -> str:
        return "humidity"

    @property
    def available(self) -> bool:
        return super().available and self.channel.humidity is not None

    @property
    def name(self) -> str:
        ch = self.channel
        return f"{ch.label or f'Channel {self._channel}'} Humidity"

    @property
    def native_value(self) -> float | None:
        return self.channel.humidity


class _DeviceLevelSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, bridge: ThermaConnectBridge, device: ThermaConnectDevice) -> None:
        self._bridge = bridge
        self._device = device
        self._unsub = None
        self._attr_unique_id = (
            f"{DOMAIN}-{device.device_id}-dev-{self.uid_suffix}"
        )

    @property
    def uid_suffix(self) -> str:  # pragma: no cover
        raise NotImplementedError

    @property
    def device_info(self):
        from homeassistant.helpers.device_registry import DeviceInfo
        from .const import MANUFACTURER

        d = self._device
        return DeviceInfo(
            identifiers={(DOMAIN, d.device_id)},
            name=d.name or d.device_id,
            manufacturer=MANUFACTURER,
            model=(d.model or "NODE").title(),
            sw_version=d.firmware,
            serial_number=d.device_id,
        )

    @property
    def available(self) -> bool:
        return self._device.online

    async def async_added_to_hass(self) -> None:
        self._unsub = self._bridge.listen(self._on_update)

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub:
            self._unsub()

    def _on_update(self, device: ThermaConnectDevice) -> None:
        if device.device_id == self._device.device_id:
            self.async_write_ha_state()


class DeviceSignalSensor(_DeviceLevelSensor):
    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_translation_key = "wifi_strength"

    @property
    def uid_suffix(self) -> str:
        return "wifi-strength"

    @property
    def native_value(self) -> int | None:
        return self._device.wifi_strength


class DeviceBatterySensor(_DeviceLevelSensor):
    _attr_translation_key = "battery_status"

    @property
    def uid_suffix(self) -> str:
        return "battery"

    @property
    def native_value(self) -> str | None:
        return self._device.battery


class DeviceFirmwareSensor(_DeviceLevelSensor):
    _attr_translation_key = "firmware"

    @property
    def uid_suffix(self) -> str:
        return "firmware"

    @property
    def native_value(self) -> str | None:
        return self._device.firmware
