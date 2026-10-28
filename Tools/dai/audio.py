"""
Procedurally synthesised ambient loops and UI one-shots (16-bit mono WAV).

Loops are generated in the frequency domain / with integer-cycle modulation so
they are perfectly periodic: they loop seamlessly in Unreal (bLooping).
"""

import math
import os
import wave

import numpy as np

from . import config as C

SR = 22050


def _write(path, x, sr=SR):
    x = np.asarray(x, np.float64)
    peak = np.max(np.abs(x)) + 1e-9
    x = x / peak * 0.85
    data = (x * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(data.tobytes())


def band_noise(n, lo, hi, seed, tilt=0.0):
    """Periodic noise with energy between lo..hi Hz (FFT mask), optional spectral tilt (dB/oct-ish)."""
    r = np.random.default_rng(seed)
    F = np.fft.rfft(r.standard_normal(n))
    f = np.fft.rfftfreq(n, 1.0 / SR)
    mask = ((f >= lo) & (f <= hi)).astype(np.float64)
    # smooth edges
    mask *= np.clip((f - lo * 0.8) / (lo * 0.2 + 1e-9), 0, 1) * np.clip((hi * 1.25 - f) / (hi * 0.25), 0, 1)
    if tilt:
        mask *= (np.maximum(f, 1.0) / max(lo, 1.0)) ** (-tilt)
    x = np.fft.irfft(F * mask, n)
    return x / (np.std(x) + 1e-9)


def periodic_lfo(n, cycles, phase=0.0):
    t = np.arange(n) / n
    return np.sin(2 * math.pi * cycles * t + phase)


def ocean(dur=24.0):
    n = int(SR * dur)
    surf = band_noise(n, 60, 2500, 1, tilt=0.6)
    hiss = band_noise(n, 1500, 7000, 2, tilt=0.3) * 0.25
    t = np.arange(n) / n
    env = np.zeros(n)
    for k, (cyc, ph) in enumerate([(3, 0.0), (4, 1.3), (5, 2.1)]):
        w = np.clip(np.sin(2 * math.pi * cyc * t + ph), 0, 1) ** 3
        env += w * (0.7 + 0.1 * k)
    env = 0.35 + env
    return surf * env + hiss * (0.3 + env * 0.5)


def wind(dur=20.0):
    n = int(SR * dur)
    x = band_noise(n, 150, 1400, 3, tilt=0.8)
    env = 0.6 + 0.25 * periodic_lfo(n, 2, 0.4) + 0.15 * periodic_lfo(n, 5, 1.1)
    whistle = band_noise(n, 600, 900, 4) * (0.2 + 0.2 * periodic_lfo(n, 3, 2.0))
    return x * env + whistle * 0.3


def birds(dur=20.0, seed=5):
    n = int(SR * dur)
    r = np.random.default_rng(seed)
    out = wind(dur) * 0.15
    t_all = np.arange(n) / SR
    for _ in range(int(dur * 1.6)):
        start = r.uniform(0, dur - 0.6)
        notes = r.integers(2, 6)
        f0 = r.uniform(2200, 4200)
        for k in range(notes):
            s = int((start + k * r.uniform(0.08, 0.16)) * SR)
            L = int(r.uniform(0.05, 0.12) * SR)
            if s + L >= n:
                continue
            tt = np.arange(L) / SR
            sweep = f0 * (1 + r.uniform(-0.3, 0.4) * tt / tt[-1])
            ph = 2 * math.pi * np.cumsum(sweep) / SR
            env = np.sin(math.pi * np.arange(L) / L) ** 2
            out[s:s + L] += (np.sin(ph) + 0.3 * np.sin(2 * ph)) * env * r.uniform(0.3, 0.8)
    return out


def volcano(dur=24.0):
    n = int(SR * dur)
    rumble = band_noise(n, 20, 120, 6, tilt=1.0)
    env = 0.7 + 0.3 * periodic_lfo(n, 3, 0.3)
    r = np.random.default_rng(7)
    booms = np.zeros(n)
    for _ in range(4):
        s = int(r.uniform(0, n - SR * 3))
        L = int(SR * 2.5)
        e = np.exp(-np.arange(L) / (SR * 0.6))
        booms[s:s + L] += band_noise(L, 25, 90, int(s)) * e * 1.5
    hiss = band_noise(n, 800, 4000, 8) * 0.08
    return rumble * env + booms + hiss


def waterfall(dur=16.0):
    n = int(SR * dur)
    x = band_noise(n, 80, 5000, 9, tilt=0.35)
    return x * (0.9 + 0.1 * periodic_lfo(n, 7))


def hot_spring(dur=16.0):
    n = int(SR * dur)
    base = band_noise(n, 200, 3000, 10, tilt=0.6) * 0.15
    r = np.random.default_rng(11)
    out = base.copy()
    for _ in range(int(dur * 9)):
        s = int(r.uniform(0, n - SR * 0.2))
        L = int(SR * r.uniform(0.03, 0.09))
        f0 = r.uniform(300, 900)
        tt = np.arange(L) / SR
        freq = f0 * (1 + 2.5 * tt / tt[-1])
        ph = 2 * math.pi * np.cumsum(freq) / SR
        env = np.exp(-tt * 40) * np.clip(tt * 600, 0, 1)
        out[s:s + L] += np.sin(ph) * env * r.uniform(0.2, 0.6)
    return out


def crowd(dur=20.0):
    n = int(SR * dur)
    voices = np.zeros(n)
    r = np.random.default_rng(12)
    for v in range(10):
        x = band_noise(n, 250, 2800, 20 + v, tilt=0.5)
        cyc = r.integers(30, 60)
        env = np.clip(periodic_lfo(n, int(cyc), r.uniform(0, 6)) * 0.5 + 0.5, 0, 1) ** 2
        voices += x * env * 0.3
    swell = 0.7 + 0.3 * periodic_lfo(n, 2, 1.0)
    return voices * swell


def one_shot_chime(notes=(880, 1108.7, 1318.5), spacing=0.09, dur=1.4):
    n = int(SR * dur)
    out = np.zeros(n)
    for k, f in enumerate(notes):
        s = int(k * spacing * SR)
        tt = np.arange(n - s) / SR
        env = np.exp(-tt * 3.5) * np.clip(tt * 200, 0, 1)
        out[s:] += (np.sin(2 * math.pi * f * tt) + 0.4 * np.sin(2 * math.pi * f * 2.01 * tt)) * env
    return out


def duel_start(dur=1.8):
    n = int(SR * dur)
    tt = np.arange(n) / SR
    sweep_f = 200 + 1400 * (tt / dur) ** 2
    ph = 2 * math.pi * np.cumsum(sweep_f) / SR
    sweep = np.sin(ph) * np.clip(tt * 4, 0, 1) * np.exp(-np.maximum(tt - 1.0, 0) * 6)
    whoosh = band_noise(n, 400, 6000, 30) * np.sin(math.pi * np.clip(tt / dur, 0, 1)) * 0.4
    chord = np.zeros(n)
    s = int(1.0 * SR)
    t2 = np.arange(n - s) / SR
    for f in (523.25, 659.25, 783.99, 1046.5):
        chord[s:] += np.sin(2 * math.pi * f * t2) * np.exp(-t2 * 2.5)
    return sweep * 0.6 + whoosh + chord * 0.5


def card_draw(dur=0.35):
    n = int(SR * dur)
    tt = np.arange(n) / SR
    env = np.sin(math.pi * tt / dur) ** 2
    return band_noise(n, 1500, 9000, 31) * env


def ui_click(dur=0.08):
    n = int(SR * dur)
    tt = np.arange(n) / SR
    return np.sin(2 * math.pi * 1800 * tt) * np.exp(-tt * 70)


SOUNDS = {
    "A_Ocean": (ocean, True), "A_Wind": (wind, True), "A_Forest": (birds, True), "A_Volcano": (volcano, True),
    "A_Waterfall": (waterfall, True), "A_HotSpring": (hot_spring, True), "A_Crowd": (crowd, True),
    "A_Discover": (one_shot_chime, False), "A_DuelStart": (duel_start, False), "A_CardDraw": (card_draw, False),
    "A_UIClick": (ui_click, False),
}


def build_audio(log=print):
    os.makedirs(C.OUT_AUDIO, exist_ok=True)
    for name, (fn, _loop) in SOUNDS.items():
        _write(os.path.join(C.OUT_AUDIO, name + ".wav"), fn())
    log(f"  audio: {len(SOUNDS)} sounds")
    return {k: v[1] for k, v in SOUNDS.items()}
