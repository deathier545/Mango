"""Red dot-sphere HUD in a separate pygame process (Mango orb)."""

from __future__ import annotations

import logging
import math
import multiprocessing as mp
import os
import queue
import sys
import time
from multiprocessing import Queue
from typing import Any

logger = logging.getLogger(__name__)


def _env_first(*names: str, default: str = "") -> str:
    for name in names:
        raw = os.getenv(name, "").strip()
        if raw:
            return raw
    return default


def _env_on(*names: str) -> bool:
    return _env_first(*names).lower() in ("1", "true", "yes", "on")


def _maybe_position_hud_window(pg: Any, win_w: int, win_h: int) -> None:
    """Pin HUD to bottom-right on Windows when ``MANGO_HUD_POSITION=bottom-right``."""
    raw = os.getenv("MANGO_HUD_POSITION", "").strip().lower().replace("-", "").replace("_", "")
    if raw != "bottomright":
        return
    if sys.platform != "win32":
        return
    try:
        import ctypes

        info = pg.display.get_wm_info()
        hwnd = info.get("window")
        if not hwnd:
            return
        user32 = ctypes.windll.user32
        sw = int(user32.GetSystemMetrics(0))
        sh = int(user32.GetSystemMetrics(1))
        margin = 14
        taskbar = 52
        x = max(0, sw - win_w - margin)
        y = max(0, sh - win_h - margin - taskbar)
        SWP_SHOWWINDOW = 0x0040
        user32.SetWindowPos(hwnd, 0, int(x), int(y), int(win_w), int(win_h), SWP_SHOWWINDOW)
        logger.info("Mango HUD window placed bottom-right at (%d,%d)", x, y)
    except Exception:
        logger.debug("HUD bottom-right placement skipped", exc_info=True)


_HUD_SHELL_SCALE = 0.76
_HUD_LOUDNESS_SCALE_BUMP = 0.08
_HUD_LOUDNESS_DOT_BUMP = 0.7


def _enabled_from_env() -> bool:
    return _env_on("MANGO_HUD", "MANGO_JARVIS_HUD")


def _fibonacci_unit_sphere(n: int) -> list[tuple[float, float, float]]:
    if n <= 0:
        return []
    if n == 1:
        return [(0.0, 1.0, 0.0)]
    pts: list[tuple[float, float, float]] = []
    phi_g = math.pi * (3.0 - math.sqrt(5.0))
    for i in range(n):
        y = 1.0 - (2.0 * i + 1.0) / n
        r = math.sqrt(max(0.0, 1.0 - y * y))
        th = phi_g * i
        pts.append((math.cos(th) * r, y, math.sin(th) * r))
    return pts


def _rotate_y(x: float, y: float, z: float, ang: float) -> tuple[float, float, float]:
    c, s = math.cos(ang), math.sin(ang)
    return c * x + s * z, y, -s * x + c * z


def _rotate_x(x: float, y: float, z: float, ang: float) -> tuple[float, float, float]:
    c, s = math.cos(ang), math.sin(ang)
    return x, c * y - s * z, s * y + c * z


def _dot_count_for_window(w: int, h: int) -> int:
    raw = _env_first("MANGO_HUD_BALL_DOTS", "MANGO_JARVIS_HUD_BALL_DOTS")
    if raw:
        try:
            n = int(raw)
            return max(80, min(n, 4000))
        except ValueError:
            pass
    area = max(w * h, 1)
    return max(220, min(1600, int(area / 900)))


def _ball_radius_fraction() -> float:
    raw = _env_first("MANGO_HUD_BALL_RADIUS", "MANGO_JARVIS_HUD_BALL_RADIUS")
    if raw:
        try:
            return max(0.18, min(float(raw), 0.48))
        except ValueError:
            pass
    return 0.30


