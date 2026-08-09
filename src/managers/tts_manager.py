import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class TTSManager:
    """Offline TTS using Piper (primary) or eSpeak-NG (fallback)."""

    # Map FLORES-200 codes to eSpeak-NG voices.
    _ESPEAK_LANGUAGES = {
        "eng_Latn": "en",
        "tha_Thai": "th",
        "zho_Hans": "zh",
        "zho_Hant": "zh",
        "kor_Hang": "ko",
        "mya_Mymr": "my",
    }

    def __init__(self, model_dir, executable="piper"):
        self.model_dir = Path(model_dir)
        self.executable = executable
        self.cache_path = Path("/app/data/tts/last.wav")
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._voice: str | None = None
        self._language: str | None = None

    def _voice_files(self, voice: str | None):
        """Find the .onnx and .onnx.json files for a given voice key."""
        if not voice:
            return None, None
        # Search recursively; voices may be in a nested folder like en/en_US/.../voice.onnx
        for f in self.model_dir.rglob(f"*{voice}*.onnx"):
            if f.name.endswith(".onnx.json"):
                continue
            config = f.with_suffix(f".onnx.json")
            if not config.exists():
                config = self.model_dir / (f.stem + ".onnx.json")
            if config.exists():
                return f, config
        return None, None

    def has_voice(self, voice: str | None) -> bool:
        model, _ = self._voice_files(voice)
        return model is not None

    def set_voice(self, voice: str | None):
        self._voice = voice

    def set_language(self, language: str | None):
        self._language = language

    def _espeak_lang(self) -> str | None:
        return self._ESPEAK_LANGUAGES.get(self._language, "en") if self._language else "en"

    def _espeak_speak(self, text: str, output_path: Path) -> Path:
        if not shutil.which("espeak-ng") and not shutil.which("espeak"):
            raise RuntimeError("No TTS engine available")
        cmd = ["espeak-ng" if shutil.which("espeak-ng") else "espeak", "-v", self._espeak_lang(), "-w", str(output_path), text]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=120)
            return output_path
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            raise RuntimeError(f"eSpeak TTS failed: {exc}") from exc

    def is_model_present(self) -> bool:
        if self._voice:
            return self.has_voice(self._voice)
        return any(self.model_dir.rglob("*.onnx"))

    def speak(self, text, output_path=None, voice: str | None = None):
        if output_path is None:
            output_path = self.cache_path
        output_path = Path(output_path)

        voice = voice or self._voice
        if not voice:
            # No Piper voice configured: try eSpeak fallback immediately.
            return self._espeak_speak(text, output_path)

        model_path, config_path = self._voice_files(voice)
        if not model_path or not shutil.which(self.executable):
            logger.warning("Piper voice not available, falling back to eSpeak: %s", voice)
            return self._espeak_speak(text, output_path)

        cmd = [
            self.executable,
            "--model", str(model_path),
            "--output_file", str(output_path),
            "--text", text,
        ]
        if config_path and config_path.exists():
            cmd += ["--config", str(config_path)]
        try:
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=120,
            )
            return output_path
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            logger.warning("Piper TTS failed, falling back to eSpeak: %s", exc)
            return self._espeak_speak(text, output_path)

    def replay(self):
        if self.cache_path.exists():
            return self.cache_path
        return None
