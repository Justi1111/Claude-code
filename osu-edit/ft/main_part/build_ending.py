"""Ending of the FlyingTuna edit (v4), rendered alone: track 0:56.18 to the end of the #1 clip.

The pounding cuts are reused from the main part render as they are (with their #4 / #2 captions).
From the calm (1:00.952) the clip "When Tuna really gets #1" plays in full, uncut, with its own sound:
"oh shit" -> YES -> YES -> "oh my f*cking god" -> result screen. The "#1" caption, in the same style as
the other milestone captions, shows from its first frame. The song keeps playing under the clip and
fades out right before its drums return (1:11.11), so the clip finishes on its own sound.

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
CLIP = f"{LIB}/2019-02-12_when_tuna_really_gets_1.mp4"
WORK = sys.argv[1]
os.makedirs(WORK, exist_ok=True)
BEAT = 60 / 189
FPS = 60


def F(b):
    return round(b * BEAT * FPS)


B_START = 177
t_start = F(B_START) / FPS
t_clip = F(192) / FPS        # the calm: the #1 clip starts here
CAP_HOLD, CAP_FADE = 6 * BEAT, 0.25
END_FADE = 0.4

# --- the #1 clip, full length, caption from the first frame (same look as the other milestone captions)
n_clip = int(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames", "-show_entries",
                             "stream=nb_read_frames", "-of", "csv=p=0", CLIP], capture_output=True, text=True).stdout.strip())
clip_dur = n_clip / FPS
alpha = f"min(1,t*14)*(1-min(1,max(0,(t-{CAP_HOLD:.3f})/{CAP_FADE})))"
cap = (f"drawtext=fontfile={FONT}:text='#1 IN THE WORLD':fontsize=150:fontcolor=white:borderw=12:bordercolor=0x15121a"
       f":shadowcolor=0x15121a:shadowx=0:shadowy=10:x=(w-tw)/2:y=h*0.20:alpha='{alpha}',"
       f"drawtext=fontfile={FONT}:text='11.02.2019':fontsize=60:fontcolor=0xffd84a:borderw=8:bordercolor=0x15121a"
       f":x=(w-tw)/2:y=h*0.20+175:alpha='{alpha}'")
vf = f"fps=60,scale=1920:1080:flags=lanczos,setsar=1,{cap},fade=t=out:st={clip_dur - END_FADE:.3f}:d={END_FADE}"
clip_out = f"{WORK}/clip_1.mp4"
subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", CLIP, "-frames:v", str(n_clip), "-vf", vf, "-an",
                "-c:v", "libx264", "-preset", "fast", "-crf", "14", "-pix_fmt", "yuv420p", "-r", "60", clip_out], check=True)

# --- picture: the last pounding cuts as rendered for the main part, then the clip
segs = [f"{MAINW}/seg_{k:03d}.mp4" for k in range(68, 78)] + [clip_out]
with open(f"{WORK}/concat.txt", "w") as f:
    for s in segs:
        f.write(f"file '{s}'\n")
video = f"{WORK}/video.mp4"
subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", f"{WORK}/concat.txt", "-c", "copy", video], check=True)

# --- sound: song (a bit lower under the clip, faded out before the drums return) + the clip's own audio
total = (t_clip - t_start) + clip_dur
calm0 = t_clip - t_start
fade_st, fade_d = 70.05 - t_start, 1.0
fc = (f"[1:a]atrim={t_start:.4f}:{t_start + total:.4f},asetpts=PTS-STARTPTS,aresample=48000,"
      f"volume='if(gte(t,{calm0:.3f}),0.72,1)':eval=frame,afade=t=out:st={fade_st:.3f}:d={fade_d}[song];"
      f"[2:a]aresample=48000,afade=t=out:st={clip_dur - END_FADE:.3f}:d={END_FADE},"
      f"adelay=delays={int(round(calm0 * 1000))}:all=1[clip];"
      f"[song][clip]amix=inputs=2:normalize=0:duration=longest,alimiter=limit=0.9:level=false[a]")
final = f"{WORK}/ending.mp4"
subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", video, "-i", SONG, "-i", CLIP, "-filter_complex", fc,
                "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest", "-movflags", "+faststart", final],
               check=True)
print("ending", round(total, 3), "s from track", round(t_start, 3), "->", final)
