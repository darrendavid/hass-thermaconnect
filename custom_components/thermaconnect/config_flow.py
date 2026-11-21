"""Config flow for ThermaConnect (ThermoWorks IoT over MQTT)."""

from __future__ import annotations

import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.core import callback

from .const import (
    CONF_AUTO_DISCOVER,
    CONF_DEVICE_IDS,
    CONF_NAME_PREFIX,
    CONF_TOPIC_PREFIX,
    DEFAULT_NAME_PREFIX,
    DEFAULT_TOPIC_PREFIX,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# ThermoWorks serials: T + 12 hex chars (see BLE Device ID / README)
SERIAL_RE = re.compile(r"^T[0-9A-Fa-f]{12}$")


class ThermaConnectConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ThermaConnect."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        # The integration is MQTT-driven; require the broker to be set up first.
        mqtt_config_entries = [
            entry
            for entry in self._async_current_entries(include_ignore=False)
            if entry.domain == "mqtt"
        ] or self.hass.config_entries.async_entries("mqtt")
        if not mqtt_config_entries:
            return self.async_abort(reason="mqtt_required")

        if user_input is not None:
            raw_ids = user_input.get(CONF_DEVICE_IDS, "")
            serials = [
                s.strip()
                for s in raw_ids.replace(";", ",").replace("\n", ",").split(",")
                if s.strip()
            ]
            bad = [s for s in serials if not SERIAL_RE.match(s)]
            if bad:
                errors[CONF_DEVICE_IDS] = "invalid_serial"
            else:
                # One integration entry manages all devices (shared MQTT bridge).
                await self.async_set_unique_id("thermaconnect-mqtt")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="ThermoWorks ThermaConnect",
                    data={
                        CONF_DEVICE_IDS: serials,
                        CONF_AUTO_DISCOVER: user_input.get(CONF_AUTO_DISCOVER, True),
                        CONF_TOPIC_PREFIX: user_input.get(
                            CONF_TOPIC_PREFIX, DEFAULT_TOPIC_PREFIX
                        ),
                        CONF_NAME_PREFIX: user_input.get(
                            CONF_NAME_PREFIX, DEFAULT_NAME_PREFIX
                        ),
                    },
                )

        schema = vol.Schema(
            {
                vol.Optional(CONF_DEVICE_IDS, default=""): str,
                vol.Optional(CONF_AUTO_DISCOVER, default=True): bool,
                vol.Optional(CONF_TOPIC_PREFIX, default=DEFAULT_TOPIC_PREFIX): str,
                vol.Optional(CONF_NAME_PREFIX, default=DEFAULT_NAME_PREFIX): str,
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ):  # pragma: no cover - thin wiring
        from .options_flow import ThermaConnectOptionsFlow

        return ThermaConnectOptionsFlow(config_entry)
