"""Service to (re)publish a device's retained config on demand."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .bridge import ThermaConnectBridge
from .const import DOMAIN

SERVICE_PUBLISH_CONFIG = "publish_config"

SERVICE_SCHEMA = vol.Schema(
    {vol.Required("device_id"): cv.string}
)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register thermaconnect.publish_config."""

    async def _handle(call: ServiceCall) -> None:
        device_id = call.data["device_id"]
        for entry in hass.config_entries.async_entries(DOMAIN):
            bridge: ThermaConnectBridge | None = getattr(entry, "runtime_data", None)
            if bridge is None:
                continue
            device = bridge.devices.get(device_id)
            if device is not None:
                await bridge.async_publish_config(device)
                return
        raise ValueError(f"Unknown ThermaConnect device: {device_id}")

    hass.services.async_register(
        DOMAIN, SERVICE_PUBLISH_CONFIG, _handle, schema=SERVICE_SCHEMA
    )


async def async_unload_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_PUBLISH_CONFIG):
        hass.services.async_remove(DOMAIN, SERVICE_PUBLISH_CONFIG)
