"""Local fixtures for the grading GUI/dialog tests.

Many tests in this directory build *live* tkinter dialogs (EditGradeDialog,
ModuleEnrollmentDialog, etc.) and assert on real widget state — e.g.
``score_var.get() == "85.0"`` or treeview ``get_children()``. The suite-wide
headless ``tk.Tk()`` neutering in the root ``conftest.py`` makes that
impossible, since every Tcl call there returns a ``MagicMock`` (so
``StringVar.get()`` yields a mock instead of the stored string).

This directory-scoped, autouse fixture temporarily restores the real
``tkinter.Tk`` methods that the root conftest stashed in ``tk._HEADLESS_REAL``
so real widgets can be built, then puts the neutered versions back on teardown
so no other test module is affected. It also clears ``tk._default_root`` for the
duration so that bare ``tk.StringVar()``/``tk.Toplevel()`` calls (which have no
explicit master) bind to the real root each test creates via its ``root``
fixture, not the stale mock default root. If no display is reachable, the test
is skipped rather than failed — these are ``@pytest.mark.gui`` tests that
genuinely need one.

Headless: real Tcl is needed for the widget assertions, but the windows must
not flash up on the developer's screen. So while the real tkinter is active we
wrap ``Tk.__init__``/``Toplevel.__init__`` to ``withdraw()`` each window the
moment it's created. The tests never call ``mainloop()``/``deiconify()``, so a
withdrawn window is never mapped — every widget still behaves like a real one,
but nothing is ever displayed.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _live_tkinter(request):
    import tkinter as tk

    # Only the live-widget GUI tests (marked ``gui``) need the real tkinter
    # restored. Headless tests in this directory (e.g. test_comparisons.py)
    # must stay on the suite-wide neutered tkinter so they never open a real
    # window — otherwise the autouse fixture would pop a probe window for
    # every non-GUI test in the directory.
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
    # Clear the mock default root so the next real ``tk.Tk()`` (created by a
    # test's ``root`` fixture) becomes the default that master-less variables
    # and widgets bind to.
    tk._default_root = None

    # Auto-hide every window: real Tcl, but withdrawn immediately so it is
    # never mapped onto the screen. Wrap the now-restored real __init__ of
    # both Tk and Toplevel.
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

    # Neuter blocking modal dialogs. ``messagebox.showerror`` /
    # ``simpledialog.askstring`` / ``filedialog.askopenfilename`` etc. spin
    # their own modal event loop and wait for a human to click — which never
    # happens under test and hangs until the timeout fires. Replace them with
    # non-blocking stubs returning safe defaults. Tests that assert on these
    # calls install their own ``@patch`` over the top, which still works.
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
