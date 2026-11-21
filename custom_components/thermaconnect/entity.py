"""Entity base classes shared by all ThermaConnect platforms."""

from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import UNDEFINED

from .bridge import ThermaConnectBridge
from .const import DOMAIN, MANUFACTURER
from .models import ChannelSnapshot, ThermaConnectDevice


class ThermaConnectChannelEntity(RestoreEntity):
    """One entity bound to (device, channel). Survives restarts via restore_state."""

    _attr_has_entity_name = True

    def __init__(
        self, bridge: ThermaConnectBridge, device: ThermaConnectDevice, channel: int
    ) -> None:
        self._bridge = bridge
        self._device = device
        self._channel = channel
        self._unsub = None
        ch_label = f"Channel {channel}"
        self._attr_translation_key = getattr(self, "_attr_translation_key", None)
        self._attr_name = UNDEFINED if self._attr_translation_key else ch_label
        # unique_id must be stable across restarts and independent of labels.
        self._attr_unique_id = (
            f"{DOMAIN}-{device.device_id}-ch{channel}-{self.uid_suffix}"
        )

    @property
    def uid_suffix(self) -> str:  # pragma: no cover - overridden
        raise NotImplementedError

    @property
    def channel(self) -> ChannelSnapshot:
        return self._device.channel(self._channel)

    @property
    def available(self) -> bool:
        return self._device.online

    @property
    def device_info(self) -> DeviceInfo:
        d = self._device
        return DeviceInfo(
            identifiers={(DOMAIN, d.device_id)},
            name=d.name or d.device_id,
            manufacturer=MANUFACTURER,
            model=(d.model or "NODE").title(),
            sw_version=d.firmware,
            serial_number=d.device_id,
            configuration_url=None,
        )

    # -------------------------------------------------------------- lifecycle
    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._unsub = self._bridge.listen(self._on_device_update)
        # Restore the last known value so the UI is not blank until the next
        # transmit interval (battery NODEs can be asleep for a long time).
        if (state := await self.async_get_last_state()) is not None:
            self._restore_from_state(state)

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub is not None:
            self._unsub()
            self._unsub = None

    def _on_device_update(self, device: ThermaConnectDevice) -> None:
        if device.device_id == self._device.device_id:
            self.async_write_ha_state()

    def _restore_from_state(self, state) -> None:
        """Subclasses with a cached native value override this."""
