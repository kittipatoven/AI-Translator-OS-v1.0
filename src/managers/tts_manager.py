import shutil
import subprocess
from pathlib import Path


class TTSManager:
    """Offline TTS using Piper. Selects the voice model from the language pack."""

    def __init__(self, model_dir, executable="piper"):
        self.model_dir = Path(model_dir)
        self.executable = executable
        self.cache_path = Path("/app/data/tts/last.wav")
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._voice: str | None = None

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
            raise RuntimeError("No TTS voice selected for this language pack")

        model_path, config_path = self._voice_files(voice)
        if not model_path:
            raise RuntimeError(f"Piper voice not found: {voice}")

        # Ensure the `piper` executable is available.
        if not shutil.which(self.executable):
            raise RuntimeError("Piper executable not found. Install `piper-tts`.")

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
            raise RuntimeError(f"TTS failed: {exc}") from exc

    def replay(self):
        if self.cache_path.exists():
            return self.cache_path
        return None
