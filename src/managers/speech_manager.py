import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class SpeechManager:
    """Offline speech-to-text using whisper.cpp CLI (primary) or openai-whisper (fallback)."""

    def __init__(self, model_dir: str, executable: str = "whisper-cli"):
        self.model_dir = Path(model_dir)
        self.executable = executable
        self.model_path = self._find_model()
        self._whisper_module = None

    def _find_model(self):
        for ext in (".bin", ".gguf"):
            for f in self.model_dir.glob(f"*{ext}"):
                return f
        return None

    def _load_whisper_python(self):
        if self._whisper_module is not None:
            return self._whisper_module
        try:
            import whisper
            self._whisper_module = whisper
        except ImportError as exc:
            logger.error("openai-whisper not installed: %s", exc)
        return self._whisper_module

    def is_model_present(self) -> bool:
        if self._find_model():
            return True
        if self._load_whisper_python():
            return True
        return False

    def transcribe(self, wav_path, language="en"):
        wav_path = Path(wav_path)
        if not wav_path.exists():
            raise RuntimeError(f"Audio file not found: {wav_path}")

        # Primary: whisper.cpp CLI (best for Raspberry Pi)
        if self.model_path and shutil.which(self.executable):
            cmd = [
                self.executable,
                "-m", str(self.model_path),
                "-f", str(wav_path),
                "-l", language,
                "--no-timestamps",
            ]
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=120,
                    check=True,
                )
                return result.stdout.strip()
            except subprocess.CalledProcessError as exc:
                logger.error("whisper-cli failed: %s", exc.stderr)
                raise RuntimeError(f"Whisper failed: {exc.stderr}") from exc

        # Fallback: openai-whisper Python package (cross-platform)
        whisper = self._load_whisper_python()
        if not whisper:
            raise RuntimeError(
                "No Whisper runtime available. Install whisper.cpp or `pip install openai-whisper`."
            )
        try:
            model = whisper.load_model("base", download_root=str(self.model_dir))
            result = model.transcribe(str(wav_path), language=language)
            return result.get("text", "").strip()
        except Exception as exc:
            raise RuntimeError(f"Whisper fallback failed: {exc}") from exc
