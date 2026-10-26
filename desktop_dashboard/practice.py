"""Local sustained-note measurements. Heuristics, not a validated cello assessment."""
from dataclasses import dataclass
from desktop_dashboard.media_import import load_audio
import numpy as np


@dataclass
class Take:
    name: str
    duration: float
    time: np.ndarray
    pitch: np.ndarray
    confidence: np.ndarray
    trend: np.ndarray
    variation: np.ndarray
    loudness: np.ndarray
    source_start: float = 0.



def analyze(path, start=0., duration=30.):
    audio = load_audio(path, start, duration)
    rate, samples = audio.sample_rate, audio.samples
    # Resample to a bounded analysis rate; no device or network access.
    target = 8000
    if rate > target:
        # Suppress frequencies above the analysis Nyquist limit before decimation.
        spectrum = np.fft.rfft(samples)
        frequencies = np.fft.rfftfreq(len(samples), 1 / rate)
        spectrum[frequencies >= 3500] = 0
        samples = np.fft.irfft(spectrum, n=len(samples))
    samples = np.interp(np.arange(0, len(samples), rate / target), np.arange(len(samples)), samples)
    size, hop = 640, 160  # 80 ms windows / 20 ms hop; cello range 55–1000 Hz
    times, pitches, confidence, levels = [], [], [], []
    for start in range(0, len(samples) - size + 1, hop):
        x = samples[start:start + size].copy()
        x -= x.mean()
        rms = np.sqrt(np.mean(x*x))
        levels.append(20 * np.log10(max(rms, 1e-6)))
        times.append((start + size/2) / target)
        pitch, conf = np.nan, 0.
        if rms > .003:
            # Normalized squared difference (YIN-like); first strong local trough
            # avoids selecting a later period / octave-down on clean tones.
            lags = np.arange(1, 146)
            diff = np.array([np.sum((x[:-lag]-x[lag:])**2) for lag in lags])
            cmnd = diff * lags / np.maximum(np.cumsum(diff), 1e-15)
            candidates = [k for k in range(7, 144) if cmnd[k] < .15 and cmnd[k] <= cmnd[k-1] and cmnd[k] < cmnd[k+1]]
            if candidates:
                k = candidates[0]
                denom = cmnd[k-1] - 2*cmnd[k] + cmnd[k+1]
                lag = k+1 + (.5*(cmnd[k-1]-cmnd[k+1])/denom if denom else 0)
                conf = float(1-cmnd[k])
                pitch = 1200*np.log2((target/lag)/220)
        pitches.append(pitch)
        confidence.append(conf)
    pitch = np.array(pitches)
    trend = np.full(len(pitch), np.nan)
    for i in range(12, len(pitch)-12):
        segment = pitch[max(0,i-12):min(len(pitch),i+13)]
        # Never smooth across unvoiced gaps or octave-sized discontinuities.
        if np.isfinite(segment).all() and np.ptp(segment) < 600:
            trend[i] = np.median(segment)
    levels = np.array(levels)
    relative = levels - np.max(levels) if len(levels) else levels
    return Take(audio.name, audio.duration, np.array(times), pitch, np.array(confidence), trend, pitch-trend, relative, audio.source_start)
