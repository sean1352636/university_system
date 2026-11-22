"""Capture print() output of the current thread only.

Swapping ``sys.stdout`` for a StringIO on a worker thread captures every
thread's prints for as long as the worker runs, and leaves stdout redirected
if the worker dies before restoring it. ``capture_stdout()`` instead installs
(once) a router that sends each thread's writes to that thread's buffer, or
to the real stdout when the thread isn't capturing.

    with capture_stdout() as buf:
        generate_revenue_summary()
    report_output = buf.getvalue()
"""

from __future__ import annotations

import io
import sys
import threading
from contextlib import contextmanager
from typing import Iterator, TextIO

_local = threading.local()
_install_lock = threading.Lock()


class _ThreadRouter:
    def __init__(self, fallback: TextIO) -> None:
        self._fallback = fallback

    def _target(self) -> TextIO:
        buf = getattr(_local, "buf", None)
        return self._fallback if buf is None else buf

    def write(self, s: str) -> int:
        return self._target().write(s)

    def flush(self) -> None:
        self._target().flush()

    def __getattr__(self, name: str):
        # encoding, isatty, fileno, ... come from the real stream.
        return getattr(self._fallback, name)


@contextmanager
def capture_stdout() -> Iterator[io.StringIO]:
    with _install_lock:
        if not isinstance(sys.stdout, _ThreadRouter):
            sys.stdout = _ThreadRouter(sys.stdout)
    buf = io.StringIO()
    prev = getattr(_local, "buf", None)
    _local.buf = buf
    try:
        yield buf
    finally:
        _local.buf = prev
