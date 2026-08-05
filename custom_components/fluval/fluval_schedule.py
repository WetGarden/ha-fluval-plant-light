"""EDIT THIS FILE to match your own light's schedule.

The curves below are an EXAMPLE only. Set them to whatever your FluvalSmart
app is currently programmed to do: open the app, look at each channel's
ramp/hold points, and translate them into (minute_of_day, percent) pairs
below. Nothing reads your schedule back from the app automatically - this
file is the single source of truth once you're relying on it instead of the
app.

Format: each curve is a list of (minute_of_day, percent_0_to_100) points,
covering the full 0-1440 minute day, in order. Between two points, the value
is linearly interpolated (a straight ramp). To hold a flat value between two
times, repeat that percent at both the start and end minute of the hold.

Example curve below: off -> ramp up 09:30-10:00 to 100% -> full until 18:00
-> ramp down 18:00-18:30 -> off. Edit the channel names/curves to match your
own light's actual channel set and schedule.
"""

_EXAMPLE_MAIN_CURVE = [(0, 0), (570, 0), (600, 100), (1080, 100), (1110, 0), (1440, 0)]

# Example: a channel with an extra dim "moonlight" plateau before going dark.
_EXAMPLE_MOONLIGHT_CURVE = [
    (0, 0),
    (570, 0),
    (600, 100),
    (1080, 100),
    (1110, 10),
    (1320, 10),
    (1350, 0),
    (1440, 0),
]

# Fluval Plant 3.0 has 5 channels: pink, blue, cold_white, pure_white,
# warm_white. If your model has a different channel set, this dict's keys
# must match the channel names used in __init__.py's CHANNEL_ORDER.
CHANNEL_CURVES = {
    "pink": _EXAMPLE_MAIN_CURVE,
    "blue": _EXAMPLE_MOONLIGHT_CURVE,
    "cold_white": _EXAMPLE_MAIN_CURVE,
    "pure_white": _EXAMPLE_MAIN_CURVE,
    "warm_white": _EXAMPLE_MAIN_CURVE,
}


def _interpolate(curve: list[tuple[int, int]], minute_of_day: float) -> float:
    for (t0, v0), (t1, v1) in zip(curve, curve[1:]):
        if t0 <= minute_of_day <= t1:
            if t1 == t0:
                return v0
            frac = (minute_of_day - t0) / (t1 - t0)
            return v0 + frac * (v1 - v0)
    return curve[-1][1]


def channel_percents(minute_of_day: float) -> dict[str, float]:
    return {ch: _interpolate(curve, minute_of_day) for ch, curve in CHANNEL_CURVES.items()}


def channel_raw_values(minute_of_day: float) -> dict[str, int]:
    """Percents converted to the device's native 0-1000 scale."""
    return {ch: round(pct * 10) for ch, pct in channel_percents(minute_of_day).items()}
