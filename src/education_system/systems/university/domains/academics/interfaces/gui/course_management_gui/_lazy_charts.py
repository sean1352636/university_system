"""Deferred access to the plotting stack (matplotlib / seaborn / numpy).

Both ``core/_imports.py`` and ``analytics/analytics.py`` used to open with the
same eager block::

    import matplotlib
    matplotlib.use('TkAgg')
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    import seaborn as sns
    import numpy as np
    CHARTS_AVAILABLE = True

Importing seaborn pulls matplotlib, pandas and scipy — about 4.7s and ~950
modules. That cost was paid every time the Course Management window was opened,
whether or not the user went near a chart; only the analytics dialogs plot
anything.

The names exported here behave like the originals at every use site (they are
called or attribute-accessed inside methods), but the real import happens on
first touch. ``CHARTS_AVAILABLE`` is answered with ``find_spec``, so the
"install matplotlib and seaborn" guidance still appears when the packages are
genuinely missing, without importing them to find out.
"""

from importlib import import_module
from importlib.util import find_spec

#: True when the plotting stack is installed. Resolved without importing it.
CHARTS_AVAILABLE = (
    find_spec("matplotlib") is not None and find_spec("seaborn") is not None
)

_resolved: dict = {}


def _load(module_name: str):
    """Import *module_name*, selecting the Tk backend before pyplot loads."""
    if module_name not in _resolved:
        if module_name in ("matplotlib.pyplot", "matplotlib.figure",
                           "matplotlib.backends.backend_tkagg"):
            # matplotlib.use() must run before pyplot is imported.
            mpl = import_module("matplotlib")
            if not _resolved.get("_backend_set"):
                mpl.use("TkAgg")
                _resolved["_backend_set"] = True
        _resolved[module_name] = import_module(module_name)
    return _resolved[module_name]


class _LazyModule:
    """Stands in for a module, importing it on first attribute access."""

    __slots__ = ("_module_name",)

    def __init__(self, module_name):
        self._module_name = module_name

    def __getattr__(self, attr):
        return getattr(_load(self._module_name), attr)

    def __repr__(self):
        return f"<lazy module {self._module_name}>"


class _LazyAttr:
    """Stands in for a class/callable inside a module (Figure, canvas, ...)."""

    __slots__ = ("_module_name", "_attr")

    def __init__(self, module_name, attr):
        self._module_name = module_name
        self._attr = attr

    def _resolve(self):
        return getattr(_load(self._module_name), self._attr)

    def __call__(self, *args, **kwargs):
        return self._resolve()(*args, **kwargs)

    def __getattr__(self, attr):
        return getattr(self._resolve(), attr)

    def __repr__(self):
        return f"<lazy {self._module_name}.{self._attr}>"


plt = _LazyModule("matplotlib.pyplot")
sns = _LazyModule("seaborn")
np = _LazyModule("numpy")
Figure = _LazyAttr("matplotlib.figure", "Figure")
FigureCanvasTkAgg = _LazyAttr("matplotlib.backends.backend_tkagg", "FigureCanvasTkAgg")

__all__ = ["CHARTS_AVAILABLE", "plt", "sns", "np", "Figure", "FigureCanvasTkAgg"]
