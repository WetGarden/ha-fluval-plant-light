"""Low-level Fluval Plant 3.0 BLE protocol.

Reverse-engineered by TooManyFrogs, plantedtank.net thread "Reverse Engineering
the Fluval Plant 3.0 BLE protocol" (2022). Encryption/CRC verified byte-for-byte
against the thread's captured example:
  545affc3af5454545454545454ab503c  ->  6804ffffffffffffffff00fb97
  (0x68 header, 0x04 brightness command, channels ff/ff/ff/ff/00fb=251, CRC 0x97)
"""

# 1001 is the only command endpoint; 1002 is notify-only. Until 2026-10-11
# commands were written to 1002: with response=True the light rejected them
# (ATT error 3), with response=False they were silently dropped. Confirmed
# against MrMooreUK/fluvalble (LEGACY_COMMAND_WRITE_UUIDS / NOTIFY_UUIDS).
WRITE_CHAR = "00001001-0000-1000-8000-00805F9B34FB"
NOTIFY_CHAR = "00001002-0000-1000-8000-00805F9B34FB"
HANDSHAKE_CHAR = WRITE_CHAR
KEEPALIVE_CHAR = "00001004-0000-1000-8000-00805F9B34FB"

NO_CHANGE = 0xFFFF
CMD_CLOCK = 0x0E
CMD_SWITCH = 0x03
CMD_BRIGHTNESS = 0x04


def _crc(msg: bytearray) -> int:
    check = 0
    for b in msg:
        check ^= b
    return check


def _encrypt(msg: bytearray, key: int = 0x0E) -> bytearray:
    """Wrap+XOR a [0x68, cmd, args..., crc] message for the wire."""
    header = bytearray([0x54, (len(msg) + 1) ^ 0x54, key ^ 0x54])
    return header + bytearray(b ^ key for b in msg)


def _decrypt(data: bytes) -> bytes:
    key = data[0] ^ data[2]
    return bytes(b ^ key for b in data[3:])


def build_message(payload: list[int]) -> bytearray:
    msg = bytearray([0x68]) + bytearray(payload)
    msg.append(_crc(msg))
    return _encrypt(msg)


MODE_NAMES = {0x00: "manual", 0x01: "auto", 0x02: "pro"}


def clock_message(now) -> bytearray:
    """Set the light's clock (cmd 0x0E: YY M D ISO-weekday h m s). The light has
    no RTC battery; after a power loss its clock resets and a pro-mode schedule
    runs against the wrong time. Layout from MrMooreUK/fluvalble old_clock_packet."""
    return build_message([
        CMD_CLOCK, now.year % 100, now.month, now.day, now.isoweekday(),
        now.hour, now.minute, now.second,
    ])


def power_message(on: bool) -> bytearray:
    return build_message([CMD_SWITCH, 0x01 if on else 0x00])


def brightness_message(
    pink: int | None,
    blue: int | None,
    cold_white: int | None,
    pure_white: int | None,
    warm_white: int | None,
) -> bytearray:
    """Each value is 0-1000, or None to leave that channel unchanged."""

    def enc(v: int | None) -> bytes:
        if v is None:
            return NO_CHANGE.to_bytes(2, "big")
        if not 0 <= v <= 1000:
            raise ValueError(f"brightness {v} out of range 0-1000")
        return v.to_bytes(2, "big")

    payload = [CMD_BRIGHTNESS]
    for v in (pink, blue, cold_white, pure_white, warm_white):
        payload.extend(enc(v))
    return build_message(payload)


def handshake_message() -> bytearray:
    return _encrypt(bytearray([0x68, 0x05, 0x68 ^ 0x05]))
