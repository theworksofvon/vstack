# Reference videos

Numbers from `demo.py study <url>`, measured 2026-11-10. The cut count is a
low estimate: the detector misses slow fades and moving text. Add a row by
running `study` on a new link and reading its sheet.

| video                                                                                 | models the mode     | length | on screen                                                                                                   | hard cuts                               | pauses in the sound | loudness   |
| ------------------------------------------------------------------------------------- | ------------------- | ------ | ----------------------------------------------------------------------------------------------------------- | --------------------------------------- | ------------------- | ---------- |
| [Retool Apps: Build polished apps, fast](https://www.youtube.com/watch?v=kxpWVpEPw3E) | `product`           | 1:33   | real UI clips, many short ones, 1 logo open, 1 end card                                                     | 11                                      | 1                   | -18.0 LUFS |
| [Intro to Linear](https://www.youtube.com/watch?v=9Q5BoiIFBiY)                        | `demo`              | 4:01   | 1 screen recording at real speed from 0:44 to 3:43, no cut; a presenter on camera only at the start and end | 16, all in the first 44 s and last 18 s | 34, 27 s in total   | -18.6 LUFS |
| [Introducing Aside](https://www.youtube.com/watch?v=Q-f0dQ764so)                      | `launch`, not built | 1:28   | large moving text, the UI only as short proof                                                               | 5                                       | 2                   | -14.1 LUFS |

What the modes take from them:

- `demo` follows Linear: the screen runs at real speed, the narrator
  pauses, and the camera stays wide most of the time.
- `product` follows Retool: no pause in the sound, a new clip every few
  seconds, about 90 seconds in total.
- Loudness of narrated demos sits near -18 LUFS.

Not yet measured, so still guesses in the tool: the 1.2x to 1.4x focus
zoom, the 0.6 s cursor glide, and the 3.4 s caption.
