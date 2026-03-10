"""Global configuration, matplotlib setup, and constants for student analytics."""

import matplotlib
import matplotlib.pyplot as plt
import seaborn as sns
import warnings


def configure_matplotlib():
    """Configure matplotlib backend with proper GUI support and error handling"""
    try:
        import tkinter
        # Test if tkinter actually works
        root = tkinter.Tk()
        root.withdraw()  # Hide the test window
        root.destroy()   # Clean up test window

        matplotlib.use('TkAgg')
        print("✓ GUI mode enabled with TkAgg backend")
        return True
    except Exception as e:
        print(f"TkAgg not available ({e}), trying Qt5Agg...")
        try:
            matplotlib.use('Qt5Agg')
            print("✓ GUI mode enabled with Qt5Agg backend")
            return True
        except Exception as e2:
            print(f"Qt5Agg not available ({e2}), trying other backends...")
            try:
                matplotlib.use('GTK3Agg')
                print("✓ GUI mode enabled with GTK3Agg backend")
                return True
            except Exception as e3:
                print(f"No GUI backends available, falling back to Agg")
                matplotlib.use('Agg')
                return False

# Configure matplotlib and seaborn at startup
GUI_AVAILABLE = configure_matplotlib()
sns.set_style("whitegrid")
plt.style.use('seaborn-v0_8')
warnings.filterwarnings('ignore')

# Global configuration
CONFIG = {
    'colors': ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b'],
    'figure_size': (15, 10),
    'dpi': 300,
    'export_formats': ['png', 'pdf', 'svg', 'excel'],
    'email_config': {
        'smtp_server': 'smtp.gmail.com',
        'smtp_port': 587,
        'sender_email': '',
        'sender_password': ''
    }
}
