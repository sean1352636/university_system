"""Log Analyzer adapter — embeds the standalone analyzer from
``shared/extras/log-analyzer/`` into a parent frame.

The original module is path-based (``shared/extras`` isn't a Python
package), so we load it via importlib rather than dotted import.
"""

import importlib.util
import os
import tkinter as tk
from tkinter import ttk


def _load_analyzer_module():
    """Load shared/extras/log-analyzer/log_analyzer.py as a module."""
    here = os.path.dirname(os.path.abspath(__file__))
    # operations_console -> shared/gui -> modules/shared -> modules ->
    # university_system -> education_system -> repo root
    repo_root = os.path.normpath(os.path.join(here, "..", "..", "..", "..", "..", ".."))
    target = os.path.join(repo_root, "education_system", "shared", "extras",
                          "log-analyzer", "log_analyzer.py")
    spec = importlib.util.spec_from_file_location("operations_console_log_analyzer", target)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_log_analyzer_panel(parent):
    """Render the Log Analyzer into ``parent``.

    Returns a dict with ``frame`` and ``stop`` for parity with the
    other operations-console adapters.
    """
    container = ttk.Frame(parent)
    container.pack(fill=tk.BOTH, expand=True)

    try:
        mod = _load_analyzer_module()
    except Exception as e:
        ttk.Label(container,
                  text=f"Log Analyzer unavailable: {e}",
                  foreground="#c62828").pack(padx=20, pady=20)
        return {'frame': container, 'stop': lambda: None}

    # The analyzer packs its widgets directly onto the root it's given.
    mod.LogAnalyzerApp(container, embedded=True)
    return {'frame': container, 'stop': lambda: None}
