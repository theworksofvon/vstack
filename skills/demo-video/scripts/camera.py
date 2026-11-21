"""The camera: notes of where to look, and the moving crop that films them.

A recording never scales the page. It writes camera notes (`t`, `cx`, `cy`
in page pixels, `z` zoom, `d` seconds), and the build crops the frames.
"""

OUTPUT = (1920, 1080)  # the size of the finished video


def aim(
    cx: float, cy: float, zoom: float, size: tuple[int, int], scale: float
) -> tuple[float, float, float]:
    """The nearest note that stays sharp and keeps the view on the page.

    `scale` is frame pixels per page pixel: a zoom past the frame's own
    pixels would blur.
    """
    width, height = size
    zoom = min(zoom, width * scale / OUTPUT[0])
    half_w, half_h = width / zoom / 2, height / zoom / 2
    return (
        min(max(cx, half_w), width - half_w),
        min(max(cy, half_h), height - half_h),
        zoom,
    )


# The camera is a spring: it starts slowly, arrives with a soft tail, and when a
# new target comes mid-move it bends towards it with no jerk. A spring is linear,
# so its path through many targets is the sum of 1 step response per change.
SETTLE = 5.0  # stiffness x seconds: the spring is 96% of the way after a note's `d`
BOUNCE = 0.8  # damping of a zoom-in: below 1 it passes the target by 1.5%, then returns


def spring(at: float, length: float, change: float, damping: float) -> str:
    """An ffmpeg term: the move of a spring that starts at `at` towards `change`."""
    w = SETTLE / max(length, 0.05)
    t = f"st(0,max(it-{at:.3f},0))"
    if damping >= 1:
        return f"{change:.4f}*({t}*0+1-(1+{w:.4f}*ld(0))*exp(-{w:.4f}*ld(0)))"
    wd = w * (1 - damping**2) ** 0.5
    ratio = damping / (1 - damping**2) ** 0.5
    return (
        f"{change:.4f}*({t}*0+1-exp(-{damping * w:.4f}*ld(0))"
        f"*(cos({wd:.4f}*ld(0))+{ratio:.4f}*sin({wd:.4f}*ld(0))))"
    )


def eased(
    start: float, moves: list[tuple[float, float, float]], bounce: bool = False
) -> str:
    """An ffmpeg expression: `start`, plus 1 spring per (time, seconds, change)."""
    terms = [f"{start:.3f}"]
    for at, length, change in moves:
        if abs(change) < 1e-6:
            continue
        damping = BOUNCE if bounce and change > 0 else 1.0
        terms.append(spring(at, length, change, damping))
    return "+".join(terms)


def crop(manifest: dict, fps: int) -> str:
    """The ffmpeg filter that moves the crop along the camera notes of a take."""
    keys = manifest.get("camera") or []
    if not keys:
        return f"scale={OUTPUT[0]}:{OUTPUT[1]}:flags=lanczos"
    width, height = manifest["size"]
    scale = manifest.get("scale", 2)  # device pixels per page pixel
    at = {"cx": width / 2, "cy": height / 2, "z": 1.0}
    moves: dict[str, list[tuple[float, float, float]]] = {"cx": [], "cy": [], "z": []}
    for key in keys:
        for name in moves:
            moves[name].append((key["t"], key["d"], key[name] - at[name]))
            at[name] = key[name]
    zoom = f"max(1,{eased(1.0, moves['z'], bounce=True)})"
    cx = eased(width / 2 * scale, [(t, d, c * scale) for t, d, c in moves["cx"]])
    cy = eased(height / 2 * scale, [(t, d, c * scale) for t, d, c in moves["cy"]])
    return (
        f"zoompan=z='{zoom}':x='clip(({cx})-iw/zoom/2,0,iw-iw/zoom)'"
        f":y='clip(({cy})-ih/zoom/2,0,ih-ih/zoom)':d=1:s={OUTPUT[0]}x{OUTPUT[1]}:fps={fps}"
    )
