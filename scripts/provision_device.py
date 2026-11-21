#!/usr/bin/env python3
"""Generate the exact BLE provisioning values for a ThermoWorks NODE.

ThermaConnect devices are configured over Bluetooth Low Energy while in SETUP
MODE (hold START 5-10s until the display reads SETUPMODE). This script does NOT
talk to the device — it prints the field values you type into a BLE tool such as
the ThermoWorks test provisioner (https://thermoworks-iot-provisioning.web.app/)
or your own Web Bluetooth app.

Device contract (ThermaConnect README):
  - scheme mqtt:// or ws://  -> CA cert MUST be empty, auth = user/pass or none
  - scheme mqtts:// or wss://-> CA cert REQUIRED
  - send ALL fields; unused ones as empty string (overwrites prior provisioning)

Examples
--------
Plaintext broker on the LAN with username/password auth:

  ./provision_device.py --broker mqtt://10.0.1.20 --port 1883 \
      --ssid MyWiFi --wifi-pass secret --username nodeuser --password nodepass

TLS broker (paste/print your CA PEM):

  ./provision_device.py --broker mqtts://mqtt.example.com --port 8883 \
      --ssid MyWiFi --wifi-pass secret --ca-file ca.crt \
      --username nodeuser --password nodepass
"""
from __future__ import annotations

import argparse
import sys


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--broker", required=True, help="scheme://host, e.g. mqtt://10.0.1.20")
    p.add_argument("--port", type=int, default=1883, help="1883 mqtt / 8883 mqtts (default 1883)")
    p.add_argument("--ssid", required=True, help="Wi-Fi SSID (<=32 chars)")
    p.add_argument("--wifi-pass", required=True, help="Wi-Fi password (<=64 chars)")
    p.add_argument("--username", default="", help="MQTT username ('' = no user/pass auth)")
    p.add_argument("--password", default="", help="MQTT password")
    p.add_argument("--ca-file", default="", help="Path to CA PEM (required for mqtts/wss)")
    args = p.parse_args()

    scheme = args.broker.split("://", 1)[0].lower()
    secure = scheme in ("mqtts", "wss")
    if not secure and scheme not in ("mqtt", "ws"):
        print(f"ERROR: unsupported scheme '{scheme}' (use mqtt/mqtts/ws/wss)", file=sys.stderr)
        return 2

    ca = ""
    if args.ca_file:
        with open(args.ca_file, "r", encoding="utf-8") as fh:
            ca = fh.read().strip()
    if secure and not ca:
        print("ERROR: mqtts/wss requires --ca-file (device rejects TLS without a CA cert)", file=sys.stderr)
        return 2
    if not secure and ca:
        print("WARN: CA cert provided but scheme is plaintext; device expects an EMPTY CA cert", file=sys.stderr)

    fields = {
        "WIFI SSID": args.ssid,
        "WIFI PASSWORD": args.wifi_pass,
        "MQTT BROKER URL": args.broker,
        "MQTT BROKER PORT": str(args.port),
        "MQTT USERNAME": args.username,          # '' clears
        "MQTT PASSWORD": args.password,          # '' clears
        "MQTT CA CERT": ca,                      # '' for plaintext
        "MQTT CLIENT CERT": "",                  # currently unavailable on NODE
        "MQTT CLIENT KEY": "",                   # currently unavailable on NODE
    }

    print("Write these to the device via BLE (SETUP MODE), then send CONNECT_START:\n")
    width = max(len(k) for k in fields)
    for k, v in fields.items():
        shown = v if "\n" not in v and len(v) <= 60 else ("<PEM %d bytes>" % len(v) if "CERT" in k or "KEY" in k else v)
        print(f"  {k:<{width}} : {shown!r}")
    print("\nThen write: CONNECT_START   (to the Commands characteristic)")
    print("Watch BLE: Wifi Connection Status -> '1', MQTT Connection Status -> '1'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
