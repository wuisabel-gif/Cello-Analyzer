"""Deterministic SYNTHETIC fixtures; these do not validate real cello accuracy."""
import tempfile
import unittest
import wave
from pathlib import Path
import numpy as np
from desktop_dashboard.practice import analyze


from synthetic import fixture


class Measurements(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def take(self, kind='steady', **kwargs):
        path = Path(self.temp.name)/f'SYNTHETIC-{kind}.wav'
        fixture(path, kind, **kwargs)
        return analyze(path)

    def test_steady_gain_and_sample_rates(self):
        for rate in (8000, 16000, 44100, 48000):
            for gain in (.03, .5):
                take = self.take(rate=rate, gain=gain)
                self.assertLess(abs(np.nanmedian(take.pitch)), 3)
                self.assertGreater(np.isfinite(take.pitch).mean(), .95)
                self.assertLess(np.ptp(take.loudness), .3)

    def test_drift_and_vibrato_separation(self):
        drift = self.take('drift')
        self.assertGreater(drift.trend[np.isfinite(drift.trend)][-1]-drift.trend[np.isfinite(drift.trend)][0], 28)
        vibrato = self.take('vibrato')
        self.assertLess(np.nanstd(vibrato.trend[20:-20]), 5)
        self.assertGreater(np.nanstd(vibrato.variation[20:-20]), 10)

    def test_silence_noise_and_octave_gaps(self):
        for kind in ('silence', 'noise'):
            take = self.take(kind)
            self.assertFalse(np.isfinite(take.pitch).any())
        take = self.take('octave')
        middle = (take.time > 1.3) & (take.time < 1.7)
        self.assertFalse(np.isfinite(take.trend[middle]).any())

    def test_invalid_and_short(self):
        with self.assertRaises(OSError):
            analyze(Path(self.temp.name)/'missing.wav')
        path = Path(self.temp.name)/'bad.wav'
        path.write_text('invalid')
        with self.assertRaises(ValueError):
            analyze(path)

