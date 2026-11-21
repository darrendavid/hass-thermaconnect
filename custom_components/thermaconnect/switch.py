"""Switch entities: enable/disable channels and high/low alarms."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
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
        out = []
        for number in device.channels:
            out.extend(
                [
                    ChannelEnabledSwitch(bridge, device, number),
                    ChannelHighAlarmEnabledSwitch(bridge, device, number),
                    ChannelLowAlarmEnabledSwitch(bridge, device, number),
                ]
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


class _ChannelSwitch(ThermaConnectChannelEntity, SwitchEntity):
    _attr_entity_category = EntityCategory.CONFIG

    async def _publish(self) -> None:
        await self._bridge.async_publish_config(self._device)
        self.async_write_ha_state()


class ChannelEnabledSwitch(_ChannelSwitch):
    @property
    def uid_suffix(self) -> str:
        return "enabled"

    @property
    def name(self) -> str:
        ch = self.channel
        return f"{ch.label or f'Channel {self._channel}'} Enabled"

    @property
    def is_on(self) -> bool:
        return self.channel.enabled

    async def async_turn_on(self, **kwargs) -> None:
        self.channel.enabled = True
        await self._publish()

    async def async_turn_off(self, **kwargs) -> None:
        self.channel.enabled = False
        await self._publish()


class ChannelHighAlarmEnabledSwitch(_ChannelSwitch):
    @property
    def uid_suffix(self) -> str:
        return "high-alarm-enabled"

    @property
    def name(self) -> str:
        ch = self.channel
        return f"{ch.label or f'Channel {self._channel}'} High Alarm Enabled"

    @property
    def is_on(self) -> bool | None:
        return self.channel.high_alarm_enabled

    async def async_turn_on(self, **kwargs) -> None:
        self.channel.high_alarm_enabled = True
        await self._publish()

    async def async_turn_off(self, **kwargs) -> None:
        self.channel.high_alarm_enabled = False
        await self._publish()


class ChannelLowAlarmEnabledSwitch(_ChannelSwitch):
    @property
    def uid_suffix(self) -> str:
        return "low-alarm-enabled"

    @property
    def name(self) -> str:
        ch = self.channel
        return f"{ch.label or f'Channel {self._channel}'} Low Alarm Enabled"

    @property
    def is_on(self) -> bool | None:
        return self.channel.low_alarm_enabled

    async def async_turn_on(self, **kwargs) -> None:
        self.channel.low_alarm_enabled = True
        await self._publish()

    async def async_turn_off(self, **kwargs) -> None:
        self.channel.low_alarm_enabled = False
        await self._publish()
