"""Fluval Plant 3.0 BLE light control.

Talks directly to the light's own BLE GATT protocol (reverse-engineered
separately, see fluval_protocol.py). The light runs its own pro-mode program;
this re-syncs its clock so the program self-heals after a power outage
without the FluvalSmart app. Connects via whichever Home Assistant Bluetooth
proxy currently has the light in range.

Configure your light's MAC address in configuration.yaml:

    fluval:
      mac_address: "AA:BB:CC:DD:EE:FF"
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

import voluptuous as vol
from bleak import BleakClient
from bleak_retry_connector import establish_connection

import homeassistant.helpers.config_validation as cv
from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant, ServiceCall

from . import fluval_protocol as proto

_LOGGER = logging.getLogger(__name__)

DOMAIN = "fluval"
CONF_MAC_ADDRESS = "mac_address"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_MAC_ADDRESS): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    mac_address = config[DOMAIN][CONF_MAC_ADDRESS]

    async def handle_apply_schedule(call: ServiceCall) -> None:
        ble_device = bluetooth.async_ble_device_from_address(
            hass, mac_address, connectable=True
        )
        if ble_device is None:
            _LOGGER.warning(
                "Fluval light %s not currently visible to any Bluetooth proxy",
                mac_address,
            )
            return

        try:
            client = await establish_connection(BleakClient, ble_device, "fluval-light")
        except Exception:
            _LOGGER.exception("Failed to connect to Fluval light")
            return

        try:
            try:
                status: list[bytes] = []
                await client.start_notify(
                    proto.NOTIFY_CHAR, lambda _c, data: status.append(bytes(data))
                )
                await client.read_gatt_char(proto.KEEPALIVE_CHAR)

                # The light runs its own pro-mode program (set in the FluvalSmart
                # app). It has no RTC battery, so after a power loss its clock is
                # wrong and the program runs at the wrong time of day. Re-sync
                # the clock every run, then read state, the same order
                # FluvalSmart uses on connect; the light's own schedule does
                # the rest.
                #
                # Writes use response=False, matching the APK's classic path; a
                # dropped write is harmless because this re-runs every 5 min.
                now = datetime.now()
                await client.write_gatt_char(
                    proto.WRITE_CHAR, data=proto.clock_message(now), response=False
                )
                await asyncio.sleep(0.3)

                await client.write_gatt_char(
                    proto.WRITE_CHAR, data=proto.handshake_message(), response=False
                )
                await asyncio.sleep(0.8)
                # Reply spans several notifications, each separately encrypted.
                state = b"".join(proto._decrypt(c) for c in status)
                _LOGGER.info(
                    "Fluval state: mode=%s raw=%s",
                    proto.MODE_NAMES.get(state[2], hex(state[2])) if len(state) > 2 else "?",
                    state.hex() or "none",
                )

                _LOGGER.info("Fluval clock synced to %s", now.isoformat(timespec="seconds"))
            except Exception:
                # BLE over a marginal-signal proxy connection is expected to drop
                # occasionally; the automation retries every 5 minutes, so log and
                # let the next run correct it rather than surfacing this as an
                # automation error each time it happens.
                _LOGGER.warning(
                    "Fluval schedule write failed this run, will retry next cycle",
                    exc_info=True,
                )
        finally:
            await client.disconnect()

    hass.services.async_register(DOMAIN, "apply_schedule", handle_apply_schedule)
    return True
