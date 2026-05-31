"""Desktop shell for Mango: dedicated window + voice core in a child process.

The voice/STT/LLM/TTS stack runs in a separate process so pygame + sounddevice stay on
that process's main thread (Windows-friendly).

When **pywebview** is installed, the shell is a **large window** loading ``desktop.html``:
the **3D globe (globe.gl) fills the view** and a **compact Mango panel** sits in the **bottom-right** corner.

Otherwise the shell falls back to **Tk** (no external browser; install **pywebview** for the embedded globe window).

The parent starts the static HTTP server first and sets ``MANGO_GLOBE_PORT`` so the voice
process serves URLs against the same port without binding a second server.

Launch: ``python -m mango --desktop``
"""

from __future__ import annotations

import json
import logging
import multiprocessing
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import font as tkfont
from typing import Any
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)


def _voice_process_entry(
    stop_event: multiprocessing.Event,
    desktop_queue: multiprocessing.Queue | None,
) -> None:
    """Child process target — must be top-level for Windows spawn."""
    import mango.desktop.desktop_ipc as desktop_ipc
    from mango.logging_setup import setup_logging
    from mango.main import run_voice_session

    setup_logging()
    if desktop_queue is not None:
        desktop_ipc.attach_parent_queue(desktop_queue)
    run_voice_session(stop_event=stop_event)


def _screen_dimensions() -> tuple[int, int]:
    if sys.platform == "win32":
        try:
            import ctypes

            user32 = ctypes.windll.user32
            return int(user32.GetSystemMetrics(0)), int(user32.GetSystemMetrics(1))
        except Exception:
            pass
    try:
        r = tk.Tk()
        r.withdraw()
        w, h = r.winfo_screenwidth(), r.winfo_screenheight()
        r.destroy()
        return int(w), int(h)
    except Exception:
        return 1920, 1080


def _desktop_webview_geometry(screen_w: int, screen_h: int) -> tuple[int, int, int, int]:
    """Nearly full screen — map is the background; Mango UI is only the corner card in HTML."""
    margin = 6
    taskbar = 52
    width = max(480, screen_w - 2 * margin)
    height = max(400, screen_h - 2 * margin - taskbar)
    x = margin
    y = margin
    return width, height, x, y


def _parse_globe_message(msg: dict[str, Any]) -> tuple[float, float, str] | None:
    label = str(msg.get("label") or "")
    lat_q = msg.get("lat")
    lng_q = msg.get("lng")
    if lat_q is not None and lng_q is not None:
        try:
            return float(lat_q), float(lng_q), label
        except (TypeError, ValueError):
            pass
    url = str(msg.get("url") or "")
    if not url:
        return None
    try:
        q = urlparse(url).query
        qs = parse_qs(q)
        lat = float(qs.get("lat", ["nan"])[0])
        lng = float(qs.get("lng", ["nan"])[0])
        if not (lat == lat and lng == lng):  # NaN check
            return None
        return lat, lng, label
    except Exception:
        return None


