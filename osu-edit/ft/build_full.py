"""The whole FlyingTuna edit: track 0:15.23 to the end of the #1 clip.

Picture: intro (intro_clip/build_intro.sh: the end of the achieve-list clip) -> the main part cuts up to the calm
(main_part/build_main.py) -> the #1 clip with its plate (main_part/build_ending.py).
Sound: the song from 0:15.23 (ducked and muffled under the intro, full from the drop at 0:20.32, lower in the calm,
gone by 1:07.30 when the map ends in the #1 clip), his achieve-list voice with the scream running over the drop, and
the #1 clip's own sound from the calm on.

usage: FT_MAIN_WORK=<build_main.py workdir> FT_END_WORK=<build_ending.py workdir> python -I build_full.py <out.mp4>
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "main_part"))
import build_ending as E  # noqa: E402

INTRO_V = os.environ.get("FT_INTRO_V", "/home/user/Claude-code/osu-edit/out/ft_intro_clip/intro_v.mp4")
ACHIEVE = os.path.normpath(os.path.join(HERE, "..", "clips/ft_library/09_owc2024/2024-12-08_achieve_list_reading.mp4"))
ENDW = os.environ.get("FT_END_WORK", "/home/user/Claude-code/osu-edit/out/ft_ending_v6/work")
INTRO_F0 = 914                      # track frame of the first intro frame (0:15.233)
VOICE_IN, VOICE_OUT = 15.201333, 20.75   # achieve-list clip; track = clip + 0.032 s, the scream ends ~20.75

out = sys.argv[1]
work = os.path.dirname(os.path.abspath(out))
segs = [INTRO_V] + E.main_segments(64) + [f"{ENDW}/clip_1.mp4"]
with open(f"{work}/full_concat.txt", "w") as f:
    for s in segs:
        f.write(f"file '{s}'\n")
video = f"{work}/full_video.mp4"
subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", f"{work}/full_concat.txt",
                "-c", "copy", video], check=True)

t0 = INTRO_F0 / E.FPS
t_drop = E.F(64) / E.FPS
calm_out = (E.F(192) - INTRO_F0) / E.FPS
fc = (f"[1:a]asplit=2[sa][sb];"
      f"[sa]atrim={t0:.6f}:{t_drop:.6f},asetpts=PTS-STARTPTS,aresample=48000,volume=-9dB,lowpass=f=1100:p=2,"
      f"afade=t=in:d=0.15[s1];"
      f"[sb]{E.song_chain(t_drop, 's2')};"
      f"[s1][s2]concat=n=2:v=0:a=1[song];"
      f"[2:a]atrim={VOICE_IN}:{VOICE_OUT},asetpts=PTS-STARTPTS,aresample=48000,afade=t=in:st=0.09:d=0.03,"
      f"acompressor=threshold=0.1:ratio=4:attack=5:release=150:makeup=2,volume=4dB,"
      f"afade=t=out:st={VOICE_OUT - VOICE_IN - 0.2:.4f}:d=0.2[vo];"
      f"[3:a]{E.clip_audio_chain(calm_out, 'clip')};"
      f"[song][vo][clip]amix=inputs=3:normalize=0:duration=longest,alimiter=limit=0.9:level=false[a]")
subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", video, "-i", E.SONG, "-i", ACHIEVE, "-i", E.CLIP,
                "-filter_complex", fc, "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k",
                "-shortest", "-movflags", "+faststart", out], check=True)
n = 305 + (E.F(192) - E.F(64)) + E.n_clip
print("full edit", n, "frames,", round(n / E.FPS, 3), "s ->", out)
