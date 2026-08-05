"""Fluval Plant 3.0 BLE light control.

Talks directly to the light's own BLE GATT protocol (reverse-engineered
separately, see fluval_protocol.py), bypassing its onboard schedule so it
self-heals after a power outage without the FluvalSmart app. Connects via
whichever Home Assistant Bluetooth proxy currently has the light in range.

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
from . import fluval_schedule as sched

_LOGGER = logging.getLogger(__name__)

DOMAIN = "fluval"
CONF_MAC_ADDRESS = "mac_address"
CHANNEL_ORDER = ["pink", "blue", "cold_white", "pure_white", "warm_white"]

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
        now = datetime.now()
        minute_of_day = now.hour * 60 + now.minute + now.second / 60
        values = sched.channel_raw_values(minute_of_day)
        any_on = any(v > 0 for v in values.values())

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
                await client.start_notify(proto.NOTIFY_CHAR, lambda *_: None)
                await client.read_gatt_char(proto.KEEPALIVE_CHAR)
                await client.write_gatt_char(
                    proto.HANDSHAKE_CHAR, data=proto.handshake_message(), response=False
                )
                await asyncio.sleep(0.5)

                await client.write_gatt_char(
                    proto.WRITE_CHAR, data=proto.power_message(any_on), response=False
                )
                await asyncio.sleep(0.3)

                msg = proto.brightness_message(*(values[c] for c in CHANNEL_ORDER))
                await client.write_gatt_char(proto.WRITE_CHAR, data=msg, response=False)
                await asyncio.sleep(0.3)

                _LOGGER.info(
                    "Fluval schedule applied: power=%s pink=%d blue=%d cold_white=%d "
                    "pure_white=%d warm_white=%d",
                    any_on,
                    *(values[c] for c in CHANNEL_ORDER),
                )
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
