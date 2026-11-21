# ThermoWorks ThermaConnect for Home Assistant

Publish real-time readings from **ThermoWorks IoT thermometers** (NODE, Signals,
RFX Gateway + probes) straight into Home Assistant over **MQTT — no ThermoWorks
cloud required.**

The ThermaConnect firmware is a plain MQTT client: you point it at *your* broker
over Bluetooth during provisioning, and this integration turns the topics it
publishes into Home Assistant devices and entities.

> ⚠️ **Provisioning is done over BLE, not by this integration.** This project
> consumes the MQTT the device emits. Use the ThermoWorks provisioner (or your
> own Web Bluetooth app) to point the device at your broker — see
> [`scripts/provision_device.py`](scripts/provision_device.py).

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
| `/devices/<serial>/state`      | device → HA    | sensors, alarms, connectivity |
| `/devices/<serial>/events`     | device → HA    | temperature / humidity readings |
| `/devices/<serial>/config`     | HA → device    | alarm setpoints, channel enable, units (retained) |
| `/probes/<probeId>/events`     | gateway → HA   | RFX probe telemetry |

Battery NODEs sleep between transmit intervals; entities **restore their last
value** across restarts and report `unavailable` only after a grace window
(2.5× the transmit interval). RFX gateways stay connected and stream live.

---

## Entities created (per device)

| Entity | Type | Notes |
| ------ | ---- | ----- |
| `<channel>` Temperature | sensor | °F/°C from device units |
| `<channel>` Humidity | sensor | only when the channel reports humidity |
| `<channel>` High/Low Alarm | binary_sensor | heat / cold device class |
| `<channel>` High/Low Alarm Setpoint | number | writes retained config |
| `<channel>` Enabled, High/Low Alarm Enabled | switch | config entities |
| Wi-Fi signal, Battery, Firmware | sensor | diagnostics |
| Connected | binary_sensor | asleep vs online (see note) |
| Display units | select | F / C |

---

## Prerequisites

1. **MQTT integration** configured in Home Assistant and connected to a broker
   the devices can reach. (Add-ons like *Mosquitto broker* work fine.)
2. A ThermoWorks IoT device, provisioned to point at that broker over BLE.
3. The device's serial: `T` + 12 hex chars (on the label, or via BLE Device ID).

### Provisioning the device to your broker

Put the device in **SETUP MODE** (hold START 5–10 s until it reads `SETUPMODE`),
connect over BLE, and write these fields — leave unused ones as empty strings:

```
MQTT BROKER URL : mqtt://<broker-ip>      # or mqtts:// for TLS
MQTT BROKER PORT: 1883                     # 8883 for TLS
MQTT USERNAME   : <user>                   # '' if broker allows anonymous
MQTT PASSWORD   : <pass>
MQTT CA CERT    : ''                       # REQUIRED PEM for mqtts/wss, else empty
MQTT CLIENT CERT: ''                       # currently unsupported on NODE
MQTT CLIENT KEY : ''
```

Then write `CONNECT_START`. Watch the BLE *Wi-Fi Connection Status* and *MQTT
Connection Status* characteristics flip to `1`. Run
`python3 scripts/provision_device.py --help` to generate these values correctly.

> **Network note:** battery NODEs only wake on their transmit interval, so after
> provisioning the first message may take up to that interval to appear.

---

## Installation

Home Assistant 2026.11+ ships the **Marketplace** built in (it replaced HACS,
using the same catalog and `hacs.json`). No separate download needed.

### Option A — Marketplace custom repository (before it's in the catalog)
1. Add this repo as a custom repository: **Settings → Devices & Services →
   Marketplace** (three-dot menu top-right) → **Add custom repository**, enter
   this repo URL, category **Integration**.
2. Install **ThermoWorks ThermaConnect**, then restart Home Assistant if asked.

### Option B — Manual
Copy `custom_components/thermaconnect/` into your HA `config/custom_components/`
directory and restart Home Assistant.

> To get listed in the catalog so it appears by search, open a PR adding this
> repo to [`hacs/default`](https://github.com/hacs/default) (integrations list).

---

## Configuration

**Settings → Devices & Services → Add Integration → "ThermoWorks ThermaConnect".**

- **Device serials** — comma-separated list to pre-create entities before the
  first message (optional).
- **Auto-discover** — create a device automatically for any new `/devices/<id>/…`
  topic it sees on the broker (default: on). With this on you can leave the
  serial list empty.
- **Topic prefix** — must match what your devices publish to (firmware default
  `/devices`).

One integration entry manages all devices over the shared MQTT bridge.

---

## Writing settings back to the device

Alarm setpoints, channel enable/disable and display units publish a **complete,
retained** config object. Because the firmware *replaces its entire config* on
receipt:

- Changes apply on the device's **next wake** (immediately for RFX gateways).
- The integration **refuses to publish** until it has seen the device report at
  least once, so it can never wipe channels/options from an empty snapshot.
- For Billows fan or RFX probe config (not modelled as entities), publish your
  own retained JSON to `/devices/<serial>/config`, or extend via the
  `thermaconnect.publish_config` service after seeding state.

---

## Limitations / roadmap
- BLE provisioning is out of scope (no reliable HA-side BLE for sleeping devices).
- Billows fan control and RFX probe config are read/passed-through, not full UI.
- Battery is a status letter (`C`, …), not a percentage — matches the protocol.

## Development
```
python3 -m py_compile custom_components/thermaconnect/*.py
```
Payload parsing is validated against the ThermaConnect README sample state /
telemetry objects. PRs welcome.

## License
MIT
