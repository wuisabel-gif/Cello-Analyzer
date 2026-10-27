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



def _refine_trough(values, index):
    """Parabolic lag and minimum; compare troughs beyond integer-lag bias."""
    left, middle, right = values[index-1:index+2]
    curvature = left-2*middle+right
    offset = .5*(left-right)/curvature if curvature else 0.
    score = middle-(left-right)**2/(8*curvature) if curvature else middle
    return index+1+offset, max(0., float(score))


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
            # Normalized squared difference (YIN-like), with an initial short
            # period and a conservative check for stronger full-period matches.
            lags = np.arange(1, int(np.ceil(target/55))+2)
            diff = np.array([np.sum((x[:-lag]-x[lag:])**2) for lag in lags])
            cmnd = diff * lags / np.maximum(np.cumsum(diff), 1e-15)
            candidates = [k for k in range(7, len(cmnd)-1) if cmnd[k] < .15 and cmnd[k] <= cmnd[k-1] and cmnd[k] < cmnd[k+1]]
            if candidates:
                k = candidates[0]
                # A strong overtone can cross the first-trough threshold before
                # the fundamental. Prefer the earliest integer-multiple period
                # only when it gives a much deeper match; do not chase arbitrary
                # later troughs (which would octave-down clean sine tones).
                first_lag, first_score = _refine_trough(cmnd, k)
                if first_score > .01:
                    for candidate in candidates[1:]:
                        candidate_lag, candidate_score = _refine_trough(cmnd, candidate)
                        ratio = candidate_lag/first_lag
                        multiple = round(ratio)
                        if (2 <= multiple <= 4 and abs(ratio-multiple) < .1
                                and candidate_score < .2*first_score):
                            k = candidate
                            break
                lag, _ = _refine_trough(cmnd, k)
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
