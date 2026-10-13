"""New ending of the FlyingTuna edit, rendered alone: track 0:56.18-1:11.12 (beats 177-224).

The pounding cuts up to the drop into the calm are reused as rendered for the main part.
The calm (beats 192-224) is rebuilt so the #1 reads at once:
  b192-198  ranking panel "#1 · 15 032pp" with the caption from the first frame, his "NUMBER ONE!" shout
  b198-212  the next-day reaction: "Oh shit" / "YES!" / "oh my fucking gosh"
  b212-224  "I will go to say to my parents", music and picture fade out on the last bar
usage: python -I build_ending.py <workdir>
"""
import os
import subprocess
import sys

S = "/tmp/claude-0/-home-user-Claude-code/a61365b4-59b2-5d5f-8537-7f9c9b765619/scratchpad"
LIB = "/home/user/Claude-code/osu-edit/clips/ft_library/03_number_one_2019-02-11"
MAINW = "/home/user/Claude-code/osu-edit/out/ft_main/work"
SONG = f"{S}/tracks_x/2143023/audio.mp3"
FONT = f"{S}/fonts/LilitaOne.ttf"
WORK = sys.argv[1]
os.makedirs(WORK, exist_ok=True)
BEAT = 60 / 189
FPS = 60


def F(b):
    return round(b * BEAT * FPS)


TOP1 = f"{LIB}/2019-02-11_top1_moment_60s.mp4"
REAL = f"{LIB}/2019-02-12_when_tuna_really_gets_1.mp4"
PAR = f"{LIB}/2019-02-11_i_will_go_to_say_to_my_parents.mp4"


def caption(cap, date):
    a = "min(1,t*14)"
    return (f"drawtext=fontfile={FONT}:text='{cap}':fontsize=150:fontcolor=white:borderw=12:bordercolor=0x15121a"
            f":shadowcolor=0x15121a:shadowx=0:shadowy=10:x=(w-tw)/2:y=h*0.20:alpha='{a}',"
            f"drawtext=fontfile={FONT}:text='{date}':fontsize=60:fontcolor=0xffd84a:borderw=8:bordercolor=0x15121a"
            f":x=(w-tw)/2:y=h*0.20+175:alpha='{a}'")


# (beat0, beat1, source, source_in, caption?)
CALM = [
    (192, 198, TOP1, 32.30, ("#1 · 15,032PP", "11.02.2019")),
    (198, 201.5, REAL, 0.49, None),
    (201.5, 204.5, REAL, 9.85, None),
    (204.5, 212, REAL, 13.57, None),
    (212, 224, PAR, 19.60, None),
]
B_START = 177  # first reused cut (main-part segment index 68)
reuse = [f"{MAINW}/seg_{k:03d}.mp4" for k in range(68, 78)]
segs = list(reuse)
for i, (b0, b1, src, sin, cap) in enumerate(CALM):
    n = F(b1) - F(b0)
    vf = "fps=60,scale=1920:1080:flags=lanczos,setsar=1"
    if cap:
        vf += "," + caption(*cap)
    if i == len(CALM) - 1:  # fade to black over the last bar
        vf += f",fade=t=out:st={n / FPS - 4 * BEAT:.3f}:d={4 * BEAT:.3f}"
    out = f"{WORK}/calm_{i}.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{sin:.3f}", "-i", src, "-frames:v", str(n), "-vf", vf, "-an",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "14", "-pix_fmt", "yuv420p", "-r", "60", out], check=True)
    segs.append(out)
with open(f"{WORK}/concat.txt", "w") as f:
    for s in segs:
        f.write(f"file '{s}'\n")
video = f"{WORK}/video.mp4"
subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", f"{WORK}/concat.txt", "-c", "copy", video], check=True)

# ---------------- audio
t_start = F(B_START) / FPS
t_end = F(224) / FPS
dur = t_end - t_start
calm0 = F(192) / FPS - t_start
fade0 = F(220) / FPS - t_start


def at(b):  # seconds from the start of this render
    return F(b) / FPS - t_start


voice = "highpass=f=110,lowpass=f=7000,acompressor=threshold=0.1:ratio=5:attack=4:release=140:makeup=2"
parts = []
inputs = ["-i", video, "-i", SONG, "-i", PAR, "-i", REAL, "-i", PAR]
fc = (f"[1:a]atrim={t_start:.4f}:{t_end:.4f},asetpts=PTS-STARTPTS,aresample=48000,"
      f"volume='if(gte(t,{calm0:.3f}),0.62,1)':eval=frame,afade=t=out:st={fade0:.3f}:d={dur - fade0:.3f}[song];")
# "NUMBER ONE!" lands right after the music drops
fc += (f"[2:a]atrim=16.05:17.70,asetpts=PTS-STARTPTS,aresample=48000,{voice},volume=1.2dB,afade=t=in:d=0.02,afade=t=out:st=1.45:d=0.2,"
       f"adelay=delays={int((calm0 + 0.05) * 1000)}:all=1[v0];")
# the next-day reaction, cut to the beat like the picture (gated so his game's music stays out)
real_parts = [(198, 201.5, 0.49), (201.5, 204.5, 9.85), (204.5, 212, 13.57)]
labels = []
for j, (b0, b1, sin) in enumerate(real_parts):
    d = (F(b1) - F(b0)) / FPS
    fc += (f"[3:a]atrim={sin:.3f}:{sin + d:.3f},asetpts=PTS-STARTPTS,aresample=48000,highpass=f=110,lowpass=f=7000,"
           f"agate=threshold=0.07:ratio=8:attack=2:release=150:range=0.1,"
           f"acompressor=threshold=0.1:ratio=5:attack=4:release=140:makeup=2,volume=1dB,afade=t=in:d=0.015,afade=t=out:st={d - 0.03:.3f}:d=0.03,"
           f"adelay=delays={int(at(b0) * 1000)}:all=1[r{j}];")
    labels.append(f"[r{j}]")
d_par = (F(224) - F(212)) / FPS
fc += (f"[4:a]atrim=19.60:{19.60 + d_par:.3f},asetpts=PTS-STARTPTS,aresample=48000,{voice},volume=1dB,afade=t=in:d=0.02,"
       f"afade=t=out:st={d_par - 4 * BEAT:.3f}:d={4 * BEAT:.3f},adelay=delays={int(at(212) * 1000)}:all=1[v2];")
fc += f"[song][v0]{''.join(labels)}[v2]amix=inputs={3 + len(labels)}:normalize=0:duration=first,alimiter=limit=0.89:level=false[a]"
final = f"{WORK}/ending.mp4"
subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", *inputs, "-filter_complex", fc, "-map", "0:v", "-map", "[a]", "-c:v", "copy",
                "-c:a", "aac", "-b:a", "256k", "-shortest", "-movflags", "+faststart", final], check=True)
print("ending", round(dur, 3), "s from track", round(t_start, 3), "->", final)