def _run_desktop_webview(
    ipc_queue: multiprocessing.Queue,
    stop_event: multiprocessing.Event,
    proc: multiprocessing.Process,
    http_port: int,
) -> None:
    import webview

    from mango.desktop.globe_server import DESKTOP_ASSET_VER

    sw, sh = _screen_dimensions()
    ww, wh, gx, gy = _desktop_webview_geometry(sw, sh)
    desk_url = f"http://127.0.0.1:{http_port}/desktop.html?v={DESKTOP_ASSET_VER}"

    pending_globe: dict[str, Any] | None = None
    pending_globe_visible: bool | None = False
    pending_ai_state: str | None = "listening"

    class MangoApi:
        def quit(self) -> None:
            logger.info("Desktop Quit requested from UI.")
            stop_event.set()
            try:
                for w in list(webview.windows):
                    webview.destroy_window(w)
            except Exception:
                logger.debug("destroy_window", exc_info=True)

    api = MangoApi()

    window = webview.create_window(
        "Mango",
        desk_url,
        width=ww,
        height=wh,
        x=gx,
        y=gy,
        js_api=api,
    )

    try:
        if hasattr(window, "events"):
            def _on_closing() -> bool:
                stop_event.set()
                return True

            window.events.closing += _on_closing  # type: ignore[operator]
    except Exception:
        logger.debug("Could not attach closing handler", exc_info=True)

    def flush_pending_globe() -> None:
        nonlocal pending_globe
        if pending_globe is None:
            return
        wins = webview.windows
        if not wins:
            return
        parsed = _parse_globe_message(pending_globe)
        if not parsed:
            pending_globe = None
            return
        lat, lng, label = parsed
        bbox_raw = pending_globe.get("bbox") if isinstance(pending_globe, dict) else None
        bbox = bbox_raw if isinstance(bbox_raw, dict) else None
        if bbox:
            js = f"mangoFlyTo({lat}, {lng}, {json.dumps(label)}, true, {json.dumps(bbox)})"
        else:
            js = f"mangoFlyTo({lat}, {lng}, {json.dumps(label)}, true, null)"
        try:
            wins[0].evaluate_js(js)
            pending_globe = None
        except Exception:
            logger.exception("evaluate_js mangoFlyTo failed")

    def flush_pending_state() -> None:
        nonlocal pending_globe_visible
        if pending_globe_visible is None:
            return
        wins = webview.windows
        if not wins:
            return
        js = f"mangoSetGlobeVisible({str(bool(pending_globe_visible)).lower()})"
        try:
            wins[0].evaluate_js(js)
            pending_globe_visible = None
        except Exception:
            logger.exception("evaluate_js mangoSetGlobeVisible failed")

    def flush_pending_ai_state() -> None:
        nonlocal pending_ai_state
        if pending_ai_state is None:
            return
        wins = webview.windows
        if not wins:
            return
        js = f"mangoSetAiState({json.dumps(pending_ai_state)})"
        try:
            wins[0].evaluate_js(js)
            pending_ai_state = None
        except Exception:
            logger.exception("evaluate_js mangoSetAiState failed")

    def ipc_loop() -> None:
        nonlocal pending_globe, pending_globe_visible, pending_ai_state
        while not stop_event.is_set():
            try:
                msg = ipc_queue.get(timeout=0.35)
            except queue.Empty:
                flush_pending_ai_state()
                flush_pending_state()
                flush_pending_globe()
                continue
            if not isinstance(msg, dict):
                continue
            if msg.get("type") == "globe":
                pending_globe_visible = True
                pending_globe = msg
                pending_ai_state = "thinking"
                flush_pending_ai_state()
                flush_pending_state()
                flush_pending_globe()
            elif msg.get("type") == "globe_state":
                pending_globe_visible = bool(msg.get("visible"))
                flush_pending_state()
            elif msg.get("type") == "ai_state":
                s = str(msg.get("state") or "").strip().casefold()
                if s in {"listening", "thinking", "speaking"}:
                    pending_ai_state = s
                    flush_pending_ai_state()

    ipc_thread = threading.Thread(target=ipc_loop, daemon=True, name="MangoDesktopIPC")
    ipc_thread.start()

    try:
        webview.start(debug=False)
    finally:
        stop_event.set()
        if proc.is_alive():
            proc.join(timeout=30.0)
        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=5.0)


