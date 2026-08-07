from pathlib import Path

from utils import system_helper


class DiagnosticsManager:
    def __init__(self, config):
        self.config = config

    def _test(self, name, check):
        try:
            return "PASS" if check() else "FAIL"
        except Exception as exc:
            return f"FAIL: {exc}"

    def run_all(self):
        return {
            "lcd": self._test("lcd", self._check_i2c),
            "gpio": self._test("gpio", self._check_gpio),
            "i2c": self._test("i2c", self._check_i2c),
            "speaker": self._test("speaker", self._check_speaker),
            "microphone": self._test("microphone", self._check_microphone),
            "storage": self._test("storage", self._check_storage),
        }

    def _check_i2c(self):
        rc, _, _ = system_helper.run_cmd(
            ["i2cdetect", "-y", str(self.config.get("lcd.i2c_bus", 1))]
        )
        return rc == 0

    def _check_gpio(self):
        return Path("/dev/gpiomem").exists()

    def _check_speaker(self):
        rc, out, _ = system_helper.run_cmd(["aplay", "-l"])
        return rc == 0 and "card" in out

    def _check_microphone(self):
        rc, out, _ = system_helper.run_cmd(["arecord", "-l"])
        return rc == 0 and "card" in out

    def _check_storage(self):
        usage = system_helper.disk_usage("/")
        if not usage:
            return False
        return usage.used / usage.total < 0.95
