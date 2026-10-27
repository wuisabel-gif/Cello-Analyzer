# Cello Analyzer Desktop Dashboard

PySide6 desktop application for monitoring a Photon 2 based Cello Analyzer in real time.

<img src="assets/desktop-dashboard-preview.gif" alt="Cello Analyzer desktop dashboard preview" width="720" />

## Features

- Live waveform graph
- Volume meter and dynamic label
- Temperature and humidity monitoring
- OLED-style preview panel
- Session recording in memory
- CSV export
- Mock data mode for UI development
- Serial mode scaffold for live device integration

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r desktop_dashboard/requirements.txt
python3 -m desktop_dashboard.main
```

## Data Sources

- `Mock Source`
  - generates realistic cello-like performance and environment data for testing the UI
- `Serial Source`
  - scaffold for reading line-based data from a Photon 2 over USB serial
  - supports JSON lines and the current `Amp: ... | Vol: ... | Dyn: ...` serial format

## Copyright

Copyright (c) 2026 wuisabel-gif. All rights reserved.

## Local practice measurement foundation

`desktop_dashboard.wav_import.load_wav(path)` loads only local 16-bit PCM WAV
(mono/stereo, 8–96 kHz, nonempty, at most 60 seconds / 32 MB).
`desktop_dashboard.practice.analyze(path)` returns 80 ms pitch/RMS frames at a
20 ms hop, with time in seconds from the file start. Pitch uses a normalized
squared-difference periodicity heuristic over approximately 55–1000 Hz.
Confidence is a periodicity score, not a calibrated probability. Quiet frames
(below about −50 dBFS RMS) and frames without a strong periodic candidate have
no pitch. Stereo is averaged to mono; opposing channels can cancel.

Trend is a centered 0.5 s median using continuous voiced frames only. It is
withheld at edges, gaps and octave-sized discontinuities. Short variation is
pitch minus trend, not a validated vibrato measure. Pitch is in cents relative
to A3 / 220 Hz, without inferring the intended note. Relative RMS is normalized
to each take's loudest frame: useful for shape, not absolute volume or SPL.
Different microphone gains, automatic gain control, noise and room acoustics
limit comparison. The analysis resamples with a simple FFT low-pass; transients
and boundaries can affect results. Polyphony, strong overtones and real bow
noise can produce errors, including octaves.

Tests use generated synthetic signals, not real cello validation:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

## Compare local takes

Run the dashboard and select **Compare local WAVs**, or launch the isolated
practice window (no mock or serial sources):

```bash
.venv/bin/python -m desktop_dashboard.ui.practice_window
```

Import take 1 and take 2 of the same sustained-note exercise. Reimporting
replaces that slot; errors preserve previous takes. Analysis runs in a worker
thread. Purple is take 1 and gold is take 2. Charts share seconds from file
start and retain original durations; they do not stretch or infer musical
alignment. No arbitrary-score timing analysis is provided. Plot gaps mean no
supported measurement. For silence, the normalized RMS shape is flat and says
nothing about absolute loudness. Files shorter than an 80 ms frame have no pitch.

Generate optional, clearly labelled **synthetic** demonstration WAVs:

```bash
.venv/bin/python tests/synthetic.py /tmp/cello-synthetic
```

Run headless UI checks with:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -v
```

The UI test saves `practice-preview.png` in the repository root for visual QA.
Audio remains local; the practice window has no recording or network features.

## Local practice cues

The observation panel uses deterministic rules, not an AI model or an expert
teacher. It reports the longest continuous supported trend interval, change
between 200 ms end-window medians, and the middle-80% span of short variation.
It withholds observations below 60% voiced coverage, on register-sized pitch
changes, or without one continuous second of trend. The periodicity threshold
and these gates are heuristic; octave mistakes can still pass on real audio.
File-duration differences include silence and are not musical timing judgments.
Listen back in your own player; this increment does not provide playback.

Before drawing musical conclusions, compare measurements against a trusted
reference and test representative real cello recordings locally. Synthetic
validation alone cannot prove pitch, vibrato, intonation or teaching accuracy.

## Import MOV audio locally

The practice importer accepts `.mov` as well as `.wav`. Click **Import take 1**
or **Import take 2**, paste the local file path (absolute or `~/...`), and
confirm. Cancel leaves existing takes unchanged. A simple path dialog avoids
macOS accessibility crashes observed in Qt file-tree dialogs during testing.
Before importing a MOV,
set **MOV only • start** (seconds into the source) and **duration** (0.1–60 s;
default 30 s). The selected interval is decoded from the first audio track,
without playing audio or decoding video. The take label records its actual
source interval. Charts start at each excerpt's zero; observation timestamps
refer to the source. Near the source end the excerpt can be shorter than the
requested duration. An empty/out-of-range excerpt produces an error.

MOV support requires an already installed `ffmpeg` on PATH. The app does not
install or download it. If it is missing, invalid, or cannot find an audio
track, an explanatory error preserves the previous takes. Decoding is local,
limited to 30 seconds of wall time and local-file protocols, and uses a private
temporary PCM WAV that is removed after loading. Sources are never changed.
WAV import retains its existing 60-second/32-MB limit; MOV files are limited
to 2 GB. Excerpt controls do not trim WAVs.

A musical performance with changing notes is outside sustained-note coaching.
Treat coverage, large pitch changes and relative loudness as descriptive signals;
they cannot distinguish note changes from octave errors or assess technique.

## Synthetic pitch benchmark

Run `.venv/bin/python -m benchmarks.yin_pitch --json-path /tmp/cello-yin-current.json`.
See [benchmark definitions and limitations](../docs/yin-benchmark.md) for known
frequencies, cents error, voiced coverage, silence/noise rejection, octave errors,
transition exclusions and the baseline/improved reports. The detector checks
for a substantially deeper full-period match when a strong overtone could cause
an octave error; this is still a heuristic, not real cello accuracy validation.
