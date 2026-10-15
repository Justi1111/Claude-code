"""Ending of the FlyingTuna edit: the real #1 moment as one uncut piece, then his "NUMBER ONE!" over black.

From the calm (1:00.952) the clip "топ 1" (Super Driver [Fiery's Extreme] HDDT, 778pp, 11.02.2019 22:57 KST) runs
uncut from its last spinner: the result screen, he stares at the ranking panel, pulls the headphones off, drops onto
the desk screaming and lies there. The in-point keeps the result screen on 1:11.11 as before. While he lies on the
desk the picture and its sound fade to black (clip 52.7-53.7, about 1:17.4-1:18.4 of the edit); after half a second
of silence his "NUMBER ONE!" from the clip with the Super Driver result screen (shot a minute later) plays over the
black, and the edit ends a beat after it.

Sound: the song plays on for 4.5 s of the calm and fades over the next two bars, gone by 1:07.30 when the map ends
in the clip (the playfield fades at clip 27.0-27.25); after that only the clip's own sound.

The "세계 1위 / #1 IN THE WORLD / 11.02.2019" plate (../captions/captions.py) fades in when the ranking panel comes up
and he stares at it (clip 32.70), stays through his first scream and leaves before the second (from 38.60).

Writes clip_1.mp4 (the clip with the plate, used by build_full.py) and ending.mp4, a preview from 0:55.87 (the #4
shot) with the last pounding cuts taken from the main part render.

usage: FT_MAIN_WORK=<build_main.py workdir> python -I build_ending.py <workdir>
"""
import csv
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "captions"))
import captions  # noqa: E402

S = os.environ.get("FT_WORK", "/tmp/claude-0/-home-user-Claude-code/a61365b4-59b2-5d5f-8537-7f9c9b765619/scratchpad")
LIB = "/home/user/Claude-code/osu-edit/clips/ft_library/03_number_one_2019-02-11"
MAINW = os.environ.get("FT_MAIN_WORK", "/home/user/Claude-code/osu-edit/out/ft_main_v6/work")
SONG = f"{S}/tracks_x/2143023/audio.mp3"
CLIP = f"{LIB}/2019-02-11_top1_moment_60s.mp4"
PAR = f"{LIB}/2019-02-11_i_will_go_to_say_to_my_parents.mp4"
SHOUT_IN, SHOUT_OUT = 16.02, 17.35   # "NUMBER ONE!" (whisper: 15.80-17.12, the loud part 16.12-17.05)
SHOUT_GAP, TAIL = 0.35, 0.9          # silence before it, black after it
CLIP_FADE_AT = 52.70                 # he lies on the desk; the picture starts to go
RESULT_AT = 31.167           # result screen appears in the clip (scene change)
PANEL_AT = 32.70             # the online ranking panel is up and he stares at it
PLATE_OUT = 38.60            # the plate starts to leave: first scream over, the second starts at 40.0
BEAT = 60 / 189
FPS = 60
END_FADE = 1.0


def F(b):
    return round(b * BEAT * FPS)


B_START = 176                              # the #4 shot
t_start = F(B_START) / FPS
t_clip = F(192) / FPS                      # the calm: the #1 clip starts here
CLIP_IN = RESULT_AT - (224 * BEAT - t_clip)
MUSIC_HOLD, MUSIC_GONE = 206 * BEAT, 212 * BEAT
n_clip = round((CLIP_FADE_AT + END_FADE - CLIP_IN) * FPS)   # up to black
clip_dur = n_clip / FPS
n_total = n_clip + round((SHOUT_GAP + SHOUT_OUT - SHOUT_IN + TAIL) * FPS)
total_dur = n_total / FPS


