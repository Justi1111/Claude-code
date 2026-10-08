"""Audio synthesis and processing helpers (drums, synths, transition FX)."""
import numpy as np
from scipy import signal

SR = 44100
rng = np.random.default_rng(7)


def n_samples(dur):
    return int(round(dur * SR))


def t_arr(dur):
    return np.arange(n_samples(dur)) / SR


def midi_hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def _sos(kind, f, order=2):
    return signal.butter(order, f, btype=kind, fs=SR, output="sos")


def lowpass(x, f, order=2):
    return signal.sosfilt(_sos("low", f, order), x, axis=0)


def highpass(x, f, order=2):
    return signal.sosfilt(_sos("high", f, order), x, axis=0)


def bandpass(x, lo, hi, order=2):
    return signal.sosfilt(_sos("band", [lo, hi], order), x, axis=0)


def stereo(x):
    return np.stack([x, x], axis=1) if x.ndim == 1 else x


def place(buf, x, at):
    """Mix x into buf starting at sample `at` (clipped to bounds)."""
    x = stereo(x)
    if at < 0:
        x, at = x[-at:], 0
    end = min(len(buf), at + len(x))
    if end > at:
        buf[at:end] += x[: end - at]


# ---------------------------------------------------------------- drums
def kick(f0=170, f1=42, decay=0.22, click=0.35):
    t = t_arr(0.45)
    f = f1 + (f0 - f1) * np.exp(-t / 0.035)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / decay)
    s += rng.standard_normal(len(t)) * np.exp(-t / 0.004) * click
    return np.tanh(s * 1.8) * 0.9


def snare(tone=190, decay=0.11):
    t = t_arr(0.3)
    body = np.sin(2 * np.pi * tone * t) * np.exp(-t / 0.05) * 0.7
    noise = bandpass(rng.standard_normal(len(t)), 1200, 9000) * np.exp(-t / decay)
    return np.tanh((body + noise * 1.4) * 1.2) * 0.7


def hat(open_=False):
    t = t_arr(0.25 if open_ else 0.07)
    n = highpass(rng.standard_normal(len(t)), 7000, 4)
    return n * np.exp(-t / (0.09 if open_ else 0.012)) * 0.35


def crash(dur=1.6):
    t = t_arr(dur)
    n = highpass(rng.standard_normal(len(t)), 4000, 2)
    return n * np.exp(-t / 0.55) * 0.35


def hitsound(clap=False):
    """osu!-like soft hitnormal (+ optional clap)."""
    t = t_arr(0.12)
    s = bandpass(rng.standard_normal(len(t)), 1800, 7000) * np.exp(-t / 0.018) * 0.8
    s += np.sin(2 * np.pi * 920 * t) * np.exp(-t / 0.025) * 0.35
    if clap:
        c = bandpass(rng.standard_normal(len(t)), 900, 3500) * np.exp(-t / 0.05)
        s += c * 0.9
    return s * 0.5


# ---------------------------------------------------------------- synths
def saw(freq, t, phase=0.0):
    return signal.sawtooth(2 * np.pi * freq * t + phase)


def supersaw(freq, dur, voices=5, detune=0.011):
    t = t_arr(dur)
    out = np.zeros((len(t), 2))
    for i in range(voices):
        d = 1 + detune * (i - (voices - 1) / 2) / ((voices - 1) / 2)
        for ch in range(2):
            out[:, ch] += saw(freq * d * (1 + 0.002 * (ch - 0.5)), t, rng.uniform(0, 6.28))
    return out / voices


def pluck(freq, dur, decay=0.12, square=False):
    t = t_arr(dur)
    w = signal.square(2 * np.pi * freq * t) if square else saw(freq, t)
    w = w + 0.5 * saw(freq * 2.003, t)
    return lowpass(w, min(9000, freq * 8)) * np.exp(-t / decay)


def bass_note(freq, dur, cutoff=900, dist=2.5):
    t = t_arr(dur)
    w = saw(freq, t) + 0.6 * signal.square(2 * np.pi * freq / 2 * t)
    w = np.tanh(lowpass(w, cutoff, 2) * dist)
    env = np.minimum(1, t / 0.004) * np.exp(-t / (dur * 1.5))
    return w * env


