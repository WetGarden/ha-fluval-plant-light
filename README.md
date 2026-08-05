# Home Assistant: Fluval Plant Light Schedule Enforcer

Fixes a well-known Fluval Plant 3.0 problem: **the light's onboard BLE-programmed
schedule is lost on any power interruption**, and it stays dark (or stuck at
whatever brightness it was at) until you manually reprogram it through the
FluvalSmart app. This integration bypasses the light's own clock entirely —
Home Assistant computes what the brightness *should* be for the current time
of day and pushes it directly over Bluetooth every few minutes, so a power
blip corrects itself automatically instead of requiring you to notice and fix
it by hand.

This talks directly to the light's BLE GATT protocol (reverse-engineered by
[TooManyFrogs on plantedtank.net](https://www.plantedtank.net/), "Reverse
Engineering the Fluval Plant 3.0 BLE protocol", 2022) — it does not use or
need the FluvalSmart app at all once set up.

**Tested against**: Fluval Plant 3.0 specifically. The protocol details
(command bytes, encryption wrapper, 5-channel layout) may or may not apply
unmodified to other Fluval light models — if you try this on a different
model and it works (or needs tweaking), please open an issue or PR.

## How it works

- A custom Home Assistant integration (`custom_components/fluval`) registers
  a service, `fluval.apply_schedule`, that connects to the light over BLE and
  writes the correct power/brightness for the current time.
- An automation calls that service every 5 minutes and on Home Assistant
  startup — the same "re-assert state, don't just wait for an edge"
  approach used for things like smart plugs with unreliable cloud scheduling.
- Your schedule (the actual ramp-up/hold/ramp-down times and percentages you
  want) lives in a plain Python file you edit once, `fluval_schedule.py` —
  nothing reads this back from the FluvalSmart app automatically.

## Prerequisites

- Home Assistant with the core **Bluetooth** integration enabled (it is by
  default in most installs).
- **Your light needs to be in Bluetooth range of something Home Assistant can
  use as a scanner** — either HA's own local Bluetooth adapter, or an
  [ESPHome Bluetooth proxy](https://esphome.io/components/bluetooth_proxy.html)
  (a cheap ESP32 board flashed with ESPHome's Bluetooth proxy firmware,
  placed near the tank) if your HA server isn't close enough. Aquarium water
  itself attenuates 2.4GHz signal significantly, so if your server is more
  than a room away, budget for needing a proxy — this is a common enough
  situation that it's worth planning for from the start rather than
  discovering it after installing.

## Installation

1. Copy the `custom_components/fluval/` folder from this repo into your Home
   Assistant config directory, so you end up with
   `<config>/custom_components/fluval/__init__.py` etc.
2. Find your light's Bluetooth MAC address. The easiest way is the
   FluvalSmart app's device list (it's shown alongside your light's name),
   or by scanning for it directly if you have a way to do that.
3. Add this to your `configuration.yaml`:

   ```yaml
   fluval:
     mac_address: "AA:BB:CC:DD:EE:FF"
   ```

4. **Edit `custom_components/fluval/fluval_schedule.py`** to match your own
   light's actual schedule — the file has an example curve in it and
   explains the format in its header comment. This is the one file you're
   expected to customize per-install; everything else should work as-is.
5. Add an automation (`automations.yaml` or via the UI) to call the service
   on a recurring basis:

   ```yaml
   - id: 'fluval_schedule_enforce'
     alias: 'Fluval Plant Light - enforce schedule'
     trigger:
       - platform: time_pattern
         minutes: '/5'
       - platform: homeassistant
         event: start
     action:
       - service: fluval.apply_schedule
   ```

6. Restart Home Assistant (custom components with a plain `async_setup` need
   a full restart to be picked up — just being present in
   `custom_components/` isn't enough on its own).

## Troubleshooting

- **"Service not found" when the automation runs**: double check
  `fluval:` (with your `mac_address:`) is actually present in
  `configuration.yaml` — a component like this one does nothing at all,
  silently, if it's not referenced there, even if the files are in place.
- **GATT error "Write not permitted"**: this integration already writes
  using "Write Without Response" (`response=False`), which is what the real
  hardware expects — if you're modifying the protocol code, note that
  `response=True` fails immediately against the real device.
- **Occasional GATT error 133 / connection drops**: normal over BLE,
  especially if your light's signal is marginal at the proxy/adapter hearing
  it. The integration already catches this and logs a warning instead of
  surfacing an automation error — the next 5-minute run self-corrects.
- **No `Fluval schedule applied: ...` line ever showing in your log**: Home
  Assistant's default log level often doesn't include `INFO`. Add this to
  `configuration.yaml` to see confirmation of every successful run:

  ```yaml
  logger:
    logs:
      custom_components.fluval: info
  ```

## License

MIT — see `LICENSE`.
