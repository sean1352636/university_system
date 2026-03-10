"""
Pytest configuration for finance GUI tests.

Mocks matplotlib and tkinter to allow tests to run in headless environments.
"""

import sys
from unittest.mock import MagicMock

# Mock GUI-related modules before any finance modules are imported
# This prevents matplotlib from trying to use TkAgg backend in headless environments

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

# Mock tkinter components
mock_tk = MagicMock()
mock_tk.Tk = MagicMock
mock_tk.Toplevel = MagicMock
mock_tk.Frame = MagicMock
mock_tk.Label = MagicMock
mock_tk.Button = MagicMock
mock_tk.Entry = MagicMock
mock_tk.Text = MagicMock
mock_tk.Canvas = MagicMock
mock_tk.Listbox = MagicMock
mock_tk.Scrollbar = MagicMock
mock_tk.Menu = MagicMock
mock_tk.StringVar = MagicMock
mock_tk.IntVar = MagicMock
mock_tk.DoubleVar = MagicMock
mock_tk.BooleanVar = MagicMock
mock_tk.END = 'end'
mock_tk.BOTH = 'both'
mock_tk.LEFT = 'left'
mock_tk.RIGHT = 'right'
mock_tk.TOP = 'top'
mock_tk.BOTTOM = 'bottom'
mock_tk.X = 'x'
mock_tk.Y = 'y'
mock_tk.HORIZONTAL = 'horizontal'
mock_tk.VERTICAL = 'vertical'
mock_tk.NORMAL = 'normal'
mock_tk.DISABLED = 'disabled'
mock_tk.WORD = 'word'
mock_tk.NONE = 'none'

sys.modules['tkinter'] = mock_tk
sys.modules['tkinter.ttk'] = MagicMock()
sys.modules['tkinter.messagebox'] = MagicMock()
sys.modules['tkinter.simpledialog'] = MagicMock()
sys.modules['tkinter.filedialog'] = MagicMock()
sys.modules['tkinter.colorchooser'] = MagicMock()
sys.modules['tkinter.font'] = MagicMock()
sys.modules['tkinter.scrolledtext'] = MagicMock()

# Mock PIL/Pillow (used by some finance modules)
sys.modules['PIL'] = MagicMock()
sys.modules['PIL.Image'] = MagicMock()
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

# Mock qrcode
sys.modules['qrcode'] = MagicMock()

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