def power_chord(freq, dur):
    """Distorted guitar-ish power chord."""
    t = t_arr(dur)
    w = sum(saw(freq * r, t, rng.uniform(0, 6)) for r in (1, 1.498, 2, 2.997))
    w = np.tanh(lowpass(w, 3500, 2) * 6) * 0.5
    env = np.minimum(1, t / 0.003) * np.exp(-t / (dur * 2))
    return w * env


# ---------------------------------------------------------------- FX
def stft_filter_sweep(x, f_start, f_end, kind="low", curve=2.0):
    """Time-varying low/high-pass via STFT masking (smooth, click free)."""
    x = stereo(x)
    nper = 2048
    out = np.zeros_like(x)
    for ch in range(2):
        f, tt, Z = signal.stft(x[:, ch], SR, nperseg=nper)
        prog = np.clip(tt / max(tt[-1], 1e-6), 0, 1) ** curve
        cut = np.exp(np.log(f_start) + (np.log(f_end) - np.log(f_start)) * prog)
        if kind == "low":
            mask = 1 / (1 + (f[:, None] / cut[None, :]) ** 6)
        else:
            mask = 1 / (1 + (cut[None, :] / np.maximum(f[:, None], 1)) ** 6)
        _, y = signal.istft(Z * mask, SR, nperseg=nper)
        out[:, ch] = y[: len(x)] if len(y) >= len(x) else np.pad(y, (0, len(x) - len(y)))
    return out


def riser(dur, f_lo=300, f_hi=12000):
    t = t_arr(dur)
    noise = rng.standard_normal((len(t), 2))
    noise = stft_filter_sweep(noise, f_lo, f_hi, kind="low", curve=1.5)
    pitch = 120 * 2 ** (t / dur * 3)
    tone = signal.sawtooth(2 * np.pi * np.cumsum(pitch) / SR) * 0.15
    env = (t / dur) ** 2
    return (noise * 0.5 + stereo(tone)) * env[:, None]


def impact(dur=1.4):
    t = t_arr(dur)
    f = 30 + 70 * np.exp(-t / 0.08)
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.45)
    hit = lowpass(rng.standard_normal(len(t)), 2500) * np.exp(-t / 0.06) * 0.8
    s = np.tanh((boom * 1.4 + hit) * 1.5)
    return stereo(s) * 0.9 + reverb(stereo(hit * 0.4), 1.2, wet=1.0)[: len(t)]


def whoosh(dur=0.35):
    t = t_arr(dur)
    env = np.sin(np.pi * t / dur) ** 2
    n = rng.standard_normal((len(t), 2))
    n = stft_filter_sweep(n, 400, 6000, kind="low", curve=1.0)
    return n * env[:, None] * 0.5


def reverse_cymbal(dur=0.6):
    c = crash(dur)
    return stereo(c[::-1]) * 1.2


def reverb(x, decay=1.5, wet=0.35):
    x = stereo(x)
    n = n_samples(decay * 1.6)
    t = np.arange(n) / SR
    out = np.zeros((len(x) + n - 1, 2))
    for ch in range(2):
        ir = rng.standard_normal(n) * np.exp(-t / (decay / 6.9))
        ir = lowpass(ir, 6000)
        ir /= np.sqrt(np.sum(ir ** 2))
        out[:, ch] = signal.fftconvolve(x[:, ch], ir)
    out[: len(x)] *= wet
    out[len(x):] *= wet
    dry = np.zeros_like(out)
    dry[: len(x)] = x * (1 - wet * 0.3)
    return dry + out * 0.6


def varispeed(x, rate):
    """Play x with a per-output-sample playback rate (tape stop etc.).
    rate: array of rates for each output sample. Returns output + read positions."""
    x = stereo(x)
    pos = np.concatenate([[0], np.cumsum(rate[:-1])])
    pos = np.clip(pos, 0, len(x) - 1)
    out = np.stack([np.interp(pos, np.arange(len(x)), x[:, ch]) for ch in range(2)], axis=1)
    return out, pos


def fade(x, fin=0.004, fout=0.004):
    x = stereo(x).copy()
    a, b = n_samples(fin), n_samples(fout)
    if a:
        x[:a] *= np.linspace(0, 1, a)[:, None]
    if b:
        x[-b:] *= np.linspace(1, 0, b)[:, None]
    return x


def rms(x):
    return float(np.sqrt(np.mean(np.square(x)) + 1e-12))


def master(x, drive=1.6, ceiling=0.93):
    x = np.tanh(x * drive) / np.tanh(drive)
    return x / max(np.max(np.abs(x)), 1e-9) * ceiling
