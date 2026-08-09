"""Simple offline noise reduction for 16-bit PCM WAV files."""

import wave
from pathlib import Path


class NoiseReduction:
    """Remove DC offset, apply a simple noise gate, and normalize volume."""

    def __init__(self, gate_db: float = -42.0, normalize_headroom: float = 0.9):
        self.gate_db = gate_db
        self.normalize_headroom = normalize_headroom

    @staticmethod
    def _bytes_to_samples(data: bytes) -> list[int]:
        samples = []
        for i in range(0, len(data), 2):
            sample = int.from_bytes(data[i : i + 2], "little", signed=True)
            samples.append(sample)
        return samples

    @staticmethod
    def _samples_to_bytes(samples: list[int]) -> bytes:
        out = bytearray()
        for s in samples:
            if s > 32767:
                s = 32767
            elif s < -32768:
                s = -32768
            out.extend(int(s).to_bytes(2, "little", signed=True))
        return bytes(out)

    def process(self, input_path: str | Path, output_path: str | Path | None = None) -> Path:
        """Apply DC removal, noise gate, and normalization."""
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

        samples = self._bytes_to_samples(frames)

        # DC offset removal.
        mean = sum(samples) / len(samples) if samples else 0
        samples = [s - int(mean) for s in samples]

        # Noise gate: zero samples below threshold.
        gate_amp = int(32768 * (10 ** (self.gate_db / 20)))
        samples = [0 if abs(s) < gate_amp else s for s in samples]

        # Normalize to headroom without clipping.
        max_amp = max((abs(s) for s in samples), default=0)
        if max_amp > 0:
            scale = (32767 * self.normalize_headroom) / max_amp
            if scale < 1.0:
                samples = [int(s * scale) for s in samples]

        with wave.open(str(output_path), "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(sample_rate)
            wf.writeframes(self._samples_to_bytes(samples))

        return output_path