def _run_desktop_tk_shell(
    ipc_queue: multiprocessing.Queue,
    stop_event: multiprocessing.Event,
    proc: multiprocessing.Process,
) -> None:
    """Classic Tk control strip with browser-based map opening."""

    root = tk.Tk()
    root.title("Mango")
    root.minsize(360, 220)

    win_w, win_h = 480, 280

    def _place_main_bottom_right() -> None:
        root.update_idletasks()
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        margin = 16
        taskbar = 52
        x = max(0, sw - win_w - margin)
        y = max(0, sh - win_h - margin - taskbar)
        root.geometry(f"{win_w}x{win_h}+{x}+{y}")

    _place_main_bottom_right()

    pad = tk.Frame(root, padx=16, pady=16)
    pad.pack(fill=tk.BOTH, expand=True)

    title_font = tkfont.Font(family="Segoe UI", size=20, weight="bold")
    tk.Label(pad, text="Mango", font=title_font).pack(anchor=tk.W)

    body = tk.Label(
        pad,
        text=(
            "Voice core runs in its own process.\n\n"
            "Map requests open in your web browser (OpenStreetMap, framed on the place).\n"
            "This window stays as Mango control + status.\n"
            "Close this window to quit Mango completely."
        ),
        justify=tk.LEFT,
        wraplength=440,
    )
    body.pack(anchor=tk.W, pady=(12, 8))

    status = tk.Label(pad, text="", fg="#333333", justify=tk.LEFT, wraplength=440)
    status.pack(anchor=tk.W, pady=(0, 12))

    root._globe_win_holder: list[object] = []  # noqa: SLF001
    root._globe_thread_started = False  # noqa: SLF001
    root._globe_note = ""  # noqa: SLF001

    def _globe_geometry() -> tuple[int, int, int, int]:
        root.update_idletasks()
        sh = root.winfo_screenheight()
        ww, wh = 540, 500
        margin = 16
        taskbar = 52
        x = margin
        y = max(0, sh - wh - margin - taskbar)
        return ww, wh, x, y

    def _open_globe(url: str, label: str) -> None:
        import webbrowser

        short = (label or "Globe")[:48]

        try:
            webbrowser.open(url)
            root._globe_note = f"Map opened in browser: {short}"  # noqa: SLF001
        except Exception:
            logger.exception("Could not open globe URL in browser")
            root._globe_note = "Could not open browser map."  # noqa: SLF001

    def poll_ipc() -> None:
        try:
            while True:
                msg = ipc_queue.get_nowait()
                if isinstance(msg, dict) and msg.get("type") == "globe":
                    url = str(msg.get("url") or "").strip()
                    label = str(msg.get("label") or "")
                    if url:
                        _open_globe(url, label)
        except queue.Empty:
            pass
        except Exception:
            logger.warning("desktop IPC poll issue", exc_info=True)
        root.after(200, poll_ipc)

    def refresh_status() -> None:
        if proc.is_alive():
            voice = f"Voice core: running  ·  PID {proc.pid}"
        else:
            voice = "Voice core: exited"
        note = str(getattr(root, "_globe_note", "") or "")
        status.config(text=f"{voice}\n{note}" if note else voice)
        root.after(1500, refresh_status)

    poll_ipc()
    refresh_status()

    def on_quit() -> None:
        stop_event.set()
        if proc.is_alive():
            proc.join(timeout=30.0)
            if proc.is_alive():
                proc.terminate()
                proc.join(timeout=5.0)
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_quit)

    tk.Button(pad, text="Quit Mango", command=on_quit).pack(anchor=tk.E, pady=(8, 0))

    root.mainloop()

    if proc.is_alive():
        proc.join(timeout=10.0)
    if proc.is_alive():
        proc.terminate()


def run_desktop_app() -> None:
    if sys.platform == "win32":
        multiprocessing.freeze_support()

    from mango.desktop.globe_server import ensure_running

    http_port = ensure_running()
    os.environ["MANGO_GLOBE_PORT"] = str(http_port)
    os.environ["MANGO_DESKTOP"] = "1"

    stop_event = multiprocessing.Event()
    ipc_queue: multiprocessing.Queue = multiprocessing.Queue()
    proc = multiprocessing.Process(
        target=_voice_process_entry,
        args=(stop_event, ipc_queue),
        name="MangoVoiceCore",
    )
    proc.start()

    # Reverted flow: use classic Tk control + external browser map view.
    _run_desktop_tk_shell(ipc_queue, stop_event, proc)


if __name__ == "__main__":
    run_desktop_app()
