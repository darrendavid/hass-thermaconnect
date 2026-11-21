"""Binary sensors: per-channel high/low alarm state + device connectivity."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .bridge import ThermaConnectBridge
from .entity import ThermaConnectChannelEntity
from .models import ThermaConnectDevice


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    bridge: ThermaConnectBridge = entry.runtime_data
    seen: set[str] = set()

    def _entities_for(device: ThermaConnectDevice):
        out = [DeviceConnectedBinarySensor(bridge, device)]
        for number in device.channels:
            out.extend(
                [
                    ChannelHighAlarmBinarySensor(bridge, device, number),
                    ChannelLowAlarmBinarySensor(bridge, device, number),
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

    for device in list(bridge.devices.values()):
        _discover(device)
    bridge.listen(_discover)


class ChannelHighAlarmBinarySensor(ThermaConnectChannelEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.HEAT

    @property
    def uid_suffix(self) -> str:
        return "high-alarm"

    @property
    def name(self) -> str:
        ch = self.channel
        return f"{ch.label or f'Channel {self._channel}'} High Alarm"

    @property
    def is_on(self) -> bool | None:
        return self.channel.high_alarming


class ChannelLowAlarmBinarySensor(ThermaConnectChannelEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.COLD

    @property
    def uid_suffix(self) -> str:
        return "low-alarm"

    @property
    def name(self) -> str:
        ch = self.channel
        return f"{ch.label or f'Channel {self._channel}'} Low Alarm"

    @property
    def is_on(self) -> bool | None:
        return self.channel.low_alarming


class DeviceConnectedBinarySensor(BinarySensorEntity):
    """On when the device has reported within its grace window.

    Battery NODEs sleep between transmit intervals, so 'off' here means
    'asleep or offline', not necessarily a fault.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "connectivity"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, bridge: ThermaConnectBridge, device: ThermaConnectDevice) -> None:
        from .const import DOMAIN
        from homeassistant.helpers.device_registry import DeviceInfo
        from .const import MANUFACTURER

        self._bridge = bridge
        self._device = device
        self._unsub = None
        self._attr_unique_id = f"{DOMAIN}-{device.device_id}-dev-connected"
        d = device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, d.device_id)},
            name=d.name or d.device_id,
            manufacturer=MANUFACTURER,
            model=(d.model or "NODE").title(),
            sw_version=d.firmware,
            serial_number=d.device_id,
        )

    @property
    def is_on(self) -> bool:
        return self._device.online

    async def async_added_to_hass(self) -> None:
        self._unsub = self._bridge.listen(self._on_update)

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub:
            self._unsub()

    def _on_update(self, device: ThermaConnectDevice) -> None:
        if device.device_id == self._device.device_id:
            self.async_write_ha_state()
