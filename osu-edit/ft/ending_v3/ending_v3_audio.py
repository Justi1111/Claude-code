"""Audio for ending v3: song (ducked in the calm, drum hit at 71.111 then a short fade), his voice in the
same cuts as the picture, and a few synthesized accents (impact on the calm hit, riser + shimmer into #1,
thumps on the shout words, boom on the final hit).

usage: python -I ending_v3_audio.py <video.mp4> <out.mp4>
"""
import os
import subprocess
import sys

import numpy as np

S = os.environ.get("FT_WORK", "/tmp/claude-0/-home-user-Claude-code/a61365b4-59b2-5d5f-8537-7f9c9b765619/scratchpad")  # mattes, fonts2, tracks_x, models
LIB = "/home/user/Claude-code/osu-edit/clips/ft_library/03_number_one_2019-02-11"
REAL = f"{LIB}/2019-02-12_when_tuna_really_gets_1.mp4"
PAR = f"{LIB}/2019-02-11_i_will_go_to_say_to_my_parents.mp4"
SONG = f"{S}/tracks_x/2143023/audio.mp3"
BEAT = 60 / 189
FPS = 60
SR = 48000


def F(b):
    return round(b * BEAT * FPS)


T0 = F(177) / FPS
T_END = (F(224) + 63) / FPS
DUR = T_END - T0
TB = lambda b: b * BEAT  # noqa: E731

video, out = sys.argv[1], sys.argv[2]

# ---------------- synthesized accents
n = int(DUR * SR) + SR
fx = np.zeros(n, np.float32)
rng = np.random.default_rng(5)


def put(sig, t, gain_db):
    i = int((t - T0) * SR)
    j = min(n, i + len(sig))
    if i < n:
        fx[i:j] += sig[:j - i] * 10 ** (gain_db / 20)


def boom(dur=1.1, f0=64, f1=30):
    t = np.arange(int(dur * SR)) / SR
    f = f1 + (f0 - f1) * np.exp(-t * 5)
    ph = 2 * np.pi * np.cumsum(f) / SR
    s = np.sin(ph) * np.exp(-t * 3.2)
    click = rng.normal(0, 1, len(t)) * np.exp(-t * 60)
    return (s + 0.25 * np.convolve(click, np.ones(8) / 8, mode="same")).astype(np.float32)


def thump(dur=0.35):
    t = np.arange(int(dur * SR)) / SR
    f = 48 + 70 * np.exp(-t * 30)
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 12)).astype(np.float32)


def riser(dur=0.5):
    t = np.arange(int(dur * SR)) / SR
    noise = rng.normal(0, 1, len(t)).astype(np.float32)
    spec = np.fft.rfft(noise)
    freqs = np.fft.rfftfreq(len(noise), 1 / SR)
    spec *= np.exp(-((np.log(freqs + 1) - np.log(2500)) ** 2) / 1.2)
    s = np.fft.irfft(spec, len(noise)).astype(np.float32)
    s /= np.abs(s).max() + 1e-9
    return s * (t / dur) ** 2.5


def shimmer(dur=1.6):
    t = np.arange(int(dur * SR)) / SR
    s = np.zeros_like(t)
    for f, a in ((1568, 1.0), (2093, 0.7), (3136, 0.5), (4186, 0.35), (2349, 0.4)):
        s += a * np.sin(2 * np.pi * f * t + rng.uniform(0, 6)) * (1 + 0.3 * np.sin(2 * np.pi * 5.5 * t))
    return (s / 2.5 * np.exp(-t * 2.2) * np.clip(t / 0.01, 0, 1)).astype(np.float32)


put(boom(), TB(192), -9)           # the calm hits: flash + letterbox
put(thump(), 62.907, -17)          # YES
put(thump(), 63.860, -15)          # YES!
put(thump(), 66.534, -17)          # GOD
put(riser(0.45), TB(210) - 0.45, -20)
put(shimmer(), TB(210), -19)       # #1
put(boom(1.3, 70, 28), TB(224), -9)  # final hit with the drums
fx_path = f"{S}/ending_v3_fx.wav"
pcm = (np.clip(fx, -1, 1) * 32767).astype(np.int16)
import wave  # noqa: E402

with wave.open(fx_path, "wb") as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())

# ---------------- voice cuts: (source, src_in, src_out, track_time, gain_db, gate)
VOICE = [
    (REAL, 0.00, 1.905, TB(192), 2, True),
    (REAL, 9.43, 10.382, TB(198), 3, True),
    (REAL, 12.27, 12.905, TB(201), 3, True),
    (REAL, 13.55, 15.772, TB(203), 3, True),
    (REAL, 17.00, 19.54, TB(210), -5, True),
    (PAR, 19.80, 22.40, TB(218), 3, False),
]
inputs = ["-i", video, "-i", SONG, "-i", fx_path]
src_idx = {}
for src, *_ in VOICE:
    if src not in src_idx:
        src_idx[src] = 3 + len(src_idx)
        inputs += ["-i", src]
a_calm = TB(192) - T0
a_hit = TB(224) - T0
fc = (f"[1:a]atrim={T0:.4f}:{T_END:.4f},asetpts=PTS-STARTPTS,aresample={SR},"
      f"volume='if(lt(t,{a_calm:.4f}),1,if(lt(t,{a_hit:.4f}),0.55,1))':eval=frame,"
      f"afade=t=out:st={TB(224) - T0 + 0.29:.3f}:d=0.7[song];")
labels = []
for i, (src, a, b, tt, g, gate) in enumerate(VOICE):
    d = b - a
    chain = f"[{src_idx[src]}:a]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS,aresample={SR},highpass=f=110,lowpass=f=7500,"
    if gate:
        chain += "agate=threshold=0.08:ratio=4:range=0.18:attack=3:release=150,"
    chain += (f"acompressor=threshold=0.25:ratio=2.5:attack=5:release=150:makeup=1.5,volume={g}dB,"
              f"afade=t=in:d=0.012,afade=t=out:st={d - 0.02:.3f}:d=0.02,adelay=delays={int((tt - T0) * 1000)}:all=1[v{i}];")
    fc += chain
    labels.append(f"[v{i}]")
fc += f"[2:a]aresample={SR}[fx];"
fc += f"[song][fx]{''.join(labels)}amix=inputs={2 + len(labels)}:normalize=0:duration=first,alimiter=limit=0.9:level=false[a]"
subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", fc, "-map", "0:v", "-map", "[a]", "-c:v", "copy",
                "-c:a", "aac", "-b:a", "256k", "-shortest", "-movflags", "+faststart", out], check=True)
print("muxed", out, round(DUR, 3), "s")
