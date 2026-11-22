# ThermoWorks ThermaConnect for Home Assistant

Publish real-time readings from **ThermoWorks IoT thermometers** (NODE, Signals,
RFX Gateway + probes) straight into Home Assistant over **MQTT — no ThermoWorks
cloud required.**

The ThermaConnect firmware is a plain MQTT client: during provisioning you point
it at *your* broker over Bluetooth, and this integration turns the topics it
publishes into Home Assistant devices and entities.

> ⚠️ **Provisioning is done over BLE, not by this integration.** This project
> consumes the MQTT the device emits. You use the ThermoWorks web provisioner to
> point the device at your broker — full walkthrough below.

---

## How it works

```
ThermoWorks NODE ──(BLE: enter broker + Wi-Fi creds once)──►  your MQTT broker
        │                                                            │
        │  on each wake (transmit interval), the device:             │
        │   • SUBSCRIBE /devices/<serial>/config  ◄── retained config│
        │   • PUBLISH   /devices/<serial>/state                      │
        │   • PUBLISH   /devices/<serial>/events  (telemetry) ──────►├──► Home Assistant
        ▼                                                            │
     (sleeps; RFX gateways stay connected)                    this integration
```

| Topic                          | Direction      | Used by |
| ------------------------------ | -------------- | ------- |
| `/devices/<serial>/state`      | device → HA    | sensors, alarms, battery, connectivity |
| `/devices/<serial>/events`     | device → HA    | temperature / humidity readings |
| `/devices/<serial>/config`     | HA → device    | alarm setpoints, channel enable, units, transmit interval (retained) |
| `/probes/<probeId>/events`     | gateway → HA   | RFX probe telemetry |

Battery NODEs sleep between transmit intervals; entities **restore their last
value** across restarts and report `unavailable` only after a grace window
(2.5× the transmit interval). RFX gateways stay connected and stream live.

---

## Prerequisites

1. **An MQTT broker** the device can reach (e.g. the Mosquitto add-on, or a
   Mosquitto container). Note its LAN IP, e.g. `10.0.1.20`.
2. **The MQTT integration** configured in Home Assistant and connected to that
   same broker (Settings → Devices & Services → MQTT).
