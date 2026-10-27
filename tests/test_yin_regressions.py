"""Synthetic regressions for observed errors, not real cello validation."""
import tempfile
from pathlib import Path
import unittest
import numpy as np
from benchmarks.yin_pitch import signals, tone, write_wav
from desktop_dashboard.practice import analyze


class YinRegressions(unittest.TestCase):
    def check_tone(self, signal, max_error=20):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'SYNTHETIC.wav'
            write_wav(path, signal)
            take = analyze(path)
        interior = (take.time > .1) & (take.time < 2.9)
        accepted = np.isfinite(take.pitch[interior])
        self.assertGreater(accepted.mean(), .95, signal.name)
        expected = 1200*np.log2(signal.frequency[0]/220)
        errors = np.abs(take.pitch[interior][accepted]-expected)
        self.assertLess(float(np.percentile(errors, 95)), max_error, signal.name)

    def test_observed_dominant_harmonic_failures(self):
        for signal in signals():
            if 'strong' in signal.name:
                with self.subTest(signal=signal.name):
                    self.check_tone(signal)

    def test_advertised_55_hz_boundary(self):
        signal = next(s for s in signals() if s.name == 'A1-range-edge')
        self.check_tone(signal, max_error=3)

    def test_additional_harmonic_ratios_frequencies_and_phase(self):
        rate = 16000
        time = np.arange(3*rate)/rate
        for frequency in (73.4161919794, 123.470825314, 196., 329.627556913):
            for weights in ((.25, 1.), (.15, .1, 1.)):
                signal = tone(f'additional-{frequency}-{weights}', frequency, time, rate, weights=weights)
                # Rotate sample phase without changing frequency or relative amplitudes.
                signal.samples = np.roll(signal.samples, 137)
                with self.subTest(frequency=frequency, weights=weights):
                    self.check_tone(signal)
