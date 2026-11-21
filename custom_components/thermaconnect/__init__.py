"""ThermaConnect — ThermoWorks IoT thermometers direct to Home Assistant via MQTT."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .bridge import ThermaConnectBridge
from .const import DOMAIN
from .services import async_setup_services, async_unload_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SWITCH,
    Platform.SELECT,
]

type ThermaConnectConfigEntry = ConfigEntry[ThermaConnectBridge]


async def async_setup_entry(hass: HomeAssistant, entry: ThermaConnectConfigEntry) -> bool:
    """Set up ThermaConnect from a config entry."""
    try:
        import voluptuous  # noqa: F401
    except ImportError as err:  # pragma: no cover - environment guard
        _LOGGER.error(
            "ThermaConnect needs the 'voluptuous' package; install it in the Home "
            "Assistant environment before adding this integration: %s",
            err,
        )
        return False

    if not hass.config_entries.async_entries("mqtt"):
        _LOGGER.error("ThermaConnect requires the MQTT integration to be configured first")
        return False

    bridge = ThermaConnectBridge(hass, entry)
    await bridge.async_setup()
    entry.runtime_data = bridge

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await async_setup_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ThermaConnectConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        bridge: ThermaConnectBridge | None = entry.runtime_data
        if bridge is not None:
            await bridge.async_close()
        if not any(
            e.state == "loaded" and e.entry_id != entry.entry_id
            for e in hass.config_entries.async_entries(DOMAIN)
        ):
            await async_unload_services(hass)
    return unload_ok
