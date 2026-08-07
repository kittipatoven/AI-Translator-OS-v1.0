import os
import time
from pathlib import Path

from managers.model_manager import ModelManager
from utils import system_helper


class BootManager:
    def __init__(self, config):
        self.config = config
        self.diagnostics = {}

    def initialize(self):
        self.diagnostics["i2c"] = self._check_i2c()
        self.diagnostics["gpio"] = self._check_gpio()
        self.diagnostics["microphone"] = self._check_mic()
        self.diagnostics["speaker"] = self._check_speaker()
        self.diagnostics["whisper"] = self._check_model("whisper")
        self.diagnostics["nllb"] = self._check_model("nllb")
        self.diagnostics["piper"] = self._check_model("piper")
        print("[BootManager] diagnostics:", self.diagnostics)
        return all(self.diagnostics.values())

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
