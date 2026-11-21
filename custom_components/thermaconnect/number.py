"""Number entities: high/low alarm setpoints.

The device only receives these when it wakes and subscribes to its retained
config topic, so writes are published as a retained full-config update; they
take effect on the next transmit interval (immediately for RFX gateways).
"""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .bridge import ThermaConnectBridge
from .entity import ThermaConnectChannelEntity
from .models import ThermaConnectDevice

UNIT_MAP = {"F": UnitOfTemperature.FAHRENHEIT, "C": UnitOfTemperature.CELSIUS}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    bridge: ThermaConnectBridge = entry.runtime_data
    seen: set[str] = set()

    def _entities_for(device: ThermaConnectDevice):
        out = []
        for number in device.channels:
            out.extend(
                [ChannelHighAlarmSetpoint(bridge, device, number),
                 ChannelLowAlarmSetpoint(bridge, device, number)]
            )
        return out

    @callback
    def _discover(device: ThermaConnectDevice) -> None:
        new = [e for e in _entities_for(device) if e.unique_id not in seen]
        for e in new:
            seen.add(e.unique_id)
        if new:
            async_add_entities(new)

    for device in list(bridge.devices.values()):
        _discover(device)
    bridge.listen(_discover)


class _AlarmSetpoint(ThermaConnectChannelEntity, NumberEntity):
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = -50
    _attr_native_max_value = 572
    _attr_native_step = 1

    @property
    def native_unit_of_measurement(self) -> str:
        return UNIT_MAP.get(self.channel.unit or "F", UnitOfTemperature.FAHRENHEIT)

    async def async_set_native_value(self, value: float) -> None:
        self._apply(value)
        await self._bridge.async_publish_config(self._device)
        self.async_write_ha_state()


class ChannelHighAlarmSetpoint(_AlarmSetpoint):
    @property
    def uid_suffix(self) -> str:
        return "high-alarm-setpoint"

    @property
    def name(self) -> str:
        ch = self.channel
        return f"{ch.label or f'Channel {self._channel}'} High Alarm Setpoint"

    @property
    def native_value(self) -> float | None:
        return self.channel.high_alarm_value

    def _apply(self, value: float) -> None:
        ch = self.channel
        ch.high_alarm_value = value
        if ch.high_alarm_enabled is None:
            ch.high_alarm_enabled = True


class ChannelLowAlarmSetpoint(_AlarmSetpoint):
    @property
    def uid_suffix(self) -> str:
        return "low-alarm-setpoint"

    @property
    def name(self) -> str:
        ch = self.channel
        return f"{ch.label or f'Channel {self._channel}'} Low Alarm Setpoint"

    @property
    def native_value(self) -> float | None:
        return self.channel.low_alarm_value

    def _apply(self, value: float) -> None:
        ch = self.channel
        ch.low_alarm_value = value
        if ch.low_alarm_enabled is None:
            ch.low_alarm_enabled = True
