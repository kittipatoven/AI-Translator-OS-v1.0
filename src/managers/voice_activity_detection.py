"""Voice Activity Detection (VAD) using frame energy."""

import wave
from pathlib import Path


class VoiceActivityDetection:
    """Trim leading/trailing silence from a 16-bit mono PCM WAV file."""

    def __init__(
        self,
        frame_ms: int = 30,
        silence_ms: int = 500,
        energy_factor: float = 2.5,
    ):
        self.frame_ms = frame_ms
        self.silence_ms = silence_ms
        self.energy_factor = energy_factor

    @staticmethod
    def _rms(frame: bytes) -> float:
        """Compute RMS for a 16-bit little-endian PCM frame."""
        total = 0
        count = len(frame) // 2
        for i in range(count):
            sample = int.from_bytes(frame[i * 2 : i * 2 + 2], "little", signed=True)
            total += sample * sample
        if count == 0:
            return 0.0
        return (total / count) ** 0.5

    def _frame_size(self, sample_rate: int, channels: int) -> int:
        return int(sample_rate * (self.frame_ms / 1000.0) * 2 * channels)

    def trim(self, input_path: str | Path, output_path: str | Path | None = None) -> Path:
        """Trim silence from a WAV and return the output path."""
        input_path = Path(input_path)
        if output_path is None:
            output_path = input_path
        else:
            output_path = Path(output_path)

        with wave.open(str(input_path), "rb") as wf:
            channels = wf.getnchannels()
            sample_rate = wf.getframerate()
            sample_width = wf.getsampwidth()
            n_frames = wf.getnframes()
            frames = wf.readframes(n_frames)

        if sample_width != 2 or n_frames == 0:
            output_path.write_bytes(input_path.read_bytes())
            return output_path

        frame_size = self._frame_size(sample_rate, channels)
        if frame_size == 0:
            output_path.write_bytes(input_path.read_bytes())
            return output_path

        energies = []
        for i in range(0, len(frames), frame_size):
            frame = frames[i : i + frame_size]
            if len(frame) < frame_size:
                frame += b"\x00" * (frame_size - len(frame))
            energies.append(self._rms(frame))

        # Estimate ambient noise from the first 300 ms.
        ambient_frames = max(1, 300 // self.frame_ms)
        ambient = sum(energies[:ambient_frames]) / ambient_frames
        threshold = max(ambient * self.energy_factor, 50.0)

        silence_frames = max(1, self.silence_ms // self.frame_ms)

        # Find first frame above threshold.
        start = 0
        for i, e in enumerate(energies):
            if e > threshold:
                start = i
                break
        else:
            # No speech detected; keep original.
            output_path.write_bytes(input_path.read_bytes())
            return output_path

        # Find last frame above threshold followed by enough silence.
        end = len(energies) - 1
        consecutive_silence = 0
        for i in range(len(energies) - 1, -1, -1):
            if energies[i] > threshold:
                end = i
                break
            consecutive_silence += 1
            if consecutive_silence >= silence_frames:
                end = i
                break

        start_byte = start * frame_size
        end_byte = min((end + 1) * frame_size, len(frames))
        trimmed = frames[start_byte:end_byte]

        with wave.open(str(output_path), "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(sample_rate)
            wf.writeframes(trimmed)

        return output_path
