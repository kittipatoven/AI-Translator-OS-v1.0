import logging
import os
from typing import Optional

try:
    import smbus2
except Exception:
    smbus2 = None

logger = logging.getLogger(__name__)


class I2CHelper:
    """Thin I2C wrapper that falls back safely when the bus/device is absent."""

    def __init__(self, bus: int, address: int):
        self.bus = bus
        self.address = address
        self._available = False
        if smbus2 is None:
            raise RuntimeError("smbus2 not available")
        if not os.path.exists(f"/dev/i2c-{bus}"):
            raise RuntimeError(f"/dev/i2c-{bus} not found")
        try:
            self._bus = smbus2.SMBus(bus)
            self._bus.write_quick(self.address)
            self._available = True
        except OSError as exc:
            raise RuntimeError(f"LCD not found at I2C address 0x{address:02X}: {exc}") from exc

    def write_byte(self, byte: int) -> None:
        if not self._available:
            return
        try:
            self._bus.write_byte(self.address, byte)
        except OSError as exc:
            logger.error("I2C write failed: %s", exc)
            self._available = False

    def read_byte(self) -> Optional[int]:
        if not self._available:
            return None
        try:
            return self._bus.read_byte(self.address)
        except OSError as exc:
            logger.error("I2C read failed: %s", exc)
            self._available = False
            return None
