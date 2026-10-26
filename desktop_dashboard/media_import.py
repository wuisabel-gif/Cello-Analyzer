"""Local MOV audio excerpts via an already installed FFmpeg; never downloads it."""
from pathlib import Path
import shutil
import subprocess
import tempfile
from desktop_dashboard.wav_import import load_wav


def load_audio(path, start=0., duration=30.):
    path = Path(path).expanduser()
    if path.suffix.lower() != '.mov':
        return load_wav(path)
    if not 0 <= start <= 86400 or not .1 <= duration <= 60:
        raise ValueError('Choose a MOV start from 0–86400 s and duration from 0.1–60 s.')
    if not path.is_file():
        raise ValueError('MOV file does not exist.')
    if path.stat().st_size > 2_000_000_000:
        raise ValueError('Use a local MOV smaller than 2 GB.')
    decoder = shutil.which('ffmpeg')
    if decoder is None:
        raise ValueError('MOV import needs FFmpeg already installed on PATH. Convert a short excerpt to 16-bit PCM WAV locally, then import that WAV. Nothing was installed.')
    with tempfile.TemporaryDirectory(prefix='cello-audio-') as directory:
        output = Path(directory)/'excerpt.wav'
        try:
            # Local files only; no shell, playback, network input or video decoding.
            result = subprocess.run([
                decoder, '-v', 'error', '-nostdin', '-protocol_whitelist', 'file,pipe',
                '-ss', str(float(start)), '-i', str(path.resolve()), '-map', '0:a:0',
                '-vn', '-t', str(float(duration)), '-map_metadata', '-1',
                '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', str(output),
            ], capture_output=True, timeout=30, check=False)
        except subprocess.TimeoutExpired as exc:
            raise ValueError('MOV audio decoding timed out. Try a shorter excerpt or a local WAV copy.') from exc
        except OSError as exc:
            raise ValueError('Cannot run the installed FFmpeg decoder. Import a local PCM WAV instead.') from exc
        if result.returncode:
            raise ValueError('Cannot decode MOV audio: invalid movie or no audio track.')
        audio = load_wav(output)
    audio.name = f'{path.name} [source {start:.2f}–{start+audio.duration:.2f} s]'
    audio.source_start = start
    return audio
