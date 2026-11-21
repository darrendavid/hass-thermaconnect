"""Constants for the ThermaConnect (ThermoWorks IoT) integration."""

from __future__ import annotations

DOMAIN = "thermaconnect"
MANUFACTURER = "ThermoWorks"

# Config flow / options keys
CONF_DEVICE_IDS = "device_ids"          # comma-separated serials to bootstrap
CONF_AUTO_DISCOVER = "auto_discover"    # create devices for any /devices/+ seen
CONF_TOPIC_PREFIX = "topic_prefix"      # leading "/" kept compatible with firmware
CONF_NAME_PREFIX = "name_prefix"        # optional friendly-name prefix

DEFAULT_TOPIC_PREFIX = "/devices"
DEFAULT_NAME_PREFIX = ""

# MQTT topic templates (firmware contract, see ThermaConnect README)
TOPIC_CONFIG = "{prefix}/{device_id}/config"      # we publish (retained) -> device
TOPIC_STATE = "{prefix}/{device_id}/state"        # device -> us
TOPIC_EVENTS = "{prefix}/{device_id}/events"      # device -> us (telemetry)
TOPIC_STATE_WILDCARD = "{prefix}/+/state"
TOPIC_EVENTS_WILDCARD = "{prefix}/+/events"

# RFX gateways forward probe telemetry on a different tree
PROBE_PREFIX = "/probes"
TOPIC_PROBE_EVENTS = "{prefix}/{probe_id}/events"
TOPIC_PROBE_EVENTS_WILDCARD = "{prefix}/+/events"

# How long after the last message we still call the device "online".
# Battery NODEs sleep between transmit intervals; RFX gateways stay connected.
DEFAULT_OFFLINE_GRACE_MULTIPLIER = 2.5
MIN_OFFLINE_GRACE_SECONDS = 180

# Translation keys for probe sensor types (channel `type` int -> readable name)
CHANNEL_TYPE_NAMES = {
    0: "Pro-Series External (Limited)",
    1: "Humidity",
    2: "Internal Chip Sensor",
    3: "Humidity (AHT)",
    4: "Humidity Temperature (AHT)",
    5: "Pro-Series External Full Range",
    6: "Humidity (SHTC)",
    7: "Humidity Temperature (SHTC)",
    8: "Pro-Series Internal",
}

# Reading `type` letters seen in telemetry/state readings
READING_TEMP = "T"
READING_HUMIDITY = "H"

# Channel status codes -> binary_sensor diagnostic values
CHANNEL_STATUS = {0: "normal", 1: "low_error", 2: "high_error", 3: "no_probe", 4: "disabled"}
