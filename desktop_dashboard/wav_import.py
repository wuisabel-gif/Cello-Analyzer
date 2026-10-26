"""Bounded, local-only 16-bit PCM WAV loading; never opens audio devices."""
from dataclasses import dataclass
from pathlib import Path
import wave
import numpy as np


@dataclass
class Audio:
    samples: np.ndarray
    sample_rate: int
    name: str
    source_start: float = 0.

    @property
    def duration(self):
        return len(self.samples) / self.sample_rate


def load_wav(path):
    path = Path(path)
    if path.stat().st_size > 32_000_000:
        raise ValueError('Use a WAV smaller than 32 MB (short sustained-note exercise).')
    try:
        with wave.open(str(path), 'rb') as wav:
            rate, channels, width = wav.getframerate(), wav.getnchannels(), wav.getsampwidth()
            if width != 2 or channels not in (1, 2) or not 8000 <= rate <= 96000:
                raise ValueError('Use 16-bit PCM mono/stereo WAV at 8–96 kHz.')
            frames = wav.getnframes()
            if not frames or frames / rate > 60:
                raise ValueError('Use a nonempty exercise of at most 60 seconds.')
            raw = wav.readframes(frames)
            if len(raw) != frames * channels * width:
                raise ValueError('WAV data is truncated.')
    except (wave.Error, EOFError) as exc:
        raise ValueError('Cannot read this PCM WAV file.') from exc
    samples = np.frombuffer(raw, dtype='<i2').astype(float).reshape(-1, channels).mean(axis=1) / 32768
    return Audio(samples, rate, path.name)
