import tempfile
import unittest
import wave
from pathlib import Path
import numpy as np
from desktop_dashboard.wav_import import load_wav
from synthetic import fixture


class WavImport(unittest.TestCase):
    def test_rates_and_gains(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'SYNTHETIC.wav'
            for rate in (8000, 16000, 44100, 48000):
                for gain in (.03, .5):
                    fixture(path, rate=rate, gain=gain)
                    audio = load_wav(path)
                    self.assertEqual(audio.sample_rate, rate)
                    self.assertEqual(audio.duration, 3)
                    self.assertAlmostEqual(np.max(audio.samples), gain, places=3)

    def test_bad_missing_empty_and_truncated(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'test.wav'
            with self.assertRaises(OSError):
                load_wav(path)
            path.write_text('invalid')
            with self.assertRaises(ValueError):
                load_wav(path)
            with wave.open(str(path), 'wb') as wav:
                wav.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
            with self.assertRaises(ValueError):
                load_wav(path)
            fixture(path)
            path.write_bytes(path.read_bytes()[:-100])
            with self.assertRaises(ValueError):
                load_wav(path)
