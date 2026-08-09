"""Fixtures for shell tests that exercise a real Tk event loop."""

import pytest


@pytest.fixture(autouse=True)
def live_tkinter(request):
    """Temporarily restore Tk methods neutered by the university conftest."""
    if request.node.get_closest_marker("gui") is None:
        yield
        return

    import tkinter as tk

    real_methods = getattr(tk, "_HEADLESS_REAL", None)
    if not real_methods:
        yield
        return

    mocked_methods = {name: getattr(tk.Tk, name) for name in real_methods}
    saved_default_root = getattr(tk, "_default_root", None)
    for name, method in real_methods.items():
        setattr(tk.Tk, name, method)
    tk._default_root = None

    try:
        probe = tk.Tk()
        probe.withdraw()
        probe.destroy()
    except Exception:
        for name, method in mocked_methods.items():
            setattr(tk.Tk, name, method)
        tk._default_root = saved_default_root
        pytest.skip("No display available for live Tk lifecycle tests")

    try:
        yield
    finally:
        for child in (
            list(getattr(tk, "_default_root", None).winfo_children())
            if getattr(tk, "_default_root", None)
            else []
        ):
            child.destroy()
        if getattr(tk, "_default_root", None):
            tk._default_root.destroy()
        for name, method in mocked_methods.items():
            setattr(tk.Tk, name, method)
        tk._default_root = saved_default_root
