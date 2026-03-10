"""Base class for StudentAnalytics: init, DB connection, directories, plot helpers."""

import os
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.shared.constants import paths

from .config import CONFIG, GUI_AVAILABLE


class StudentAnalyticsBase:
    def __init__(self, gui_mode=False):
        # Use the database connection from the infrastructure
        conn = get_connection()
        if hasattr(conn, 'execute'):
            # Get database path from connection
            self.db_path = conn.execute("PRAGMA database_list").fetchone()[2] if conn else str(paths.DEFAULT_DB_PATH)
            conn.close()
        else:
            self.db_path = str(paths.DEFAULT_DB_PATH)
        # Use canonical analytics directories
        self.plots_dir = str(paths.ANALYTICS_PLOTS_DIR)
        self.reports_dir = str(paths.ANALYTICS_REPORTS_DIR)
        self.create_directories()
        self.custom_filters = {}
        self.gui_mode = gui_mode  # Flag to control output mode

    def create_directories(self):
        """Create necessary directories"""
        for directory in [self.plots_dir, self.reports_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory)

    def get_connection(self):
        """Get database connection"""
        return get_connection()

    def safe_plot_data(self, x_data, y_data):
        """Ensure data is finite before plotting"""
        mask = np.isfinite(x_data) & np.isfinite(y_data)
        return x_data[mask], y_data[mask]

    def save_or_display_plot(self, plt_figure, plot_type, export_format='png'):
        """Enhanced plot saving with multiple format support"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        if export_format == 'png':
            filename = f"{self.plots_dir}/{plot_type}_{timestamp}.png"
            plt_figure.savefig(filename, dpi=CONFIG['dpi'], bbox_inches='tight')
        elif export_format == 'pdf':
            filename = f"{self.plots_dir}/{plot_type}_{timestamp}.pdf"
            plt_figure.savefig(filename, format='pdf', bbox_inches='tight')
        elif export_format == 'svg':
            filename = f"{self.plots_dir}/{plot_type}_{timestamp}.svg"
            plt_figure.savefig(filename, format='svg', bbox_inches='tight')

        # In GUI mode, just return the figure - let the GUI wrapper handle display
        if self.gui_mode:
            return plt_figure

        # CLI mode - prompt user for action
        if GUI_AVAILABLE:
            while True:
                choice = input(f"Would you like to (1) save, (2) display, or (3) both? Enter 1, 2, or 3: ")

                if choice == '1':
                    print(f"Plot saved to {filename}")
                    plt.close(plt_figure)
                    break
                elif choice == '2':
                    try:
                        plt.figure(plt_figure.number)
                        print(f"Displaying {plot_type}...")
                        plt.show()
                        break
                    except Exception as e:
                        print(f"Error displaying plot: {e}")
                        print(f"Plot saved to {filename}")
                        plt.close(plt_figure)
                        break
                elif choice == '3':
                    try:
                        print(f"Plot saved to {filename}")
                        plt.figure(plt_figure.number)
                        plt.show()
                        break
                    except Exception as e:
                        print(f"Plot saved to {filename}")
                        plt.close(plt_figure)
                        break
                else:
                    print("Invalid choice. Please enter 1, 2, or 3.")
        else:
            print(f"Plot automatically saved to {filename}")
            plt.close(plt_figure)