def mango_hud_main(cmd_queue: Queue, level_slot: Any) -> None:
    """Child entry point — keep imports minimal for Windows spawn."""
    import pygame as pg

    pg.init()

    win_w = int(_env_first("MANGO_HUD_SIZE", "MANGO_JARVIS_HUD_SIZE", default="880") or "880")
    win_w = max(360, min(win_w, 2400))
    win_h = win_w

    render_scale = int(
        _env_first("MANGO_HUD_RENDER_SCALE", "MANGO_JARVIS_HUD_RENDER_SCALE", default="2") or "2"
    )
    render_scale = max(1, min(render_scale, 3))

    fullscreen = _env_on("MANGO_HUD_FULLSCREEN", "MANGO_JARVIS_HUD_FULLSCREEN")
    flags = pg.FULLSCREEN if fullscreen else pg.RESIZABLE
    screen = pg.display.set_mode((win_w, win_h), flags)
    pg.display.set_caption("Mango")
    _maybe_position_hud_window(pg, win_w, win_h)
    clock = pg.time.Clock()

    def rebuild_buffers() -> None:
        nonlocal bw, bh, buf, overlay, cx, cy, base_r, unit_pts, dot_phases
        bw, bh = win_w * render_scale, win_h * render_scale
        buf = pg.Surface((bw, bh))
        overlay = pg.Surface((bw, bh), pg.SRCALPHA)
        cx, cy = bw // 2, bh // 2
        base_r = int(min(bw, bh) * _ball_radius_fraction())
        n = _dot_count_for_window(win_w, win_h)
        unit_pts = _fibonacci_unit_sphere(n)
        dot_phases = [(i * 2.399, i * 1.713) for i in range(len(unit_pts))]

    bw = bh = 0
    buf: Any = None
    overlay: Any = None
    cx = cy = base_r = 0
    unit_pts: list[tuple[float, float, float]] = []
    dot_phases: list[tuple[float, float]] = []
    rebuild_buffers()

    fps_cap = int(_env_first("MANGO_HUD_FPS", "MANGO_JARVIS_HUD_FPS", default="55") or "55")
    fps_cap = max(30, min(fps_cap, 90))

    state = "listening"
    tick = 0
    energy = 0.0
    pending_resize: tuple[int, int] | None = None
    last_resize_t = 0.0

    bg = (6, 2, 4)

    running = True
    while running:
        try:
            while True:
                msg = cmd_queue.get_nowait()
                if msg == "quit":
                    running = False
                    break
                if isinstance(msg, str) and msg in ("listening", "thinking", "speaking"):
                    state = msg
        except queue.Empty:
            pass

        if not running:
            break

        now = time.perf_counter()
        for event in pg.event.get():
            if event.type == pg.QUIT:
                running = False
            elif event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE and fullscreen:
                running = False
            elif event.type == pg.VIDEORESIZE and not fullscreen:
                nw, nh = int(event.w), int(event.h)
                nw = max(320, min(nw, 2800))
                nh = max(240, min(nh, 2000))
                pending_resize = (nw, nh)
                last_resize_t = now

        if pending_resize is not None and (now - last_resize_t) > 0.05:
            win_w, win_h = pending_resize
            pending_resize = None
            screen = pg.display.set_mode((win_w, win_h), pg.RESIZABLE)
            rebuild_buffers()

        try:
            raw_in = float(level_slot.value)
        except Exception:
            raw_in = 0.0
        raw_in = max(0.0, min(1.0, raw_in))
        audible = raw_in > 0.035
        raw = raw_in if state == "speaking" or audible else 0.0

        if state == "speaking" or audible:
            energy = energy * 0.44 + raw * 0.56
        else:
            energy = energy * 0.82 + raw * 0.18

        idle_breathe = 0.008 * math.sin(tick * 0.016)
        ball_scale = _HUD_SHELL_SCALE + idle_breathe
        j_amp = 0.0
        rot_boost = 0.0
        motion_speaking = state == "speaking" or audible
        if motion_speaking:
            ball_scale = (
                _HUD_SHELL_SCALE
                + 0.008 * math.sin(tick * 0.045)
                + _HUD_LOUDNESS_SCALE_BUMP * energy
            )
            j_amp = energy * base_r * 0.034
            rot_boost = energy * 0.06
        elif state == "thinking":
            ball_scale = _HUD_SHELL_SCALE + 0.018 * math.sin(tick * 0.03)

        buf.fill(bg)
        overlay.fill((0, 0, 0, 0))

        rot_y = tick * 0.0032 + rot_boost * math.sin(tick * 0.019)
        rot_x = 0.22 * math.sin(tick * 0.0055) + rot_boost * 0.45 * math.sin(tick * 0.024)

        rs = max(1, render_scale)

        projected: list[tuple[float, int, int, int, int, int, int]] = []
        for i, (px, py, pz) in enumerate(unit_pts):
            x, y, z = _rotate_y(px, py, pz, rot_y)
            x, y, z = _rotate_x(x, y, z, rot_x)
            ph0, ph1 = dot_phases[i]
            if j_amp > 0.5:
                x += (j_amp / base_r) * 0.85 * math.sin(tick * 0.11 + ph0)
                y += (j_amp / base_r) * 0.85 * math.cos(tick * 0.09 + ph1)
            sx = int(cx + base_r * ball_scale * x)
            sy = int(cy + base_r * ball_scale * y * 0.96)
            depth = z
            shade = 0.35 + 0.65 * max(0.0, min(1.0, (depth + 1.0) * 0.5))
            pulse = 0.65 + 0.35 * math.sin(tick * 0.04 + ph0 * 0.3)
            rcol = int(210 + 45 * shade * pulse)
            gcol = int(22 + 40 * shade * energy * (1.0 if motion_speaking else 0.0))
            bcol = int(18 + 32 * shade * energy * (1.0 if motion_speaking else 0.0))
            if motion_speaking:
                rdot = max(
                    rs,
                    int(
                        rs
                        * (
                            1.05
                            + _HUD_LOUDNESS_DOT_BUMP
                            * energy
                            * (0.45 + 0.55 * shade)
                        )
                    ),
                )
            else:
                rdot = max(rs, int(rs * 1.12))
            projected.append((depth, sx, sy, rdot, rcol, gcol, bcol))

        projected.sort(key=lambda t: t[0])

        for _d, sx, sy, rdot, rcol, gcol, bcol in projected:
            pg.draw.circle(buf, (rcol, gcol, bcol), (sx, sy), rdot)
            if motion_speaking and rdot >= rs * 2 and energy > 0.08:
                pg.draw.circle(
                    overlay,
                    (min(255, rcol + 35), max(0, gcol // 3), max(0, bcol // 3), 35),
                    (sx, sy),
                    rdot + rs,
                )

        buf.blit(overlay, (0, 0))

        if render_scale > 1:
            scaled = pg.transform.smoothscale(buf, (win_w, win_h))
            screen.blit(scaled, (0, 0))
        else:
            screen.blit(buf, (0, 0))

        pg.display.flip()
        clock.tick(fps_cap)
        tick += 1

    try:
        level_slot.value = 0.0
    except Exception:
        pass
    pg.quit()


class MangoHud:
    """Orb HUD controller; safe no-op when disabled via ``MANGO_HUD``."""

    def __init__(self, process: mp.Process, q: Queue, level_slot: Any) -> None:
        self._proc = process
        self._queue = q
        self._level_slot = level_slot

    def level_sink(self) -> Any:
        return self._level_slot

    @classmethod
    def try_start(cls) -> MangoHud | None:
        if not _enabled_from_env():
            return None
        ctx = mp.get_context("spawn")
        q = ctx.Queue()
        level_slot = ctx.Value("d", 0.0)
        proc = ctx.Process(
            target=mango_hud_main,
            args=(q, level_slot),
            daemon=True,
        )
        proc.start()
        time.sleep(0.35)
        if not proc.is_alive():
            logger.warning("Mango HUD process exited immediately — check pygame / display.")
            return None
        logger.info("Mango HUD window started.")
        return cls(proc, q, level_slot)

    def set_state(self, state: str) -> None:
        if state not in ("listening", "thinking", "speaking"):
            return
        try:
            self._queue.put_nowait(state)
        except Exception:
            logger.debug("HUD queue put failed", exc_info=True)

    def close(self) -> None:
        try:
            self._level_slot.value = 0.0
        except Exception:
            pass
        try:
            self._queue.put_nowait("quit")
        except Exception:
            pass
        if self._proc.is_alive():
            self._proc.join(timeout=3.0)
        if self._proc.is_alive():
            self._proc.terminate()
            self._proc.join(timeout=1.0)


# Backward compatibility
JarvisHud = MangoHud
jarvis_hud_main = mango_hud_main
