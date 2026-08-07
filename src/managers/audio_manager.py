import os
import time
import wave
import subprocess
import tempfile
from pathlib import Path


class AudioManager:
    def __init__(self, config):
        self.sample_rate = config.get("audio.sample_rate", 16000)
        self.channels = config.get("audio.channels", 1)
        self.record_dir = Path(config.get("audio.record_dir", "/app/data/recordings"))
        self.play_dir = Path(config.get("audio.play_dir", "/app/data/tts"))
        self.record_dir.mkdir(parents=True, exist_ok=True)
        self.play_dir.mkdir(parents=True, exist_ok=True)

    def is_microphone_present(self):
        try:
            out = subprocess.check_output(["arecord", "-l"], text=True)
            return any("card" in line for line in out.splitlines())
        except Exception:
            return False

    def is_speaker_present(self):
        try:
            out = subprocess.check_output(["aplay", "-l"], text=True)
            return any("card" in line for line in out.splitlines())
        except Exception:
            return False

    def record(self, duration=5, output_path=None):
        if output_path is None:
            output_path = self.record_dir / f"rec_{int(time.time())}.wav"
        output_path = Path(output_path)
        cmd = [
            "arecord",
            "-D", "default",
            "-f", "S16_LE",
            "-c", str(self.channels),
            "-r", str(self.sample_rate),
            "-d", str(duration),
            str(output_path),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return output_path
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f"Recording failed: {exc.stderr.decode()}") from exc

    def play(self, wav_path):
        wav_path = Path(wav_path)
        cmd = ["aplay", "-D", "default", str(wav_path)]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f"Playback failed: {exc.stderr.decode()}") from exc
