import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from desktop_dashboard.media_import import load_audio
from desktop_dashboard.practice import analyze
from synthetic import fixture


class MediaImport(unittest.TestCase):
    def test_missing_decoder_and_invalid_range(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'SYNTHETIC.mov'
            path.write_bytes(b'invalid')
            with patch('desktop_dashboard.media_import.shutil.which', return_value=None):
                with self.assertRaisesRegex(ValueError, 'already installed'):
                    load_audio(path)
            for start, duration in ((-1, 30), (0, 61), (0, 0)):
                with self.assertRaises(ValueError):
                    load_audio(path, start, duration)

    @unittest.skipUnless(shutil.which('ffmpeg'), 'requires already installed FFmpeg')
    def test_real_decoder_excerpt_source_preserved_and_bad_input(self):
        with tempfile.TemporaryDirectory() as directory:
            wav = Path(directory)/'SYNTHETIC.wav'
            mov = Path(directory)/'SYNTHETIC.mov'
            fixture(wav, 'drift')
            subprocess.run([shutil.which('ffmpeg'), '-v', 'error', '-nostdin', '-i', str(wav), '-c:a', 'pcm_s16le', str(mov)], check=True)
            original = hashlib.sha256(mov.read_bytes()).digest()
            audio = load_audio(mov, 1, 1.5)
            self.assertEqual(audio.sample_rate, 16000)
            self.assertAlmostEqual(audio.duration, 1.5, places=2)
            self.assertIn('source 1.00–2.50 s', audio.name)
            self.assertEqual(hashlib.sha256(mov.read_bytes()).digest(), original)
            self.assertEqual(analyze(mov, 1, 1.5).source_start, 1)
            with self.assertRaises(ValueError):
                load_audio(mov, 10, 1)
            mov.write_bytes(b'invalid')
            with self.assertRaisesRegex(ValueError, 'invalid movie or no audio'):
                load_audio(mov)

    @unittest.skipUnless(shutil.which('ffmpeg'), 'requires already installed FFmpeg')
    def test_movie_without_audio(self):
        with tempfile.TemporaryDirectory() as directory:
            mov = Path(directory)/'SYNTHETIC-no-audio.mov'
            subprocess.run([shutil.which('ffmpeg'), '-v', 'error', '-nostdin', '-f', 'lavfi', '-i', 'color=size=16x16:duration=0.2', '-c:v', 'mpeg4', str(mov)], check=True)
            with self.assertRaisesRegex(ValueError, 'no audio track'):
                load_audio(mov)
