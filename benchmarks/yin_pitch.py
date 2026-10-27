"""Known-signal benchmark for the existing analyzer; no recordings or new model.

Run: python -m benchmarks.yin_pitch --json-path docs/yin-baseline.json
WAV fixtures exist only in a temporary directory. Reports contain synthetic data.
"""
from dataclasses import dataclass
import argparse
import json
from pathlib import Path
import tempfile
import wave

import numpy as np
from desktop_dashboard.practice import analyze


@dataclass
class Signal:
    name: str
    samples: np.ndarray
    rate: int
    frequency: np.ndarray
    expected_voiced: np.ndarray
    transitions: tuple = ()


def signals():
    """Three-second deterministic signals; harmonic weights are amplitudes."""
    rate = 16000
    time = np.arange(3 * rate) / rate
    tones = [('A1-range-edge', 55.), ('C2-open', 65.4063913251),
             ('G2-open', 97.9988589954), ('D3-open', 146.832383959),
             ('A3-open', 220.), ('A4', 440.), ('E5', 659.255113826), ('A5', 880.)]
    for name, frequency in tones:
        yield tone(name, frequency, time, rate)
    for name, frequency, weights in (
        ('C2-second-strong', 65.4063913251, (.12, 1.)),
        ('G2-third-strong', 97.9988589954, (.12, 0., 1.)),
        ('D3-second-strong', 146.832383959, (.2, 1.)),
    ):
        yield tone(name, frequency, time, rate, weights=weights)
    for rate in (8000, 44100, 48000):
        time_at_rate = np.arange(3 * rate) / rate
        yield tone(f'C2-rate-{rate}', 65.4063913251, time_at_rate, rate)
    yield tone('A3-amplitude-varying', 220., time, 16000,
               amplitude=.025 + .35 * (time / time[-1]))
    yield tone('A3-below-quiet-gate', 220., time, 16000, amplitude=.001,
               expected_voiced=False)
    yield tone('C2-with-noise-20dB', 65.4063913251, time, 16000, noise=.35 / np.sqrt(2) / 10)
    frequencies = np.where(time < 1.5, 65.4063913251, 220.)
    yield tone('C2-to-A3-transition', frequencies, time, 16000, transitions=(1.5,))
    for seed in (7, 42):
        yield Signal(f'white-noise-seed-{seed}', np.random.default_rng(seed).normal(0, .12, len(time)),
                     16000, np.zeros(len(time)), np.zeros(len(time), dtype=bool))
    yield Signal('silence', np.zeros(len(time)), 16000, np.zeros(len(time)), np.zeros(len(time), dtype=bool))


def tone(name, frequency, time, rate, weights=(1.,), amplitude=.35,
         expected_voiced=True, noise=0., transitions=()):
    frequencies = np.broadcast_to(frequency, time.shape)
    phase = np.cumsum(frequencies) * 2 * np.pi / rate
    samples = sum(weight * np.sin((i+1)*phase) for i, weight in enumerate(weights))
    samples = amplitude * samples / sum(weights)
    if noise:
        samples += np.random.default_rng(2026).normal(0, noise, len(time))
    return Signal(name, samples, rate, frequencies,
                  np.full(len(time), expected_voiced, dtype=bool), transitions)


def write_wav(path, signal):
    with wave.open(str(path), 'wb') as wav:
        wav.setparams((1, 2, signal.rate, 0, 'NONE', 'not compressed'))
        wav.writeframes((np.clip(signal.samples, -1, 1) * 32767).astype('<i2').tobytes())


def metrics(estimated, expected_cents, expected_voiced, scored):
    voiced = scored & expected_voiced
    unvoiced = scored & ~expected_voiced
    accepted = np.isfinite(estimated)
    errors = estimated[voiced & accepted] - expected_cents[voiced & accepted]
    count = len(errors)
    def fraction(numerator, denominator):
        return float(numerator / denominator) if denominator else None
    return {
        'scored_frames': int(scored.sum()),
        'expected_voiced_frames': int(voiced.sum()),
        'accepted_voiced_frames': int((voiced & accepted).sum()),
        'voiced_coverage': fraction((voiced & accepted).sum(), voiced.sum()),
        'unvoiced_rejection': fraction((unvoiced & ~accepted).sum(), unvoiced.sum()),
        'median_abs_cents': float(np.median(np.abs(errors))) if count else None,
        'p95_abs_cents': float(np.percentile(np.abs(errors), 95)) if count else None,
        'max_abs_cents': float(np.max(np.abs(errors))) if count else None,
        'octave_error_frames': int((np.abs(np.abs(errors)-1200) <= 50).sum()),
        'gross_error_frames': int((np.abs(errors) > 50).sum()),
        'accepted_scored_frames': int((scored & accepted).sum()),
    }


def run():
    results = []
    with tempfile.TemporaryDirectory(prefix='cello-synthetic-benchmark-') as directory:
        for signal in signals():
            path = Path(directory)/f'SYNTHETIC-{signal.name}.wav'
            write_wav(path, signal)
            take = analyze(path)
            index = np.minimum((take.time * signal.rate).astype(int), len(signal.samples)-1)
            frequency = signal.frequency[index]
            expected = 1200*np.log2(np.maximum(frequency, 1)/220)
            # Score window centers away from file edges and ±80 ms around known
            # transitions; excluded transition frames are reported, never hidden.
            scored = (take.time >= .1) & (take.time <= 2.9)
            transition_excluded = np.zeros(len(take.time), dtype=bool)
            for boundary in signal.transitions:
                transition_excluded |= np.abs(take.time-boundary) <= .08 + 1e-9
            scored &= ~transition_excluded
            result = {'name': signal.name, 'sample_rate': signal.rate,
                      'transition_excluded_frames': int(transition_excluded.sum())}
            result.update(metrics(take.pitch, expected, signal.expected_voiced[index], scored))
            valid = scored & np.isfinite(take.pitch)
            result['median_accepted_periodicity'] = float(np.median(take.confidence[valid])) if valid.any() else None
            results.append(result)
    return {
        'schema': 1,
        'signal_source': 'SYNTHETIC ONLY; not cello recordings or real-world accuracy validation',
        'definitions': {
            'pitch_error': 'Estimated minus known pitch, cents; includes octave/gross errors without correction',
            'coverage': 'Finite estimates / expected voiced scored frames',
            'rejection': 'Missing estimates / expected unvoiced scored frames',
            'octave_error': 'Absolute error within 50 cents of 1200 cents (one octave)',
            'gross_error': 'Absolute error above 50 cents, including non-octave harmonics',
            'scoring': '80 ms analyzer windows, scored centers 0.1–2.9 s, excluding ±80 ms around known transitions',
            'limitation': 'No bow noise, room impulse responses, polyphony, real microphone effects, or ground-truth cello data',
        },
        'cases': results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json-path', type=Path)
    args = parser.parse_args()
    report = json.dumps(run(), indent=2, allow_nan=False) + '\n'
    if args.json_path:
        args.json_path.write_text(report)
    else:
        print(report, end='')


if __name__ == '__main__':
    main()
