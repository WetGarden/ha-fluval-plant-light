# Home Assistant: Fluval Plant Light Clock Sync

> **Disclosure:** I used [Claude](https://claude.ai) (Anthropic's AI assistant)
> to help me create and troubleshoot this integration. It's shared as-is in
> case it's useful to someone else. **Don't expect much, if any, support**:
> issues and PRs may go unanswered.

Fixes a common Fluval Plant 3.0 problem: **after a power interruption the
light stays dark (or runs at the wrong times) until you open the FluvalSmart
app.** The light has no clock battery, so a power loss resets its clock. The
Auto/Pro schedule you programmed is still stored on the light, but it now runs
against the wrong time of day. Opening the app fixes it only because the app
sets the clock when it connects.

This integration does the same thing automatically: Home Assistant connects to
the light over Bluetooth every few minutes and sets its clock. Your schedule
stays on the light and is still edited in the FluvalSmart app as usual.

It talks directly to the light's BLE GATT protocol, reverse-engineered by
[TooManyFrogs on plantedtank.net](https://www.plantedtank.net/) ("Reverse
Engineering the Fluval Plant 3.0 BLE protocol", 2022). The clock command and
the characteristic layout come from
[MrMooreUK/fluvalble](https://github.com/MrMooreUK/fluvalble), a much more
complete Fluval integration that is worth looking at if you want full control
(power, channels, modes) rather than just clock sync.

**Tested against**: one Fluval Plant 3.0 in Pro mode. Other Fluval models may
or may not use the same protocol.

## How it works

- A custom Home Assistant integration (`custom_components/fluval`) registers
  a service, `fluval.apply_schedule`, that connects to the light over BLE,
  sets its clock to Home Assistant's local time, and reads back its state.
- An automation calls that service every 5 minutes and on Home Assistant
  startup, so the clock is corrected within a few minutes of power returning.
- It sends no power, brightness or mode commands, so it never overrides the
  schedule you set in the app.

## Upgrading from 1.x

Version 1.x tried to enforce a schedule from Home Assistant by sending
power/brightness commands. Those commands were written to the wrong BLE
characteristic (`1002`, which is notify-only) and never reached the light, so
1.x never actually worked. 2.0 writes to the correct one (`1001`) and only
syncs the clock. `fluval_schedule.py` is gone; set your schedule in the
FluvalSmart app instead. The service name and automation are unchanged.

## Prerequisites

- Home Assistant with the core **Bluetooth** integration enabled (it is by
  default in most installs).
- **Your light needs to be in Bluetooth range of something Home Assistant can
  use as a scanner**: either HA's own Bluetooth adapter, or an
  [ESPHome Bluetooth proxy](https://esphome.io/components/bluetooth_proxy.html)
  (a cheap ESP32 board placed near the tank). Aquarium water attenuates
  2.4GHz signal significantly, so if your server is more than a room away,
  plan on needing a proxy.
- The light set to **Auto or Pro mode** in the FluvalSmart app, with the
  schedule you want.

## Installation

1. Copy the `custom_components/fluval/` folder from this repo into your Home
   Assistant config directory, so you end up with
   `<config>/custom_components/fluval/__init__.py` etc.
2. Find your light's Bluetooth MAC address. The easiest way is the
   FluvalSmart app's device list (it's shown alongside your light's name).
3. Add this to your `configuration.yaml`:

   ```yaml
   fluval:
     mac_address: "AA:BB:CC:DD:EE:FF"
   ```

4. Add an automation (`automations.yaml` or via the UI) to call the service
   on a recurring basis:

   ```yaml
   - id: 'fluval_schedule_enforce'
     alias: 'Fluval Plant Light - sync clock'
     trigger:
       - platform: time_pattern
         minutes: '/5'
       - platform: homeassistant
         event: start
     action:
       - service: fluval.apply_schedule
   ```

5. Restart Home Assistant (custom components with a plain `async_setup` need
   a full restart to be picked up; being present in `custom_components/`
   isn't enough on its own).

To test it, close the FluvalSmart app, unplug the light for 10 seconds during
a time your schedule has it on, and plug it back in. It should light up
within 5 minutes without opening the app.

## Troubleshooting

- **"Service not found" when the automation runs**: check that `fluval:`
  (with your `mac_address:`) is present in `configuration.yaml`. A component
  like this one does nothing at all, silently, if it's not referenced there.
- **Occasional GATT error 133 / connection drops**: normal over BLE,
  especially when the light's signal is marginal at the proxy. The
  integration logs a warning and the next 5-minute run tries again.
- **The FluvalSmart app can't connect**: the light accepts one Bluetooth
  connection at a time. Home Assistant only holds it for about a second every
  5 minutes, so retry after a few seconds.
- **No `Fluval clock synced to ...` lines in your log**: Home Assistant's
  default log level often hides `INFO`. Add this to `configuration.yaml`:

  ```yaml
  logger:
    logs:
      custom_components.fluval: info
  ```

  Each run then logs the clock it set and a `Fluval state: mode=...` line
  with the light's reported mode and raw schedule.

## License

MIT, see `LICENSE`.
