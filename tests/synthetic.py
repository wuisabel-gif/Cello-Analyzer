"""Deterministic SYNTHETIC signals, not recordings of a cello."""
import wave
import numpy as np

def fixture(path, kind='steady', rate=16000, gain=.3):
    t = np.arange(rate*3)/rate
    cents = {'steady': np.zeros(len(t)), 'drift': 40*t/3,
             'vibrato': 20*np.sin(2*np.pi*5*t), 'octave': np.where(t<1.5, 0, 1200)}.get(kind, np.zeros(len(t)))
    phase = np.cumsum(220*2**(cents/1200))*2*np.pi/rate
    x = gain*np.sin(phase)
    if kind == 'silence':
        x *= 0
    if kind == 'noise':
        x = np.random.default_rng(42).normal(0, gain, len(t))
    with wave.open(str(path), 'wb') as wav:
        wav.setparams((1, 2, rate, 0, 'NONE', 'not compressed'))
        wav.writeframes((np.clip(x,-1,1)*32767).astype('<i2').tobytes())


