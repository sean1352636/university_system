"""
Pytest configuration for finance GUI tests.

Mocks matplotlib and optional dependencies for headless test environments.
"""

import sys
from unittest.mock import MagicMock

# Mock GUI-related modules before any finance modules are imported
# This prevents matplotlib from trying to use TkAgg backend in headless environments
#
# NOTE: Do NOT mock PIL (base package), qrcode, or tkinter here — mocking
# top-level packages via sys.modules poisons them globally for the entire
# pytest session, breaking later tests that need the real modules.
# Only mock sub-modules that require a display (e.g. PIL.ImageTk,
# matplotlib.backends.backend_tkagg).

# Mock matplotlib
mock_matplotlib = MagicMock()
mock_matplotlib.use = MagicMock()
sys.modules['matplotlib'] = mock_matplotlib
sys.modules['matplotlib.pyplot'] = MagicMock()
sys.modules['matplotlib.figure'] = MagicMock()
sys.modules['matplotlib.backends'] = MagicMock()
sys.modules['matplotlib.backends.backend_tkagg'] = MagicMock()
sys.modules['matplotlib.backends.backend_agg'] = MagicMock()

# Mock seaborn
sys.modules['seaborn'] = MagicMock()

# Mock only PIL.ImageTk (requires display); leave PIL and PIL.Image real
sys.modules['PIL.ImageTk'] = MagicMock()

# Mock reportlab (PDF generation) - must be comprehensive
mock_reportlab = MagicMock()
mock_reportlab_graphics = MagicMock()
mock_reportlab_graphics_charts = MagicMock()

sys.modules['reportlab'] = mock_reportlab
sys.modules['reportlab.lib'] = MagicMock()
sys.modules['reportlab.lib.pagesizes'] = MagicMock()
sys.modules['reportlab.lib.styles'] = MagicMock()
sys.modules['reportlab.lib.colors'] = MagicMock()
sys.modules['reportlab.lib.units'] = MagicMock()
sys.modules['reportlab.lib.enums'] = MagicMock()
sys.modules['reportlab.platypus'] = MagicMock()
sys.modules['reportlab.platypus.doctemplate'] = MagicMock()
sys.modules['reportlab.platypus.flowables'] = MagicMock()
sys.modules['reportlab.platypus.paragraph'] = MagicMock()
sys.modules['reportlab.platypus.tables'] = MagicMock()
sys.modules['reportlab.graphics'] = mock_reportlab_graphics
sys.modules['reportlab.graphics.shapes'] = MagicMock()
sys.modules['reportlab.graphics.charts'] = mock_reportlab_graphics_charts
sys.modules['reportlab.graphics.charts.barcharts'] = MagicMock()
sys.modules['reportlab.graphics.charts.linecharts'] = MagicMock()
sys.modules['reportlab.graphics.charts.piecharts'] = MagicMock()
sys.modules['reportlab.graphics.charts.legends'] = MagicMock()
sys.modules['reportlab.graphics.widgets'] = MagicMock()
sys.modules['reportlab.graphics.widgets.markers'] = MagicMock()

# Mock sklearn (used in some finance modules for anomaly detection)
sys.modules['sklearn'] = MagicMock()
sys.modules['sklearn.ensemble'] = MagicMock()
sys.modules['sklearn.preprocessing'] = MagicMock()
sys.modules['sklearn.cluster'] = MagicMock()

# Mock joblib
sys.modules['joblib'] = MagicMock()

# Mock cryptography
sys.modules['cryptography'] = MagicMock()
sys.modules['cryptography.fernet'] = MagicMock()
