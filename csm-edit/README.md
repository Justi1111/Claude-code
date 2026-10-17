# Chainsaw Man collage edit

A fan edit of Chainsaw Man in the style of a white-background collage TikTok edit (cut-out anime characters floating
on #FBFBFB, crayon strokes pinned with screws, chains, flat graphic shapes, one lyric word at a time). It follows the
reference shot for shot (43 shots, same timings, scales and cadence) on the reference's own sound, 0–34.4 s,
1920x1080, 24 fps.

## Story swaps

| Reference | Here |
|---|---|
| seated duo, "still fight and i don't know why" | Denji and Power on a bench (ED12), Denji pixel-dissolves on "why" |
| stone hand on wires, three crayon strings to screws | stone hand with painted nails holding a bloody chunk, same strings and screws |
| puppet on three strings, strings snap | Denji from behind, arms out, as a puppet; strings snap, he drops onto all fours on a chain leash running off frame (to Makima) |
| metal beam | chainsaw guide bar with its orange housing, kid Denji hanging under it |
| metal mask with HUD | Chainsaw Man's head, metal-textured, framed by stone hands; Makima's ringed-eye circles and a chrome ring |
| disc → ball → throw | the head in a disc → bowling ball → Aki bowling (Kick Back OP) |
| flying duo, machine passes | Denji and Power in navy over diagonal rain, chainsaw heads passing |
| machine with tank, "HEY!" | Pochita heating up, "HEY!", bursts; the starter cord rises |
| tube swung in the climax | the cord becomes a red cone; the red slash leaves Chainsaw Man's blade in every re-framing |
| bandaged head, music drop | Denji's head wrapped in red brush bandages |
| mint/cyan echoes, glitch, paint splash | Denji's eyepatch scream with mint/cyan echoes, glitch, a hand flicks blood, blood fills the frame |
| close-ups, eye punch | Power / Denji / Power close-ups, Makima's ringed eyes |
| button pressed | Pochita's starter cord yanked, his eyes light up |
| blue flower with cables | Reze's red gerbera with cables |
| robot arm, drop | Chainsaw Man's chainsaw arm, blood runs down the blade and drips |
| bars, totem | the same bars; a recap totem hanging on a chain |

## Code

- `engine/core.py` — skia drawing core: canvas, easing, brush/ribbon strokes, chains, rings, splatter, text, glitch.
- `engine/fx.py` — cut-out treatments: XDoG sketch lines, collage fill, tint, echoes.
- `engine/cutout.py` — anime cut-outs: isnetis (skytnt/anime-seg) or GrabCut mattes, island removal, hole filling,
  cached as RGBA PNGs.
- `engine/timeline.py` — scenes and post effects on a timeline, multi-process render, stills and contact sheets.
- `assets.py` — palette, the cut-out table (source video, time, crop, matte fixes), treatments, backgrounds, props.
- `edit.py` — the 43 scenes.
- `build.py` — `python3 -I build.py render out.mp4` (also `sheet`, `stills`, `part`).

Footage: official promotional videos only (PVs, trailers, character PVs, creditless OP/EDs, Reze-arc trailer), from
Bilibili re-uploads. Footage, cut-outs, fonts (Open Sans, Permanent Marker, JetBrains Mono — OFL), CC0 textures (Poly
Haven) and renders live in the scratchpad, outside git.