3. **A broker user for the device** (if your broker isn't anonymous). Give each
   device its own user so you can revoke it independently.
4. A ThermoWorks IoT device and **its serial**: `T` + 12 hex chars
   (on the label, or shown as the BLE Device ID). Example: `TB0A732CA3ECC`.
5. A **Bluetooth-capable browser** (see the provisioning step) on the same LAN
   as the broker.

---

## Provisioning the device to your broker (step by step)

This is the part that gets people stuck, so it's spelled out fully.

### 1. Put the device in SETUP MODE
Hold the **START** button for **5–10 seconds** until the display reads
**`SETUPMODE`**. The device is now advertising over BLE.

### 2. Open the provisioner in a Web Bluetooth browser
**URL:** <https://thermoworks-iot-provisioning.web.app/>

Web Bluetooth is **not** available everywhere. Use:

| Platform | Browser that works |
| -------- | ------------------ |
| Desktop (Win/Mac/Linux) | **Chrome** or **Edge** |
| Android | **Chrome** (not Firefox, not an in-app browser) |
| iPhone / iPad | **Bluefy** (free App Store browser) — Safari never works |

If you see *"Bluetooth is not supported in this browser"*, you're on Safari,
Firefox, or an in-app WebView — switch to one of the browsers above. A headless
server (e.g. your HA host) has no Bluetooth and can never do this step.

### 3. Connect to the device
Tap to scan, then pick the device (its BLE name is usually the model, e.g.
`NODE`). If the scan finds nothing, confirm the display still says `SETUPMODE`.

### 4. Enter the Wi-Fi and MQTT fields
Send **all** fields; unused ones must be **empty strings** (they overwrite prior
provisioning).

| Field | Value | Notes |
| ----- | ----- | ----- |
| Wi-Fi SSID | your IoT Wi-Fi name | ≤32 chars |
| Wi-Fi Password | its password | ≤64 chars |
| MQTT Broker URL | `mqtt://10.0.1.20` | `mqtts://` for TLS |
| MQTT Broker Port | `1883` | `8883` for TLS |
| MQTT Username | `thermoworks-node` | empty if broker is anonymous |
| MQTT Password | *(the user's password)* | |
| MQTT CA Cert | *(empty)* | **required** PEM for `mqtts://`/`wss://`, else empty |
| MQTT Client Cert | *(empty)* | unsupported on NODE |
| MQTT Client Key | *(empty)* | unsupported on NODE |

**Scheme rules (the device enforces these):**
- `mqtt://` or `ws://` → CA cert **must be empty**.
- `mqtts://` or `wss://` → CA cert **is required** (the device refuses TLS without it).

To print a correct field sheet (and validate the scheme rules) run:

```
python3 scripts/provision_device.py \
    --broker mqtt://10.0.1.20 --port 1883 \
    --ssid "MyIoT-SSID" --wifi-pass "wifipass" \
    --username thermoworks-node --password "<broker-pass>"
```

### 5. Send `CONNECT_START`
Write `CONNECT_START` to the Commands characteristic. Watch the BLE
**Wi-Fi Connection Status** and **MQTT Connection Status** characteristics flip
to **`1`** — that means the device reached both your Wi-Fi and your broker.

### 6. Verify it reached the broker
On the broker host, watch for the device connecting and publishing:

```
# subscribe to everything for your device (shows live state/events)
mosquitto_sub -h <broker-ip> -u <user> -P <pass> -t "/devices/<serial>/#" -v
```

You should see `/devices/<serial>/state` and `/devices/<serial>/events` payloads.

> **Network notes**
> - The phone/laptop doing provisioning must be on the **same LAN/VLAN** as the
>   broker if the broker IP is private (e.g. `10.0.1.20`) — not on mobile data.
> - Battery NODEs only wake on their transmit interval, so after provisioning the
>   first message may take up to that interval to appear.

---

## Install the integration

Home Assistant 2026.11+ ships the **Marketplace** built in (it replaced HACS,
using the same catalog and `hacs.json`). No separate download needed.

### Option A — Marketplace custom repository
1. **Settings → Devices & Services → Marketplace** (three-dot menu top-right) →
   **Add custom repository**, enter this repo URL, category **Integration**.
2. Install **ThermoWorks ThermaConnect**, then restart Home Assistant if asked.

### Option B — Manual
Copy `custom_components/thermaconnect/` into your HA `config/custom_components/`
directory and restart Home Assistant.

> To get listed in the catalog so it appears by search, open a PR adding this
> repo to [`hacs/default`](https://github.com/hacs/default) (integrations list).

---

## Add the integration to Home Assistant

**Settings → Devices & Services → Add Integration → "ThermoWorks ThermaConnect".**

- **Device serials** — comma-separated list to pre-create entities before the
  first message (optional).
- **Auto-discover** — create a device automatically for any new `/devices/<id>/…`
  topic it sees on the broker (default: on). With this on you can leave the
  serial list empty.
- **Topic prefix** — must match what your devices publish to (firmware default
  `/devices`).

One integration entry manages all devices over the shared MQTT bridge. Custom
integrations only load at startup — if you just installed it and see nothing,
**restart Home Assistant** first.

---

## Entities created (per device)

| Entity | Type | Notes |
| ------ | ---- | ----- |
| `<channel>` Temperature | sensor | °F/°C from device units |
| `<channel>` Humidity | sensor | only when the channel reports humidity |
| `<channel>` High/Low Alarm | binary_sensor | heat / cold device class |
| `<channel>` High/Low Alarm Setpoint | number | writes retained config |
| `<channel>` Enabled, High/Low Alarm Enabled | switch | config entities |
| Battery level | sensor | percentage (NODE); charging flag as attribute |
| Battery | sensor | status letter (Signals) |
| Wi-Fi signal | sensor | RSSI dBm (NODE) or % (Signals), auto-detected |
| Firmware | sensor | diagnostics |
| Connected | binary_sensor | asleep vs online (see note) |
| Display units | select | F / C |

The integration parses **both** the NODE and Signals payload shapes (they
differ: NODE sends battery as an integer %, Wi-Fi as raw RSSI, channel numbers
as strings, and readings arrive on `/events`).

---

## Writing settings back to the device

Alarm setpoints, channel enable/disable and display units publish a **complete,
retained** config object. Because the firmware *replaces its entire config* on
receipt:

- Changes apply on the device's **next wake** (immediately for RFX gateways).
- The integration **refuses to publish** until it has seen the device report at
  least once, so it can never wipe channels/options from an empty snapshot.
- It caches the device's own config (including `transmitIntervalInSeconds`), so
  editing one alarm won't reset the others.
- **Avoid changing settings on the device itself** after HA has cached state —
  a later HA write rebuilds the whole config from its cache and can revert
  device-side edits. Make changes through HA.
- For Billows fan or RFX probe config (not modelled as entities), publish your
  own retained JSON to `/devices/<serial>/config`, or extend via the
  `thermaconnect.publish_config` service after seeding state.

### Changing the transmit interval
The device reads `transmitIntervalInSeconds` from its retained config. Publish a
**complete, valid** config with the new value (build it in code and JSON-validate
it — a malformed payload silently fails and a partial one can drop settings), and
the device adopts it on its next wake. A very low value may be clamped to a
firmware floor; confirm by watching consecutive broker-connect timestamps.

---

## Limitations / roadmap
- BLE provisioning is out of scope (no reliable HA-side BLE for sleeping devices).
- Billows fan control and RFX probe config are read/passed-through, not full UI.
- A NODE sleeps between transmits regardless of how it's powered — "plugged in"
  does not make it stream live. For continuous streaming use an RFX gateway.

## Development
```
python3 -m py_compile custom_components/thermaconnect/*.py
```
Payload parsing is validated against real ThermaConnect state / telemetry
objects from a live NODE and the vendor README samples. PRs welcome.

## License
MIT
