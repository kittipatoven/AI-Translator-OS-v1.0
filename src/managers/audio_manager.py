import logging
import os
import re
import shutil
import time
import wave
import subprocess
import tempfile
from pathlib import Path

try:
    import sounddevice as sd
    import soundfile as sf
    _HAS_SOUND = True
except Exception as exc:  # pragma: no cover
    sd = None
    sf = None
    _HAS_SOUND = False

from managers.noise_reduction import NoiseReduction
from managers.voice_activity_detection import VoiceActivityDetection

logger = logging.getLogger(__name__)


class AudioManager:
    """Cross-platform audio capture and playback.

    Linux/Pi: prefers ALSA arecord/aplay.
    Windows/macOS/other: falls back to sounddevice/soundfile.
    No hardware: returns/uses a dummy WAV without crashing.
    """

    def __init__(self, config):
        self.config = config
        self.sample_rate = config.get("audio.sample_rate", 16000)
        self.channels = config.get("audio.channels", 1)
        self.device_input = config.get("audio.device_input", "default")
        self.device_output = config.get("audio.device_output", "default")
        self.record_dir = Path(config.get("audio.record_dir", "/app/data/recordings"))
        self.play_dir = Path(config.get("audio.play_dir", "/app/data/tts"))
        self.record_dir.mkdir(parents=True, exist_ok=True)
        self.play_dir.mkdir(parents=True, exist_ok=True)
        self._detect_alsa_devices()

    @staticmethod
    def _first_alsa_device(cmd):
        """Return the first usable ALSA card/device for arecord/aplay as plughw:X,Y."""
        try:
            out = subprocess.check_output([cmd, "-l"], text=True, stderr=subprocess.DEVNULL)
        except Exception:
            return None
        cards = []
        for line in out.splitlines():
            m = re.match(r"^card\s+(\d+):[^,]+,\s*device\s+(\d+):", line.strip())
            if m:
                cards.append((int(m.group(1)), int(m.group(2)), line))
        built_in = ["vc4hdmi", "bcm2835", "hdmi", "dummy"]
        for card, dev, line in cards:
            if not any(b in line.lower() for b in built_in):
                return f"plughw:{card},{dev}"
        if cards:
            card, dev, _ = cards[0]
            return f"plughw:{card},{dev}"
        return None

    def _detect_alsa_devices(self, force=False):
        """Auto-detect mic/speaker if config is set to auto, or on startup."""
        if force or self.device_input in ("auto", "default"):
            found = self._first_alsa_device("arecord")
            if found:
                if self.device_input != found:
                    logger.info("Auto-selected microphone: %s", found)
                self.device_input = found
        if force or self.device_output in ("auto", "default"):
            found = self._first_alsa_device("aplay")
            if found:
                if self.device_output != found:
                    logger.info("Auto-selected speaker: %s", found)
                self.device_output = found

    @staticmethod
    def _has_arecord():
        return shutil.which("arecord") is not None

    @staticmethod
    def _has_aplay():
        return shutil.which("aplay") is not None

    def _has_sounddevice(self):
        return _HAS_SOUND

    def is_microphone_present(self):
        if self._has_arecord():
            try:
                out = subprocess.check_output(["arecord", "-l"], text=True)
                return any("card" in line for line in out.splitlines())
            except Exception:
                return False
        if _HAS_SOUND:
            try:
                devices = sd.query_devices()
                return any(d.get("max_input_channels", 0) > 0 for d in devices)
            except Exception:
                return False
        return False

    def is_speaker_present(self):
        if self._has_aplay():
            try:
                out = subprocess.check_output(["aplay", "-l"], text=True)
                return any("card" in line for line in out.splitlines())
            except Exception:
                return False
        if _HAS_SOUND:
            try:
                devices = sd.query_devices()
                return any(d.get("max_output_channels", 0) > 0 for d in devices)
            except Exception:
                return False
        return False

    def record(self, duration=10, output_path=None):
        """Record up to `duration` seconds, then apply NR and VAD trimming."""
        if output_path is None:
            output_path = self.record_dir / f"rec_{int(time.time())}.wav"
        output_path = Path(output_path)

        if self._has_arecord():
            try:
                return self._record_arecord(duration, output_path)
            except Exception as exc:
                logger.warning("arecord failed: %s", exc)

        if _HAS_SOUND:
            try:
                return self._record_sounddevice(duration, output_path)
            except Exception as exc:
                logger.warning("sounddevice recording failed: %s", exc)

        logger.warning("No audio capture engine available; returning dummy recording")
        return self._record_dummy(output_path)

    def _record_arecord(self, duration, output_path, _retry=False):
        cmd = [
            "arecord",
            "-D", self.device_input,
            "-f", "S16_LE",
            "-c", str(self.channels),
            "-r", str(self.sample_rate),
            "-d", str(duration),
            str(output_path),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as exc:
            if not _retry:
                logger.warning("Recording on %s failed, trying auto-detect", self.device_input)
                old = self.device_input
                self._detect_alsa_devices(force=True)
                if self.device_input != old:
                    return self._record_arecord(duration, output_path, _retry=True)
            raise RuntimeError(f"Recording failed: {exc.stderr.decode()}") from exc

        NoiseReduction().process(output_path)
        VoiceActivityDetection().trim(output_path, output_path)
        return output_path

    def _record_sounddevice(self, duration, output_path):
        frames = int(duration * self.sample_rate)
        data = sd.rec(
            frames,
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="int16",
            blocking=True,
        )
        sf.write(str(output_path), data, self.sample_rate, subtype="PCM_16")
        NoiseReduction().process(output_path)
        VoiceActivityDetection().trim(output_path, output_path)
        return output_path

    def _record_dummy(self, output_path):
        with wave.open(str(output_path), "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            seconds = 1
            wf.writeframes(b"\x00" * (self.sample_rate * self.channels * 2 * seconds))
        return output_path

    def record_vad(self, max_duration=10, output_path=None):
        """Record until the user stops speaking or max_duration is reached.

        Uses arecord raw PCM streaming and a simple energy-based VAD.
        Falls back to fixed-duration recording if arecord streaming fails.
        """
        if output_path is None:
            output_path = self.record_dir / f"rec_{int(time.time())}.wav"
        output_path = Path(output_path)

        if not self._has_arecord():
            logger.warning("arecord not available; falling back to fixed recording")
            return self.record(duration=max_duration, output_path=output_path)

        vad = VoiceActivityDetection()
        frame_ms = vad.frame_ms
        sample_width = 2
        frame_size = int(self.sample_rate * (frame_ms / 1000.0) * sample_width * self.channels)
        if frame_size <= 0:
            return self.record(duration=max_duration, output_path=output_path)

        ambient_frames = max(1, 300 // frame_ms)
        silence_frames = max(1, vad.silence_ms // frame_ms)
        max_frames = int(max_duration * 1000 / frame_ms)

        cmd = [
            "arecord",
            "-D", self.device_input,
            "-f", "S16_LE",
            "-c", str(self.channels),
            "-r", str(self.sample_rate),
            "-t", "raw",
            "-",
        ]
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except Exception as exc:
            logger.warning("arecord VAD start failed: %s", exc)
            return self.record(duration=max_duration, output_path=output_path)

        def read_exact(stream, n):
            buf = b""
            while len(buf) < n:
                chunk = stream.read(n - len(buf))
                if not chunk:
                    return buf
                buf += chunk
            return buf

        with wave.open(str(output_path), "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(self.sample_rate)

            # 1) collect initial frames for ambient threshold
            ambient_buf = b""
            needed = ambient_frames * frame_size
            while len(ambient_buf) < needed:
                chunk = read_exact(proc.stdout, needed - len(ambient_buf))
                if not chunk:
                    break
                ambient_buf += chunk
                wf.writeframes(chunk)

            ambient_energies = [
                vad._rms(ambient_buf[i : i + frame_size])
                for i in range(0, len(ambient_buf) - frame_size + 1, frame_size)
            ]
            ambient = sum(ambient_energies) / len(ambient_energies) if ambient_energies else 0.0
            threshold = max(ambient * vad.energy_factor, 50.0)

            # 2) stream and stop after enough consecutive silence following speech
            total_frames = len(ambient_buf) // frame_size
            has_speech = False
            consecutive_silence = 0
            try:
                while total_frames < max_frames:
                    frame = read_exact(proc.stdout, frame_size)
                    if not frame:
                        break
                    wf.writeframes(frame)
                    total_frames += 1
                    rms = vad._rms(frame)
                    if rms > threshold:
                        has_speech = True
                        consecutive_silence = 0
                    else:
                        consecutive_silence += 1
                    if has_speech and consecutive_silence >= silence_frames:
                        logger.info("VAD silence detected, stopping recording")
                        break
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except Exception:
                    proc.kill()
                    proc.wait()

        NoiseReduction().process(output_path)
        VoiceActivityDetection().trim(output_path, output_path)
        return output_path

    def play(self, wav_path):
        wav_path = Path(wav_path)
        if not wav_path.exists():
            raise RuntimeError(f"Audio file not found: {wav_path}")

        if self._has_aplay():
            try:
                self._play_aplay(wav_path)
                return
            except Exception as exc:
                logger.warning("aplay failed: %s", exc)

        if _HAS_SOUND:
            try:
                data, sr = sf.read(str(wav_path), dtype="int16")
                sd.play(data, sr, blocking=True)
                return
            except Exception as exc:
                logger.warning("sounddevice playback failed: %s", exc)

        logger.warning("No playback engine available; skipping playback of %s", wav_path)

    def _play_aplay(self, wav_path, _retry=False):
        cmd = ["aplay", "-D", self.device_output, str(wav_path)]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as exc:
            if not _retry:
                logger.warning("Playback on %s failed, trying auto-detect", self.device_output)
                old = self.device_output
                self._detect_alsa_devices(force=True)
                if self.device_output != old:
                    return self._play_aplay(wav_path, _retry=True)
            raise RuntimeError(f"Playback failed: {exc.stderr.decode()}") from exc

    @staticmethod
    def _list_alsa_devices(cmd):
        """Return every ALSA card/device reported by arecord/aplay."""
        try:
            out = subprocess.check_output([cmd, "-l"], text=True, stderr=subprocess.DEVNULL)
        except Exception:
            return []
        devices = []
        for line in out.splitlines():
            line = line.strip()
            m = re.match(r"^card\s+(\d+):\s*(.+?)\s*,\s*device\s+(\d+):\s*(.*)", line)
            if not m:
                continue
            card = int(m.group(1))
            card_name = m.group(2).strip()
            dev = int(m.group(3))
            dev_name = m.group(4).strip()
            devices.append(
                {
                    "id": f"plughw:{card},{dev}",
                    "name": f"{card_name} - {dev_name}",
                    "card": card,
                    "device": dev,
                }
            )
        return devices

    def list_input_devices(self):
        if self._has_arecord():
            return self._list_alsa_devices("arecord")
        if _HAS_SOUND:
            try:
                devices = []
                for i, d in enumerate(sd.query_devices()):
                    if d.get("max_input_channels", 0) > 0:
                        devices.append({"id": i, "name": d.get("name", f"device {i}")})
                return devices
            except Exception:
                return []
        return []

    def list_output_devices(self):
        if self._has_aplay():
            return self._list_alsa_devices("aplay")
        if _HAS_SOUND:
            try:
                devices = []
                for i, d in enumerate(sd.query_devices()):
                    if d.get("max_output_channels", 0) > 0:
                        devices.append({"id": i, "name": d.get("name", f"device {i}")})
                return devices
            except Exception:
                return []
        return []

    def set_input_device(self, device_id):
        self.device_input = device_id
        self.config.set("audio.device_input", device_id)
        self.config.save()
        logger.info("Input device set to %s", device_id)

    def set_output_device(self, device_id):
        self.device_output = device_id
        self.config.set("audio.device_output", device_id)
        self.config.save()
        logger.info("Output device set to %s", device_id)
