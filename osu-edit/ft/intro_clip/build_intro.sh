#!/bin/bash
# Intro of the FlyingTuna edit: the end of the "achievement list jumpscare" clip (08.12.2024)
# over 0:15.23-0:20.32 of LOVESICK, CANNIBAL!, music ducked and muffled, his scream filling the
# 0.11 s silence right before the drop.
#
# usage: SONG=<track audio, official 1:57 version> ./build_intro.sh   (run from osu-edit/ft/intro_clip)
#
# Timing: track = clip + 0.032 s. The scream starts at clip 20.168 = track 20.200 (start of the silence
# before the drop), the drop is track 20.3167 (frame 1219 at 60 fps). The intro is track frames 914..1218 (305 frames).
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
CLIP=${CLIP:-$HERE/../../clips/ft_library/09_owc2024/2024-12-08_achieve_list_reading.mp4}
OUT=${OUT:-$HERE/../../out/ft_intro_clip}
: "${SONG:?set SONG to the track audio}"
mkdir -p "$OUT"
ffmpeg -v error -y -ss 15.20133 -i "$CLIP" -frames:v 305 -an -vf "fps=60,scale=1920:1080:flags=lanczos,setsar=1" \
  -c:v libx264 -preset medium -crf 14 -pix_fmt yuv420p "$OUT/intro_v.mp4"
ffmpeg -v error -y -i "$SONG" -i "$CLIP" -filter_complex "\
[0:a]atrim=15.233333:20.316667,asetpts=PTS-STARTPTS,aresample=48000,volume=-9dB,lowpass=f=1100:p=2,afade=t=in:d=0.15[mus];\
[1:a]atrim=15.201333:20.284667,asetpts=PTS-STARTPTS,aresample=48000,afade=t=in:st=0.09:d=0.03,\
acompressor=threshold=0.1:ratio=4:attack=5:release=150:makeup=2,volume=4dB[vo];\
[mus][vo]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.95:level=false[a]" -map "[a]" -c:a pcm_s16le "$OUT/intro_a.wav"
ffmpeg -v error -y -i "$OUT/intro_v.mp4" -i "$OUT/intro_a.wav" -map 0:v -map 1:a -c:v copy -c:a aac -b:a 256k -shortest \
  -movflags +faststart "$OUT/tuna_intro_achieve_master.mp4"
# The scream continues past the cut: when gluing the main part after the intro, mix
# clip 20.2847-20.75 (same voice chain, fade out 0.2 s) at the start of the main part.
echo "done: $OUT/tuna_intro_achieve_master.mp4"
