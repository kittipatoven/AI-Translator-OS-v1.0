import os
import time
from pathlib import Path

from managers.model_manager import ModelManager
from utils import system_helper


class BootManager:
    def __init__(self, config, lcd=None):
        self.config = config
        self.lcd = lcd
        self.diagnostics = {}

    def _show(self, line1, line2=""):
        if self.lcd:
            try:
                self.lcd.display(line1, line2)
                time.sleep(0.3)
            except Exception:
                pass
        print(f"[BootManager] {line1} | {line2}")

    def initialize(self):
        self._show("AI TRANSLATOR", "Booting...")

        self.diagnostics["i2c"] = self._check("I2C", self._check_i2c)
        self.diagnostics["gpio"] = self._check("GPIO", self._check_gpio)
        self.diagnostics["microphone"] = self._check("Microphone", self._check_mic)
        self.diagnostics["speaker"] = self._check("Speaker", self._check_speaker)
        self.diagnostics["whisper"] = self._check("Whisper model", self._check_model, "whisper")
        self.diagnostics["nllb"] = self._check("NLLB model", self._check_model, "nllb")
        self.diagnostics["piper"] = self._check("Piper model", self._check_model, "piper")

        print("[BootManager] diagnostics:", self.diagnostics)
        all_ok = all(self.diagnostics.values())
        if all_ok:
            self._show("Boot OK", "System Ready")
        else:
            failed = [k for k, v in self.diagnostics.items() if not v]
            self._show("ERROR", f"{failed[0]} missing"[:16])
        return all_ok

    def _check(self, label, fn, *args):
        self._show("Checking", label)
        try:
            return fn(*args)
        except Exception as exc:
            print(f"[BootManager] {label} check error: {exc}")
            return False

    def _check_i2c(self):
        rc, _, _ = system_helper.run_cmd(["i2cdetect", "-y", str(self.config.get("lcd.i2c_bus", 1))])
        return rc == 0

    def _check_gpio(self):
        return Path("/dev/gpiomem").exists()

    def _check_mic(self):
        rc, out, _ = system_helper.run_cmd(["arecord", "-l"])
        return rc == 0 and "card" in out

    def _check_speaker(self):
        rc, out, _ = system_helper.run_cmd(["aplay", "-l"])
        return rc == 0 and "card" in out

    def _check_model(self, name):
        path = self.config.get(f"models.{name}_dir", f"/app/models/{name}")
        return len(ModelManager(path).list_models()) > 0
