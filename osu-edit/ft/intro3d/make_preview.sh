#!/bin/bash
# Preview: 3D intro (0-20.05) -> real jumpscare from the achieve-list clip (0.27 s) -> drop with a 2018 gameplay clip.
# Audio: the song from 0:00 plus his achieve-list voice, aligned so his words land on the on-screen dates.
set -e
# usage: SONG=<lovesick_cannibal.mp3> ./make_preview.sh   (run from osu-edit/ft/intro3d)
HERE=$(cd "$(dirname "$0")" && pwd)
L=${L:-$HERE/../../clips/ft_library}
OUT=${OUT:-$HERE/../../out/ft_intro}
ANIM=${ANIM:-$OUT/tuna_intro_3d_text.mp4}
ACH=$L/09_owc2024/2024-12-08_achieve_list_reading.mp4
DROP=$L/01_2018_mouse_to_tablet/2018-02-11_volcanic_jumps.mp4
: "${SONG:?set SONG to the track audio (official 1:57 version)}"
ffmpeg -v error -y -i "$ANIM" -i "$ACH" -i "$DROP" -i "$SONG" -filter_complex "
[0:v]trim=0:20.05,setpts=PTS-STARTPTS,fps=60,format=yuv420p[a];
[1:v]trim=20.62:20.89,setpts=PTS-STARTPTS,scale=1920:1080,fps=60,format=yuv420p,setsar=1[j];
[2:v]trim=25.8:28.4,setpts=PTS-STARTPTS,scale=1920:1080,fps=60,format=yuv420p,setsar=1[d];
[a][j][d]concat=n=3:v=1:a=0[v];
[3:a]atrim=0:22.92,asetpts=PTS-STARTPTS,volume=0.8[song];
[1:a]atrim=0.57:20.89,asetpts=PTS-STARTPTS,volume=1.7[voice];
[song][voice]amix=inputs=2:normalize=0:duration=first[aout]" \
 -map "[v]" -map "[aout]" -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -c:a aac -b:a 192k -movflags +faststart "$OUT/tuna_intro_preview.mp4"
ls -la "$OUT"
