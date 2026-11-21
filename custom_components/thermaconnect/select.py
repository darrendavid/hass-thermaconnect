"""Select entity: device display units (C/F). Published via retained config."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .bridge import ThermaConnectBridge
from .const import DOMAIN
from .models import ThermaConnectDevice


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    bridge: ThermaConnectBridge = entry.runtime_data
    seen: set[str] = set()

    @callback
    def _discover(device: ThermaConnectDevice) -> None:
        entity = DisplayUnitsSelect(bridge, device)
        if entity.unique_id in seen:
            return
        seen.add(entity.unique_id)
        async_add_entities([entity])

    for device in list(bridge.devices.values()):
        _discover(device)
    bridge.listen(_discover)


class DisplayUnitsSelect(SelectEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "display_units"
    _attr_options = ["F", "C"]
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, bridge: ThermaConnectBridge, device: ThermaConnectDevice) -> None:
        from homeassistant.helpers.device_registry import DeviceInfo
        from .const import MANUFACTURER

        self._bridge = bridge
        self._device = device
        self._unsub = None
        self._attr_unique_id = f"{DOMAIN}-{device.device_id}-dev-display-units"
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
    def current_option(self) -> str | None:
        return self._device.display_units

    async def async_select_option(self, option: str) -> None:
        self._device.display_units = option
        await self._bridge.async_publish_config(self._device)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        self._unsub = self._bridge.listen(self._on_update)

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub:
            self._unsub()

    def _on_update(self, device: ThermaConnectDevice) -> None:
        if device.device_id == self._device.device_id:
            self.async_write_ha_state()
