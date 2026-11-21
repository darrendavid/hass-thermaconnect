"""Options flow: adjust device list / auto-discovery after setup."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, OptionsFlow, OptionsFlowResult

from .const import (
    CONF_AUTO_DISCOVER,
    CONF_DEVICE_IDS,
    CONF_NAME_PREFIX,
    CONF_TOPIC_PREFIX,
)


class ThermaConnectOptionsFlow(OptionsFlow):
    def __init__(self, config_entry: ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> OptionsFlowResult:
        if user_input is not None:
            serials = [
                s.strip()
                for s in user_input.get(CONF_DEVICE_IDS, "")
                .replace(";", ",")
                .split(",")
                if s.strip()
            ]
            return self.async_create_entry(
                data={
                    CONF_DEVICE_IDS: serials,
                    CONF_AUTO_DISCOVER: user_input.get(CONF_AUTO_DISCOVER, True),
                    CONF_TOPIC_PREFIX: user_input.get(CONF_TOPIC_PREFIX, "/devices"),
                    CONF_NAME_PREFIX: user_input.get(CONF_NAME_PREFIX, ""),
                }
            )

        cur = self._entry.data
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_DEVICE_IDS, default=",".join(cur.get(CONF_DEVICE_IDS, []))
                ): str,
                vol.Optional(
                    CONF_AUTO_DISCOVER, default=cur.get(CONF_AUTO_DISCOVER, True)
                ): bool,
                vol.Optional(
                    CONF_TOPIC_PREFIX,
                    default=cur.get(CONF_TOPIC_PREFIX, "/devices"),
                ): str,
                vol.Optional(
                    CONF_NAME_PREFIX, default=cur.get(CONF_NAME_PREFIX, "")
                ): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
