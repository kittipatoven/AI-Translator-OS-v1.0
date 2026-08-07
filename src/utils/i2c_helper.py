try:
    import smbus2
except Exception:
    smbus2 = None


class I2CHelper:
    def __init__(self, bus, address):
        self.bus = bus
        self.address = address
        if smbus2 is None:
            raise RuntimeError("smbus2 not available")
        self._bus = smbus2.SMBus(bus)

    def write_byte(self, byte):
        self._bus.write_byte(self.address, byte)

    def read_byte(self):
        return self._bus.read_byte(self.address)
