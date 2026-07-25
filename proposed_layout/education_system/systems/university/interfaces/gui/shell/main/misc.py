# Miscellaneous legacy helpers.
#
# Most of this file is dead code retained for backward compatibility.
# The GUI is now always launched pre-authenticated via run.py and the
# universal login (education_system/shared/gui/login_gui.py).

import tkinter as tk
from tkinter import ttk
import logging
from education_system.systems.university.infrastructure.i18n import get_text as _t

logger = logging.getLogger(__name__)
