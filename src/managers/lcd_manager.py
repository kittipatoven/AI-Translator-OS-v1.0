import time
from pathlib import Path

from utils.i2c_helper import I2CHelper


class LCDManager:
    # LCD1602 commands
    _LCD_CHR = 1
    _LCD_CMD = 0
    _LCD_LINE_1 = 0x80
    _LCD_LINE_2 = 0xC0
    _LCD_BACKLIGHT = 0x08
    _ENABLE = 0b00000100

    def __init__(self, bus=1, address=0x27, enabled=True):
        self.address = address
        self.enabled = enabled
        try:
            self.i2c = I2CHelper(bus, address)
            self._init_lcd()
        except Exception as exc:
            self.i2c = None
            print(f"[LCDManager] LCD not available: {exc}")

    def _send_byte(self, bits, mode):
        if not self.i2c:
            return
        bits_high = mode | (bits & 0xF0) | self._LCD_BACKLIGHT
        bits_low = mode | ((bits << 4) & 0xF0) | self._LCD_BACKLIGHT
        self.i2c.write_byte(bits_high)
        self._toggle_enable(bits_high)
        self.i2c.write_byte(bits_low)
        self._toggle_enable(bits_low)

    def _toggle_enable(self, bits):
        if not self.i2c:
            return
        self.i2c.write_byte(bits | self._ENABLE)
        time.sleep(0.0005)
        self.i2c.write_byte(bits & ~self._ENABLE)
        time.sleep(0.0005)

    def _init_lcd(self):
        self._send_byte(0x33, self._LCD_CMD)
        self._send_byte(0x32, self._LCD_CMD)
        self._send_byte(0x06, self._LCD_CMD)
        self._send_byte(0x0C, self._LCD_CMD)
        self._send_byte(0x28, self._LCD_CMD)
        self.clear()

    def clear(self):
        self._send_byte(0x01, self._LCD_CMD)
        time.sleep(0.002)

    def display(self, line1="", line2=""):
        if not self.enabled:
            return
        self.clear()
        self._write_line(self._LCD_LINE_1, line1[:16])
        self._write_line(self._LCD_LINE_2, line2[:16])
        if self.i2c is None:
            print(f"[LCD] {line1} | {line2}")

    def _write_line(self, addr, text):
        self._send_byte(addr, self._LCD_CMD)
        for char in text.ljust(16):
            self._send_byte(ord(char), self._LCD_CHR)
