"""Run work on a background thread and hand results back to Tk safely.

Tkinter may only be touched from the main thread. A worker that calls
``var.set()``, ``widget.config()``, ``messagebox.*`` -- or even
``widget.after()`` -- raises ``RuntimeError: main thread is not in main
loop`` whenever the main thread is not inside ``mainloop()`` (a window built
before the loop starts, or run from ``wait_window``).

Usage::

    from education_system.platform.delivery.gui.tk_threads import start_thread, ui

    def _work():
        rows = slow_query()
        ui(tree, populate, rows)          # runs populate(rows) on the main thread

    start_thread(tree, _work)             # call from the main thread

``ui()`` never makes a Tcl call from the worker: it puts the callable on a
queue that a main-thread ``after()`` pump drains while any helper-started
thread is alive.
"""

from __future__ import annotations

import logging
import queue
import threading
import tkinter as tk
from typing import Any, Callable

logger = logging.getLogger(__name__)

_POLL_MS = 50
_lock = threading.Lock()
_pumps: dict[int, "_Pump"] = {}


class _Pump:
    def __init__(self, root: tk.Misc) -> None:
        self.root = root
        self.key = id(root.tk)
        self.queue: "queue.Queue[tuple[Callable[..., Any], tuple, dict]]" = queue.Queue()
        self.active = 0
        self.ticking = False

    def ensure_ticking(self) -> None:
        # Main thread only.
        if not self.ticking:
            self.ticking = True
            try:
                self.root.after(_POLL_MS, self._tick)
            except tk.TclError:
                self._retire()

    def _tick(self) -> None:
        while True:
            try:
                fn, args, kwargs = self.queue.get_nowait()
            except queue.Empty:
                break
            try:
                fn(*args, **kwargs)
            except tk.TclError:
                # Target widget was closed before the worker finished.
                logger.debug("tk_threads: UI callback hit a destroyed widget", exc_info=True)
            except Exception:
                logger.exception("tk_threads: UI callback failed")
        with _lock:
            keep_going = self.active > 0 or not self.queue.empty()
            if not keep_going:
                self.ticking = False
        if keep_going:
            try:
                self.root.after(_POLL_MS, self._tick)
            except tk.TclError:
                self._retire()

    def _retire(self) -> None:
        self.ticking = False
        with _lock:
            if _pumps.get(self.key) is self:
                del _pumps[self.key]


def _pump_for(widget: tk.Misc, create: bool) -> "_Pump | None":
    key = id(widget.tk)
    with _lock:
        pump = _pumps.get(key)
        if pump is None and create:
            pump = _pumps[key] = _Pump(widget._root())
        return pump


def _on_main_thread() -> bool:
    return threading.current_thread() is threading.main_thread()


def start_thread(widget: tk.Misc, target: Callable[..., Any], *args: Any,
                 name: str | None = None, daemon: bool = True,
                 **kwargs: Any) -> threading.Thread:
    """Start ``target(*args, **kwargs)`` on a daemon thread. Call from the main thread.

    While the thread runs, ``ui()`` calls made from it are delivered on the
    main thread.
    """
    pump = _pump_for(widget, create=True)
    assert pump is not None

    def _run() -> None:
        try:
            target(*args, **kwargs)
        finally:
            with _lock:
                pump.active -= 1

    with _lock:
        pump.active += 1
    if _on_main_thread():
        pump.ensure_ticking()
    thread = threading.Thread(target=_run, name=name, daemon=daemon)
    thread.start()
    return thread


def hold(widget: tk.Misc) -> Callable[[], None]:
    """Keep the pump ticking until the returned release() is called. Main thread only.

    For listeners that other threads call back at arbitrary times (event-bus
    subscribers, log handlers) rather than threads started here. release()
    is idempotent.
    """
    pump = _pump_for(widget, create=True)
    assert pump is not None
    with _lock:
        pump.active += 1
    pump.ensure_ticking()
    released = False

    def release() -> None:
        nonlocal released
        with _lock:
            if released:
                return
            released = True
            pump.active -= 1

    return release


def ui(widget: tk.Misc, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
    """Run ``fn(*args, **kwargs)`` on the Tk main thread. Safe from any thread.

    ``widget`` only identifies the Tk interpreter; it may be any widget in
    the window. On the main thread ``fn`` runs immediately.
    """
    if _on_main_thread():
        fn(*args, **kwargs)
        return
    pump = _pump_for(widget, create=True)
    assert pump is not None
    pump.queue.put((fn, args, kwargs))
