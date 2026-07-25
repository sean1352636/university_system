"""Local fixtures for the Exam Portal GUI tests.

These tests assert on *live* tkinter widget state — notebook tab labels,
treeview columns, ``get_children()`` — which the suite-wide headless
``tk.Tk()`` neutering (see the root ``conftest.py``) makes impossible,
since every Tcl call there returns a ``MagicMock``.

This directory-scoped, autouse fixture temporarily restores the real
``tkinter.Tk`` methods that the root conftest stashed in
``tk._HEADLESS_REAL`` so real widgets can be built, then puts the
neutered versions back on teardown so no other test module is affected.
If no display is reachable, the test is skipped rather than failed —
these are ``@pytest.mark.gui`` tests that genuinely need one.

Headless: while the real tkinter is active we wrap
``Tk.__init__``/``Toplevel.__init__`` to ``withdraw()`` each window the
moment it's created. The tests never call ``mainloop()``/``deiconify()``,
so a withdrawn window is never mapped — every widget still behaves like a
real one, but nothing is ever displayed on screen.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _live_tkinter(request):
    import tkinter as tk

    # Only restore real tkinter for the live-widget tests marked ``gui``.
    # Headless tests in this directory (e.g. test_exam_service.py) must stay
    # on the neutered tkinter so they never open a real probe window.
    if request.node.get_closest_marker("gui") is None:
        yield
        return

    real = getattr(tk, "_HEADLESS_REAL", None)
    if not real:
        # Root conftest never neutered tkinter (e.g. real tkinter missing
        # entirely) — nothing to restore.
        yield
        return

    # Remember the current (neutered) versions so we can put them back.
    neutered = {name: getattr(tk.Tk, name) for name in real}
    for name, fn in real.items():
        setattr(tk.Tk, name, fn)

    # Probe for a usable display; if there isn't one, restore and skip.
    try:
        probe = tk.Tk()
        probe.destroy()
    except Exception:
        for name, fn in neutered.items():
            setattr(tk.Tk, name, fn)
        pytest.skip("No display available for live tkinter GUI tests")

    saved_default_root = getattr(tk, "_default_root", None)
    tk._default_root = None

    # Auto-hide every window: real Tcl, but withdrawn immediately so it is
    # never mapped onto the screen.
    real_tk_init = tk.Tk.__init__
    real_top_init = tk.Toplevel.__init__

    def _hidden_tk_init(self, *a, **k):
        real_tk_init(self, *a, **k)
        try:
            self.withdraw()
        except Exception:
            pass

    def _hidden_top_init(self, *a, **k):
        real_top_init(self, *a, **k)
        try:
            self.withdraw()
        except Exception:
            pass

    tk.Tk.__init__ = _hidden_tk_init
    tk.Toplevel.__init__ = _hidden_top_init

    # Neuter blocking modal dialogs (messagebox/simpledialog/filedialog) so a
    # stray ``showerror``/``askstring`` can't spin its own modal loop and hang
    # the test until timeout. Tests that assert on them install their own patch.
    restore_dialogs = _stub_blocking_dialogs()
    try:
        yield
    finally:
        restore_dialogs()
        tk.Toplevel.__init__ = real_top_init
        for name, fn in neutered.items():
            setattr(tk.Tk, name, fn)
        tk._default_root = saved_default_root


def _stub_blocking_dialogs():
    """Replace modal tkinter dialog functions with non-blocking stubs.

    Returns a callable that restores the originals.
    """
    from unittest.mock import MagicMock
    import tkinter.messagebox as _mb
    import tkinter.simpledialog as _sd
    import tkinter.filedialog as _fd

    stubs = {
        _mb: {
            "showinfo": None, "showwarning": None, "showerror": None,
            "askyesno": False, "askokcancel": False, "askretrycancel": False,
            "askyesnocancel": False, "askquestion": "no",
        },
        _sd: {"askstring": None, "askinteger": None, "askfloat": None},
        _fd: {
            "askopenfilename": "", "asksaveasfilename": "", "askdirectory": "",
            "askopenfilenames": (), "askopenfile": None, "asksaveasfile": None,
        },
    }

    saved = []
    for mod, funcs in stubs.items():
        for name, retval in funcs.items():
            if hasattr(mod, name):
                saved.append((mod, name, getattr(mod, name)))
                setattr(mod, name, MagicMock(return_value=retval))

    def restore():
        for mod, name, fn in saved:
            setattr(mod, name, fn)

    return restore