def main_segments(b0, b1=192):
    """segments of the main part render from beat b0 (a cut) up to the calm."""
    rows = list(csv.DictReader(open(f"{MAINW}/cutlist.tsv", encoding="utf-8"), delimiter="\t"))
    t0, t1 = b0 * BEAT, b1 * BEAT
    segs = [r for r in rows if t0 - 2e-3 <= float(r["track_start"]) < t1 - 2e-3]
    assert segs and abs(float(segs[0]["track_start"]) - t0) < 2e-3, f"no cut at beat {b0}"
    assert abs(float(segs[-1]["track_end"]) - t1) < 2e-3
    return [f"{MAINW}/seg_{int(r['n']) - 1:03d}.mp4" for r in segs]


def build_clip(work):
    out = f"{work}/clip_1.mp4"
    off = round((PANEL_AT - CLIP_IN) * FPS)
    n_plate = round((PLATE_OUT + captions.P_OUT - PANEL_AT) * FPS) + 2
    vf = "fps=60,scale=1920:1080:flags=lanczos,setsar=1"
    post = f"fade=t=out:st={clip_dur - END_FADE:.3f}:d={END_FADE}"   # stays black after it, under the shout
    captions.render(["-ss", f"{CLIP_IN:.3f}", "-i", CLIP], vf, captions.plate_frames(n_plate, PLATE_OUT - PANEL_AT),
                    n_total, out, offset=off, post=post)
    return out


def song_chain(t0, label):
    """the song from track time t0: lower in the calm, faded out by the end of the map in the clip."""
    return (f"atrim={t0:.6f}:{MUSIC_GONE + 0.05:.6f},asetpts=PTS-STARTPTS,aresample=48000,"
            f"volume='if(lt(t,{t_clip - t0:.4f}),1,0.72)':eval=frame,"
            f"afade=t=out:st={MUSIC_HOLD - t0:.4f}:d={MUSIC_GONE - MUSIC_HOLD:.4f}:curve=qua[{label}]")


def clip_audio_chain(delay_s, label):
    return (f"atrim={CLIP_IN:.4f}:{CLIP_IN + clip_dur:.4f},asetpts=PTS-STARTPTS,aresample=48000,"
            f"afade=t=out:st={clip_dur - END_FADE:.4f}:d={END_FADE},adelay=delays={int(round(delay_s * 1000))}:all=1[{label}]")


def shout_chain(delay_s, label):
    """his "NUMBER ONE!" over the black; delay_s is where the #1 clip starts in the output."""
    d = SHOUT_OUT - SHOUT_IN
    at = delay_s + clip_dur + SHOUT_GAP
    return (f"atrim={SHOUT_IN:.3f}:{SHOUT_OUT:.3f},asetpts=PTS-STARTPTS,aresample=48000,volume=-2dB,"
            f"afade=t=in:d=0.02,afade=t=out:st={d - 0.2:.3f}:d=0.2,adelay=delays={int(round(at * 1000))}:all=1[{label}]")


if __name__ == "__main__":
    WORK = sys.argv[1]
    os.makedirs(WORK, exist_ok=True)
    clip_out = build_clip(WORK)
    segs = main_segments(B_START) + [clip_out]
    with open(f"{WORK}/concat.txt", "w") as f:
        for s in segs:
            f.write(f"file '{s}'\n")
    video = f"{WORK}/video.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", f"{WORK}/concat.txt",
                    "-c", "copy", video], check=True)
    fc = (f"[1:a]{song_chain(t_start, 'song')};[2:a]{clip_audio_chain(t_clip - t_start, 'clip')};"
          f"[3:a]{shout_chain(t_clip - t_start, 'shout')};"
          f"[song][clip][shout]amix=inputs=3:normalize=0:duration=longest,alimiter=limit=0.9:level=false,apad[a]")
    final = f"{WORK}/ending.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", video, "-i", SONG, "-i", CLIP, "-i", PAR, "-filter_complex", fc,
                    "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest",
                    "-movflags", "+faststart", final], check=True)
    print("ending", round(t_clip - t_start + total_dur, 3), "s from track", round(t_start, 3), "clip frames", n_total, "->", final)
