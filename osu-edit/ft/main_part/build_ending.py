"""Ending of the FlyingTuna edit (v5), rendered alone: track 0:56.18 to ~1:23.4.

The pounding cuts are reused from the main part render as they are (with their #4 / #2 captions).
From the calm (1:00.952) the real #1 moment plays as one uncut piece: the clip "топ 1" (Super Driver
[Fiery's Extreme] HDDT, 778pp, 11.02.2019 22:57 KST) from its last spinner. The in-point is chosen so the
result screen with "Overall Ranking #1 (+3)" appears exactly on the drums' return (1:11.111). The "#1 IN THE
WORLD" caption, in the same style as the other milestone captions, shows from the clip's first frame. He rips
his headphones off, collapses on the desk and screams; his second scream starts as the song reaches its stop
bar (1:20.0), where the song fades out and the clip finishes on its own sound.

usage: python -I build_ending.py <workdir>
"""
import os
import subprocess
import sys

S = os.environ.get("FT_WORK", "/tmp/claude-0/-home-user-Claude-code/a61365b4-59b2-5d5f-8537-7f9c9b765619/scratchpad")
LIB = "/home/user/Claude-code/osu-edit/clips/ft_library/03_number_one_2019-02-11"
MAINW = "/home/user/Claude-code/osu-edit/out/ft_main/work"
SONG = f"{S}/tracks_x/2143023/audio.mp3"
FONT = f"{S}/fonts/LilitaOne.ttf"
CLIP = f"{LIB}/2019-02-11_top1_moment_60s.mp4"
RESULT_AT = 31.167           # result screen appears in the clip (scene change)
CLIP_OUT = 43.45             # a couple of seconds after his second scream, head on the desk
WORK = sys.argv[1]
os.makedirs(WORK, exist_ok=True)
BEAT = 60 / 189
FPS = 60


def F(b):
    return round(b * BEAT * FPS)


B_START = 177
t_start = F(B_START) / FPS
t_clip = F(192) / FPS        # the calm: the #1 clip starts here
t_drums = 224 * BEAT         # 1:11.111, drums return
CLIP_IN = RESULT_AT - (t_drums - t_clip)
CAP_HOLD, CAP_FADE = 6 * BEAT, 0.25
END_FADE = 0.5

# --- the #1 moment as one piece, caption from the first frame (same look as the other milestone captions)
n_clip = round((CLIP_OUT - CLIP_IN) * FPS)
clip_dur = n_clip / FPS
alpha = f"min(1,t*14)*(1-min(1,max(0,(t-{CAP_HOLD:.3f})/{CAP_FADE})))"
cap = (f"drawtext=fontfile={FONT}:text='#1 IN THE WORLD':fontsize=150:fontcolor=white:borderw=12:bordercolor=0x15121a"
       f":shadowcolor=0x15121a:shadowx=0:shadowy=10:x=(w-tw)/2:y=h*0.20:alpha='{alpha}',"
       f"drawtext=fontfile={FONT}:text='11.02.2019':fontsize=60:fontcolor=0xffd84a:borderw=8:bordercolor=0x15121a"
       f":x=(w-tw)/2:y=h*0.20+175:alpha='{alpha}'")
vf = f"fps=60,scale=1920:1080:flags=lanczos,setsar=1,{cap},fade=t=out:st={clip_dur - END_FADE:.3f}:d={END_FADE}"
clip_out = f"{WORK}/clip_1.mp4"
subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{CLIP_IN:.3f}", "-i", CLIP, "-frames:v", str(n_clip), "-vf", vf, "-an",
                "-c:v", "libx264", "-preset", "fast", "-crf", "14", "-pix_fmt", "yuv420p", "-r", "60", clip_out], check=True)

# --- picture: the last pounding cuts as rendered for the main part, then the clip
segs = [f"{MAINW}/seg_{k:03d}.mp4" for k in range(68, 78)] + [clip_out]
with open(f"{WORK}/concat.txt", "w") as f:
    for s in segs:
        f.write(f"file '{s}'\n")
video = f"{WORK}/video.mp4"
subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", f"{WORK}/concat.txt", "-c", "copy", video], check=True)

# --- sound: song (lower under the clip, back up with the drums, gone at its stop bar) + the clip's own audio
total = (t_clip - t_start) + clip_dur
calm0 = t_clip - t_start
drums0 = t_drums - t_start
fade_st, fade_d = 252 * BEAT - t_start, 0.3  # stop bar 1:20.0, gone before its fill into chorus 2
fc = (f"[1:a]atrim={t_start:.4f}:{t_start + total:.4f},asetpts=PTS-STARTPTS,aresample=48000,"
      f"volume='if(lt(t,{calm0:.3f}),1,if(lt(t,{drums0:.3f}),0.72,0.8))':eval=frame,afade=t=out:st={fade_st:.3f}:d={fade_d}[song];"
      f"[2:a]atrim={CLIP_IN:.3f}:{CLIP_OUT:.3f},asetpts=PTS-STARTPTS,aresample=48000,afade=t=out:st={clip_dur - END_FADE:.3f}:d={END_FADE},"
      f"adelay=delays={int(round(calm0 * 1000))}:all=1[clip];"
      f"[song][clip]amix=inputs=2:normalize=0:duration=longest,alimiter=limit=0.9:level=false[a]")
final = f"{WORK}/ending.mp4"
subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", video, "-i", SONG, "-i", CLIP, "-filter_complex", fc,
                "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest", "-movflags", "+faststart", final],
               check=True)
print("ending", round(total, 3), "s from track", round(t_start, 3), "->", final)
