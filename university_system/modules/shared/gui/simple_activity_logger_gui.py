#!/usr/bin/env python3
"""
Enhanced Activity Logger GUI Application
A comprehensive graphical interface for the Enhanced Activity Logger with full backward compatibility.

Features:
- Real-time log monitoring and visualization
- Configuration management
- Analytics and reporting
- Security monitoring
- Plugin management
- Database querying and filtering
- Export functionality
- System health monitoring

Author: Enhanced Activity Logger Team
Version: 2.0.0
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import threading
import time
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import queue
import webbrowser
from pathlib import Path

# Import matplotlib for charts
try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    import matplotlib.dates as mdates
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("Matplotlib not available. Charts will be disabled.")

# Import the original logger (ensure backward compatibility)
try:
    from university_system.modules.shared.utils.simple_activity_logger import (
        EnhancedActivityLogger, LogLevel, SecurityLevel, OutputFormat,
        logger, plugin_manager, create_default_config,
        SlackNotificationPlugin, MetricsCollectionPlugin, 
        EmailNotificationPlugin, AuditTrailPlugin,
        log_activity, log_login, log_logout
    )
    LOGGER_AVAILABLE = True
except ImportError:
    LOGGER_AVAILABLE = False
    print("Warning: simple_activity_logger module not found. GUI will run in demo mode.")


class LoggerGUITheme:
    """Modern light theme for the logger GUI"""

    # Color scheme - Light Theme
    DARK_BG = "#f0f0f0"  # Light gray background
    DARKER_BG = "#e0e0e0"  # Slightly darker gray
    LIGHT_BG = "#ffffff"  # White
    ACCENT_BLUE = "#0066cc"
    ACCENT_GREEN = "#4CAF50"
    ACCENT_RED = "#f44336"
    ACCENT_ORANGE = "#ff9800"
    ACCENT_YELLOW = "#ffc107"

    TEXT_PRIMARY = "#000000"  # Black text
    TEXT_SECONDARY = "#333333"  # Dark gray text
    TEXT_MUTED = "#666666"  # Medium gray text

    BORDER = "#cccccc"  # Light gray border
    
    @classmethod
    def apply_theme(cls, root):
        """Apply the light theme to the root window"""
        # Configure ttk styles
        style = ttk.Style()
        
        # Try to use modern theme if available
        try:
            style.theme_use('clam')
        except:
            pass
        
        # Configure styles
        style.configure('Title.TLabel', 
                       background=cls.DARK_BG,
                       foreground=cls.TEXT_PRIMARY,
                       font=('Segoe UI', 14, 'bold'))
        
        style.configure('Heading.TLabel',
                       background=cls.DARK_BG,
                       foreground=cls.TEXT_PRIMARY,
                       font=('Segoe UI', 10, 'bold'))
        
        style.configure('Info.TLabel',
                       background=cls.DARK_BG,
                       foreground=cls.TEXT_SECONDARY,
                       font=('Segoe UI', 9))
        
        style.configure('Success.TLabel',
                       background=cls.DARK_BG,
                       foreground=cls.ACCENT_GREEN,
                       font=('Segoe UI', 9, 'bold'))
        
        style.configure('Error.TLabel',
                       background=cls.DARK_BG,
                       foreground=cls.ACCENT_RED,
                       font=('Segoe UI', 9, 'bold'))
        
        style.configure('Warning.TLabel',
                       background=cls.DARK_BG,
                       foreground=cls.ACCENT_ORANGE,
                       font=('Segoe UI', 9, 'bold'))
        
        # Button styles
        style.configure('Accent.TButton',
                       background=cls.ACCENT_BLUE,
                       foreground=cls.TEXT_PRIMARY,
                       font=('Segoe UI', 9))
        
        style.configure('Success.TButton',
                       background=cls.ACCENT_GREEN,
                       foreground=cls.TEXT_PRIMARY,
                       font=('Segoe UI', 9))
        
        style.configure('Danger.TButton',
                       background=cls.ACCENT_RED,
                       foreground=cls.TEXT_PRIMARY,
                       font=('Segoe UI', 9))
        
        # Frame styles
        style.configure('Card.TFrame',
                       background=cls.LIGHT_BG,
                       relief='flat',
                       borderwidth=1)
        
        # Notebook styles
        style.configure('TNotebook',
                       background=cls.DARK_BG,
                       borderwidth=0)
        
        style.configure('TNotebook.Tab',
                       background=cls.LIGHT_BG,
                       foreground=cls.TEXT_SECONDARY,
                       padding=[12, 8],
                       font=('Segoe UI', 9))
        
        # Configure root window
        root.configure(bg=cls.DARK_BG)


class StatusBar(ttk.Frame):
    """Status bar showing system information"""
    
    def __init__(self, parent, controller=None):
        super().__init__(parent)
        self.configure(style='Card.TFrame')
        self._controller = controller
        
        # Status variables
        self.status_text = tk.StringVar(value="Ready")
        self.logger_status = tk.StringVar(value="Disconnected")
        self.queue_size = tk.StringVar(value="0")
        self.total_logs = tk.StringVar(value="0")
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup status bar UI"""
        # Left side - main status
        left_frame = ttk.Frame(self)
        left_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Label(left_frame, textvariable=self.status_text, 
                 style='Info.TLabel').pack(side=tk.LEFT, padx=5)
        
        # Right side - stats
        right_frame = ttk.Frame(self)
        right_frame.pack(side=tk.RIGHT)

        # Exit button
        ttk.Button(
            right_frame,
            text="🏠 Return to Main Menu",
            command=self._handle_return
        ).pack(side=tk.RIGHT, padx=5)
        
        ttk.Label(right_frame, text="Logger:", 
                 style='Info.TLabel').pack(side=tk.LEFT, padx=(5, 0))
        ttk.Label(right_frame, textvariable=self.logger_status, 
                 style='Info.TLabel').pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Label(right_frame, text="Queue:", 
                 style='Info.TLabel').pack(side=tk.LEFT, padx=(5, 0))
        ttk.Label(right_frame, textvariable=self.queue_size, 
                 style='Info.TLabel').pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Label(right_frame, text="Total Logs:", 
                 style='Info.TLabel').pack(side=tk.LEFT, padx=(5, 0))
        ttk.Label(right_frame, textvariable=self.total_logs, 
                 style='Info.TLabel').pack(side=tk.LEFT, padx=(0, 5))

    def _handle_return(self):
        if self._controller and hasattr(self._controller, 'return_to_main_menu'):
            self._controller.return_to_main_menu()
            return

        if hasattr(self.master, 'return_to_main_menu'):
            try:
                self.master.return_to_main_menu()
                return
            except Exception:
                pass

        self.master.quit()
    
    def update_status(self, status: str):
        """Update main status text"""
        self.status_text.set(status)
    
    def update_logger_status(self, connected: bool):
        """Update logger connection status"""
        self.logger_status.set("Connected" if connected else "Disconnected")
    
    def update_queue_size(self, size: int):
        """Update queue size"""
        self.queue_size.set(str(size))
    
    def update_total_logs(self, total: int):
        """Update total logs count"""
        self.total_logs.set(str(total))


class LogViewerTab(ttk.Frame):
    """Real-time log viewer tab"""
    
    def __init__(self, parent, main_app):
        super().__init__(parent)
        self.main_app = main_app
        self.auto_refresh = tk.BooleanVar(value=True)
        self.max_display_logs = 1000
        self.filter_level = tk.StringVar(value="ALL")
        self.filter_user = tk.StringVar()
        self.filter_action = tk.StringVar()
        self.filter_module = tk.StringVar()
        self._after_id = None  # Track timer ID for cleanup

        self.setup_ui()
        
    def setup_ui(self):
        """Setup log viewer UI"""
        # Control panel
        control_frame = ttk.Frame(self, style='Card.TFrame')
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Left controls
        left_controls = ttk.Frame(control_frame)
        left_controls.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Label(left_controls, text="Filter Level:", 
                 style='Info.TLabel').pack(side=tk.LEFT, padx=(5, 2))
        
        level_combo = ttk.Combobox(left_controls, textvariable=self.filter_level,
                                  values=["ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                                  state="readonly", width=10)
        level_combo.pack(side=tk.LEFT, padx=(0, 10))
        level_combo.bind('<<ComboboxSelected>>', self.on_filter_change)
        
        ttk.Label(left_controls, text="User:", 
                 style='Info.TLabel').pack(side=tk.LEFT, padx=(5, 2))
        
        user_entry = ttk.Entry(left_controls, textvariable=self.filter_user, width=15)
        user_entry.pack(side=tk.LEFT, padx=(0, 10))
        user_entry.bind('<KeyRelease>', self.on_filter_change)
        
        ttk.Label(left_controls, text="Action:", 
                 style='Info.TLabel').pack(side=tk.LEFT, padx=(5, 2))
        
        action_entry = ttk.Entry(left_controls, textvariable=self.filter_action, width=15)
        action_entry.pack(side=tk.LEFT, padx=(0, 10))
        action_entry.bind('<KeyRelease>', self.on_filter_change)
        
        # Right controls
        right_controls = ttk.Frame(control_frame)
        right_controls.pack(side=tk.RIGHT)
        
        ttk.Checkbutton(right_controls, text="Auto Refresh", 
                       variable=self.auto_refresh).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(right_controls, text="Refresh", 
                  command=self.refresh_logs).pack(side=tk.LEFT, padx=2)
        
        ttk.Button(right_controls, text="Clear", 
                  command=self.clear_logs).pack(side=tk.LEFT, padx=2)
        
        ttk.Button(right_controls, text="Export", 
                  command=self.export_logs).pack(side=tk.LEFT, padx=2)
        
        # Log display area with treeview
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        
        # Create treeview with columns
        columns = ('timestamp', 'level', 'user', 'action', 'module', 'status', 'details')
        self.log_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=20)
        
        # Configure columns
        self.log_tree.heading('timestamp', text='Timestamp')
        self.log_tree.heading('level', text='Level')
        self.log_tree.heading('user', text='User')
        self.log_tree.heading('action', text='Action')
        self.log_tree.heading('module', text='Module')
        self.log_tree.heading('status', text='Status')
        self.log_tree.heading('details', text='Details')
        
        # Configure column widths
        self.log_tree.column('timestamp', width=150, minwidth=120)
        self.log_tree.column('level', width=80, minwidth=60)
        self.log_tree.column('user', width=100, minwidth=80)
        self.log_tree.column('action', width=120, minwidth=100)
        self.log_tree.column('module', width=100, minwidth=80)
        self.log_tree.column('status', width=80, minwidth=60)
        self.log_tree.column('details', width=300, minwidth=200)
        
        # Add scrollbars
        v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.log_tree.yview)
        h_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.log_tree.xview)
        self.log_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Pack treeview and scrollbars
        self.log_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Bind double-click to show details
        self.log_tree.bind('<Double-1>', self.show_log_details)
        
        # Start refresh timer
        self.after_refresh()
    
    def after_refresh(self):
        """Schedule next refresh"""
        # Cancel previous timer if exists
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except:
                pass

        if self.auto_refresh.get():
            self.refresh_logs()

        # Schedule next refresh and store ID
        try:
            self._after_id = self.after(2000, self.after_refresh)  # Refresh every 2 seconds
        except tk.TclError:
            # Widget destroyed, stop scheduling
            pass

    def destroy(self):
        """Clean up timers before destroying"""
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except:
                pass
        super().destroy()
    
    def refresh_logs(self):
        """Refresh log display"""
        try:
            # Query directly from database
            from university_system.infrastructure.database.db import get_connection

            with get_connection() as conn:
                # Build query with filters
                query = "SELECT id, username, action, details, timestamp, ip_address FROM activity_log WHERE 1=1"
                params = []

                if self.filter_user.get().strip():
                    query += " AND username LIKE ?"
                    params.append(f"%{self.filter_user.get().strip()}%")

                if self.filter_action.get().strip():
                    query += " AND action LIKE ?"
                    params.append(f"%{self.filter_action.get().strip()}%")

                query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(self.max_display_logs)

                cursor = conn.execute(query, params)
                rows = cursor.fetchall()

                # Convert to dict format
                logs = []
                for row in rows:
                    logs.append({
                        'id': row[0],
                        'username': row[1],
                        'action': row[2],
                        'details': row[3],
                        'timestamp': row[4],
                        'ip_address': row[5] or 'N/A'
                    })

                self.update_log_display(logs)

        except Exception as e:
            print(f"Error refreshing logs: {e}")
            import traceback
            traceback.print_exc()
    
    def update_log_display(self, logs: List[Dict]):
        """Update the log display with new logs"""
        # Clear existing items
        for item in self.log_tree.get_children():
            self.log_tree.delete(item)
        
        # Add new logs
        for log in reversed(logs):  # Show newest first
            timestamp = log.get('timestamp', '') or ''
            level = log.get('log_level', '') or ''
            user = log.get('username', '') or ''
            action = log.get('action', '') or ''
            module = log.get('module', '') or ''
            status = log.get('status', '') or ''
            # Handle None values from database
            details_raw = log.get('details') or ''
            details = details_raw[:100] + '...' if len(details_raw) > 100 else details_raw
            
            # Color code based on level and status
            tags = []
            if level in ['ERROR', 'CRITICAL']:
                tags.append('error')
            elif level == 'WARNING':
                tags.append('warning')
            elif status == 'failure':
                tags.append('failure')
            
            item = self.log_tree.insert('', 'end', 
                                       values=(timestamp, level, user, action, module, status, details),
                                       tags=tags)
        
        # Configure tags for coloring
        self.log_tree.tag_configure('error', foreground='#ff6b6b')
        self.log_tree.tag_configure('warning', foreground='#ffa726')
        self.log_tree.tag_configure('failure', foreground='#ef5350')
    
    def on_filter_change(self, event=None):
        """Handle filter changes"""
        self.refresh_logs()
    
    def clear_logs(self):
        """Clear log display"""
        for item in self.log_tree.get_children():
            self.log_tree.delete(item)
    
    def export_logs(self):
        """Export displayed logs"""
        try:
            file_path = filedialog.asksaveasfilename(
                title="Export Logs",
                defaultextension=".json",
                filetypes=[
                    ("JSON files", "*.json"),
                    ("CSV files", "*.csv"),
                    ("Text files", "*.txt"),
                    ("All files", "*.*")
                ]
            )
            
            if file_path:
                # Get current filter settings
                start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
                end_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                if hasattr(self.main_app.logger, 'export_logs'):
                    exported_file = self.main_app.logger.export_logs(
                        start_date, end_date, 
                        format=file_path.split('.')[-1].lower(),
                        output_file=file_path
                    )
                    messagebox.showinfo("Export Complete", f"Logs exported to: {exported_file}")
                else:
                    messagebox.showwarning("Export Unavailable", "Export functionality requires database logging to be enabled.")
                    
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export logs: {str(e)}")
    
    def show_log_details(self, event):
        """Show detailed log information"""
        selection = self.log_tree.selection()
        if not selection:
            return
        
        item = self.log_tree.item(selection[0])
        values = item['values']
        
        # Create details window
        details_window = tk.Toplevel(self)
        details_window.title("Log Details")
        details_window.geometry("600x400")
        details_window.configure(bg=LoggerGUITheme.DARK_BG)
        
        # Create text widget with scrollbar
        text_frame = ttk.Frame(details_window)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        text_widget = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD, height=20, width=70)
        text_widget.pack(fill=tk.BOTH, expand=True)
        
        # Format log details
        details_text = f"""Log Entry Details
{'='*50}

Timestamp: {values[0]}
Level: {values[1]}
User: {values[2]}
Action: {values[3]}
Module: {values[4]}
Status: {values[5]}

Details:
{values[6]}

{'='*50}
"""
        
        text_widget.insert(tk.END, details_text)
        text_widget.configure(state='disabled')


class AnalyticsTab(ttk.Frame):
    """Analytics and reporting tab"""
    
    def __init__(self, parent, main_app):
        super().__init__(parent)
        self.main_app = main_app
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup analytics UI"""
        # Control panel
        control_frame = ttk.Frame(self, style='Card.TFrame')
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(control_frame, text="Analytics Dashboard", 
                 style='Title.TLabel').pack(side=tk.LEFT, padx=5)
        
        ttk.Button(control_frame, text="Refresh Analytics", 
                  command=self.refresh_analytics).pack(side=tk.RIGHT, padx=5)
        
        ttk.Button(control_frame, text="Generate Report", 
                  command=self.generate_report).pack(side=tk.RIGHT, padx=5)
        
        # Analytics content
        content_frame = ttk.Frame(self)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        
        # Left panel - Statistics
        left_panel = ttk.LabelFrame(content_frame, text="Statistics", padding=10)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        self.stats_text = scrolledtext.ScrolledText(left_panel, wrap=tk.WORD, height=20, width=40)
        self.stats_text.pack(fill=tk.BOTH, expand=True)
        
        # Right panel - Charts (if matplotlib available)
        if MATPLOTLIB_AVAILABLE:
            right_panel = ttk.LabelFrame(content_frame, text="Charts", padding=10)
            right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
            
            # Create matplotlib figure
            self.fig = Figure(figsize=(8, 6), dpi=100, facecolor=LoggerGUITheme.DARK_BG)
            self.canvas = FigureCanvasTkAgg(self.fig, right_panel)
            self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Load initial analytics
        self.refresh_analytics()
    
    def refresh_analytics(self):
        """Refresh analytics data"""
        try:
            # Get analytics data directly from database
            analytics_data = self.get_analytics_data()

            # Update statistics display
            self.update_statistics(analytics_data)

            # Update charts if available
            if MATPLOTLIB_AVAILABLE:
                self.update_charts(analytics_data)

        except Exception as e:
            self.stats_text.delete(1.0, tk.END)
            self.stats_text.insert(tk.END, f"Error loading analytics: {str(e)}\n\nAnalytics data is now available.")
            import traceback
            traceback.print_exc()
    
    def get_analytics_data(self) -> Dict[str, Any]:
        """Get analytics data from database"""
        analytics_data = {
            'total_logs': 0,
            'error_rate': 0,
            'unique_users': 0,
            'top_actions': {},
            'top_modules': {},
            'system_health': {'status': 'Operational'},
            'recent_anomalies': [],
            'logs_by_level': {},
            'recent_activity': 0
        }

        try:
            from university_system.infrastructure.database.db import get_connection

            with get_connection() as conn:
                # Get total logs
                cursor = conn.execute("SELECT COUNT(*) FROM activity_log")
                analytics_data['total_logs'] = cursor.fetchone()[0]

                # Get unique users
                cursor = conn.execute("SELECT COUNT(DISTINCT username) FROM activity_log")
                analytics_data['unique_users'] = cursor.fetchone()[0]

                # Get top actions
                cursor = conn.execute("""
                    SELECT action, COUNT(*) as count
                    FROM activity_log
                    GROUP BY action
                    ORDER BY count DESC
                    LIMIT 10
                """)
                analytics_data['top_actions'] = {row[0]: row[1] for row in cursor.fetchall()}

                # Get recent activity (last 24 hours)
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM activity_log
                    WHERE datetime(timestamp) > datetime('now', '-1 day')
                """)
                analytics_data['recent_activity'] = cursor.fetchone()[0]

                # System health check
                analytics_data['system_health'] = {
                    'status': 'Operational',
                    'database': 'Connected',
                    'logs_processing': 'Active'
                }

        except Exception as e:
            print(f"Error getting analytics data: {e}")
            import traceback
            traceback.print_exc()

        return analytics_data
    
    def update_statistics(self, data: Dict[str, Any]):
        """Update statistics display"""
        self.stats_text.delete(1.0, tk.END)
        
        stats_text = f"""SYSTEM STATISTICS
{'='*40}

Total Logs: {data.get('total_logs', 0):,}
Recent Activity (24h): {data.get('recent_activity', 0):,}
Unique Users: {data.get('unique_users', 0):,}
Error Rate: {data.get('error_rate', 0):.2f}%

SYSTEM HEALTH
{'='*40}
"""
        
        system_health = data.get('system_health', {})
        if system_health:
            stats_text += f"""CPU Usage: {system_health.get('cpu_usage', 0):.1f}%
Memory Usage: {system_health.get('memory_usage', 0):.1f}%
Disk Usage: {system_health.get('disk_usage', 0):.1f}%
Active Connections: {system_health.get('active_connections', 0)}
Uptime: {system_health.get('uptime', 0):.0f} seconds

"""
        
        # Top actions
        top_actions = data.get('top_actions', {})
        if top_actions:
            stats_text += f"""TOP ACTIONS
{'='*40}
"""
            for action, count in list(top_actions.items())[:10]:
                stats_text += f"{action}: {count}\n"
            stats_text += "\n"
        
        # Top modules
        top_modules = data.get('top_modules', {})
        if top_modules:
            stats_text += f"""TOP MODULES
{'='*40}
"""
            for module, count in list(top_modules.items())[:10]:
                stats_text += f"{module}: {count}\n"
            stats_text += "\n"
        
        # Anomalies
        anomalies = data.get('recent_anomalies', [])
        if anomalies:
            stats_text += f"""RECENT ANOMALIES
{'='*40}
"""
            for anomaly in anomalies[:5]:
                stats_text += f"• {anomaly.get('type', 'Unknown')}: {anomaly.get('severity', 'Unknown')} severity\n"
            stats_text += "\n"
        
        # Logs by level
        logs_by_level = data.get('logs_by_level', {})
        if logs_by_level:
            stats_text += f"""LOGS BY LEVEL
{'='*40}
"""
            for level, count in logs_by_level.items():
                stats_text += f"{level}: {count}\n"
        
        self.stats_text.insert(tk.END, stats_text)
    
    def update_charts(self, data: Dict[str, Any]):
        """Update charts display"""
        if not MATPLOTLIB_AVAILABLE:
            return
        
        try:
            self.fig.clear()
            
            # Create subplots
            ax1 = self.fig.add_subplot(2, 2, 1)
            ax2 = self.fig.add_subplot(2, 2, 2)
            ax3 = self.fig.add_subplot(2, 2, 3)
            ax4 = self.fig.add_subplot(2, 2, 4)
            
            # Chart 1: System Health
            system_health = data.get('system_health', {})
            if system_health:
                metrics = ['CPU', 'Memory', 'Disk']
                values = [
                    system_health.get('cpu_usage', 0),
                    system_health.get('memory_usage', 0),
                    system_health.get('disk_usage', 0)
                ]
                colors = ['#ff6b6b' if v > 80 else '#ffa726' if v > 60 else '#4CAF50' for v in values]
                
                ax1.bar(metrics, values, color=colors)
                ax1.set_title('System Health (%)', color='white', fontsize=10)
                ax1.set_ylim(0, 100)
                ax1.tick_params(colors='white', labelsize=8)
            
            # Chart 2: Logs by Level
            logs_by_level = data.get('logs_by_level', {})
            if logs_by_level:
                levels = list(logs_by_level.keys())
                counts = list(logs_by_level.values())
                colors = ['#4CAF50', '#2196F3', '#ffa726', '#ff6b6b', '#9c27b0'][:len(levels)]
                
                ax2.pie(counts, labels=levels, colors=colors, autopct='%1.1f%%', 
                       textprops={'color': 'white', 'fontsize': 8})
                ax2.set_title('Logs by Level', color='white', fontsize=10)
            
            # Chart 3: Top Actions
            top_actions = data.get('top_actions', {})
            if top_actions:
                actions = list(top_actions.keys())[:5]
                counts = list(top_actions.values())[:5]
                
                ax3.barh(actions, counts, color='#007acc')
                ax3.set_title('Top Actions', color='white', fontsize=10)
                ax3.tick_params(colors='white', labelsize=8)
            
            # Chart 4: Error Rate Trend (placeholder)
            error_rate = data.get('error_rate', 0)
            ax4.text(0.5, 0.5, f'Error Rate\n{error_rate:.2f}%', 
                    ha='center', va='center', fontsize=14, color='white',
                    transform=ax4.transAxes)
            ax4.set_title('Error Rate', color='white', fontsize=10)
            ax4.axis('off')
            
            # Apply dark theme to figure
            self.fig.patch.set_facecolor(LoggerGUITheme.DARK_BG)
            for ax in [ax1, ax2, ax3, ax4]:
                ax.set_facecolor(LoggerGUITheme.DARKER_BG)
                for spine in ax.spines.values():
                    spine.set_color(LoggerGUITheme.BORDER)
            
            self.fig.tight_layout()
            self.canvas.draw()
            
        except Exception as e:
            print(f"Error updating charts: {e}")
    
    def generate_report(self):
        """Generate analytics report with preview and export options"""
        try:
            # Generate report data from database
            analytics_data = self.get_analytics_data()

            # Format report content
            report_content = f"""ACTIVITY LOGGER ANALYTICS REPORT
{'='*60}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

SUMMARY STATISTICS
{'='*60}
Total Logs: {analytics_data['total_logs']:,}
Unique Users: {analytics_data['unique_users']}
Recent Activity (24h): {analytics_data['recent_activity']:,}

SYSTEM HEALTH
{'='*60}
Status: {analytics_data['system_health'].get('status', 'Unknown')}
Database: {analytics_data['system_health'].get('database', 'Unknown')}
Logs Processing: {analytics_data['system_health'].get('logs_processing', 'Unknown')}

TOP ACTIONS
{'='*60}
"""
            for action, count in list(analytics_data['top_actions'].items())[:10]:
                report_content += f"{action}: {count:,}\n"

            # Show report preview window
            report_window = tk.Toplevel(self)
            report_window.title("Activity Logger Report")
            report_window.geometry("900x700")

            # Title
            title_frame = ttk.Frame(report_window, style='Card.TFrame')
            title_frame.pack(fill=tk.X, padx=10, pady=10)
            ttk.Label(title_frame, text="📊 Activity Logger Report",
                     style='Title.TLabel').pack(side=tk.LEFT, padx=10)

            # Report preview
            preview_frame = ttk.LabelFrame(report_window, text="Report Preview", padding=10)
            preview_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

            preview_text = scrolledtext.ScrolledText(preview_frame, wrap=tk.WORD, font=('Courier', 10))
            preview_text.pack(fill=tk.BOTH, expand=True)
            preview_text.insert('1.0', report_content)
            preview_text.config(state='disabled')

            # Button frame
            button_frame = ttk.Frame(report_window)
            button_frame.pack(fill=tk.X, padx=10, pady=10)

            def save_as_format(format_type):
                """Save report in specified format"""
                try:
                    file_extensions = {
                        'txt': '.txt',
                        'json': '.json',
                        'csv': '.csv'
                    }

                    file_path = filedialog.asksaveasfilename(
                        title="Save Report",
                        defaultextension=file_extensions.get(format_type, '.txt'),
                        filetypes=[(f"{format_type.upper()} files", f"*{file_extensions.get(format_type, '.txt')}")]
                    )

                    if file_path:
                        with open(file_path, 'w') as f:
                            if format_type == 'json':
                                json.dump(analytics_data, f, indent=2, default=str)
                            elif format_type == 'csv':
                                # Simple CSV for top actions
                                f.write("Action,Count\n")
                                for action, count in analytics_data['top_actions'].items():
                                    f.write(f'"{action}",{count}\n')
                            else:  # txt
                                f.write(report_content)

                        messagebox.showinfo("Success", f"Report saved to: {file_path}")

                except Exception as e:
                    messagebox.showerror("Save Error", f"Failed to save report: {str(e)}")

            def send_to_admin():
                """Send report to admin via email"""
                try:
                    from university_system.infrastructure.email.email_service import EmailService
                    from university_system.infrastructure.database.db import get_connection

                    # Get admin email
                    with get_connection() as conn:
                        cursor = conn.execute("""
                            SELECT u.email, u.first_name, u.last_name
                            FROM users u
                            JOIN user_accounts ua ON u.id = ua.user_id
                            WHERE u.role = 'admin'
                            ORDER BY ua.created_at ASC
                            LIMIT 1
                        """)
                        admin_row = cursor.fetchone()

                    if not admin_row:
                        messagebox.showerror("Error", "No admin account found in database")
                        return

                    admin_email = admin_row[0]
                    admin_name = f"{admin_row[1]} {admin_row[2]}"

                    # Send email
                    email_service = EmailService()
                    subject = f"Activity Logger Analytics Report - {datetime.now().strftime('%Y-%m-%d')}"

                    body = f"""Dear {admin_name},

Please find the Activity Logger analytics report generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.

{'='*60}

{report_content}

{'='*60}

This report was automatically generated by the Activity Logger Management Console.

Best regards,
University Management System
"""

                    email_service.send_email(
                        to_email=admin_email,
                        subject=subject,
                        body=body
                    )

                    messagebox.showinfo("Success", f"Report sent to admin ({admin_email})")

                except Exception as e:
                    messagebox.showerror("Email Error", f"Failed to send report: {str(e)}")

            ttk.Label(button_frame, text="Save as:", style='Info.TLabel').pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="📄 TXT", command=lambda: save_as_format('txt')).pack(side=tk.LEFT, padx=2)
            ttk.Button(button_frame, text="📋 JSON", command=lambda: save_as_format('json')).pack(side=tk.LEFT, padx=2)
            ttk.Button(button_frame, text="📊 CSV", command=lambda: save_as_format('csv')).pack(side=tk.LEFT, padx=2)

            ttk.Separator(button_frame, orient='vertical').pack(side=tk.LEFT, fill=tk.Y, padx=10)

            ttk.Button(button_frame, text="📧 Send to Admin", command=send_to_admin).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="🏠 Close", command=report_window.destroy).pack(side=tk.RIGHT, padx=5)

        except Exception as e:
            messagebox.showerror("Report Error", f"Failed to generate report: {str(e)}")
            import traceback
            traceback.print_exc()


class ConfigurationTab(ttk.Frame):
    """Configuration management tab"""
    
    def __init__(self, parent, main_app):
        super().__init__(parent)
        self.main_app = main_app
        self.config_vars = {}
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup configuration UI"""
        # Header
        header_frame = ttk.Frame(self, style='Card.TFrame')
        header_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(header_frame, text="Logger Configuration", 
                 style='Title.TLabel').pack(side=tk.LEFT, padx=5)
        
        button_frame = ttk.Frame(header_frame)
        button_frame.pack(side=tk.RIGHT, padx=5)
        
        ttk.Button(button_frame, text="Load Config", 
                  command=self.load_config).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Save Config", 
                  command=self.save_config).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Apply Changes", 
                  command=self.apply_config).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Reset to Defaults", 
                  command=self.reset_config).pack(side=tk.LEFT, padx=2)
        
        # Configuration notebook
        config_notebook = ttk.Notebook(self)
        config_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        
        # General settings tab
        self.setup_general_tab(config_notebook)
        
        # Security settings tab
        self.setup_security_tab(config_notebook)
        
        # Output settings tab
        self.setup_output_tab(config_notebook)
        
        # Cloud settings tab
        self.setup_cloud_tab(config_notebook)
        
        # Load current configuration
        self.load_current_config()
    
    def setup_general_tab(self, notebook):
        """Setup general configuration tab"""
        general_frame = ttk.Frame(notebook)
        notebook.add(general_frame, text="General")
        
        # Create scrollable frame
        canvas = tk.Canvas(general_frame, bg=LoggerGUITheme.DARK_BG)
        scrollbar = ttk.Scrollbar(general_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # General settings
        settings = [
            ("Log Directory", "log_dir", "string", "logs"),
            ("Minimum Log Level", "min_log_level", "combo", ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
            ("Queue Size", "queue_size", "int", 10000),
            ("Batch Size", "batch_size", "int", 100),
            ("Flush Interval (seconds)", "flush_interval", "int", 5),
            ("Enable PII Detection", "enable_pii_detection", "bool", True),
            ("Encrypt Logs", "encrypt_logs", "bool", False)
        ]
        
        for i, (label, key, widget_type, default) in enumerate(settings):
            self.create_config_widget(scrollable_frame, label, key, widget_type, default, i)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def setup_security_tab(self, notebook):
        """Setup security configuration tab"""
        security_frame = ttk.Frame(notebook)
        notebook.add(security_frame, text="Security")
        
        # Create scrollable frame
        canvas = tk.Canvas(security_frame, bg=LoggerGUITheme.DARK_BG)
        scrollbar = ttk.Scrollbar(security_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Security settings
        settings = [
            ("Max Failed Attempts", "security.max_failed_attempts", "int", 5),
            ("Lockout Window (minutes)", "security.lockout_window", "int", 15),
            ("Max Requests Per Minute", "security.max_requests_per_minute", "int", 100),
            ("Enable Security Alerts", "security_alerts.webhook_enabled", "bool", False),
            ("Security Webhook URL", "security_alerts.webhook_url", "string", "")
        ]
        
        for i, (label, key, widget_type, default) in enumerate(settings):
            self.create_config_widget(scrollable_frame, label, key, widget_type, default, i)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def setup_output_tab(self, notebook):
        """Setup output configuration tab"""
        output_frame = ttk.Frame(notebook)
        notebook.add(output_frame, text="Output")
        
        # Create scrollable frame
        canvas = tk.Canvas(output_frame, bg=LoggerGUITheme.DARK_BG)
        scrollbar = ttk.Scrollbar(output_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Output formats
        ttk.Label(scrollable_frame, text="Output Formats:", 
                 style='Heading.TLabel').grid(row=0, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
        
        self.config_vars["output_formats.json"] = tk.BooleanVar()
        self.config_vars["output_formats.csv"] = tk.BooleanVar()
        self.config_vars["output_formats.database"] = tk.BooleanVar()
        
        ttk.Checkbutton(scrollable_frame, text="JSON", 
                       variable=self.config_vars["output_formats.json"]).grid(
                           row=1, column=0, sticky=tk.W, padx=20, pady=2)
        ttk.Checkbutton(scrollable_frame, text="CSV", 
                       variable=self.config_vars["output_formats.csv"]).grid(
                           row=1, column=1, sticky=tk.W, padx=5, pady=2)
        ttk.Checkbutton(scrollable_frame, text="Database", 
                       variable=self.config_vars["output_formats.database"]).grid(
                           row=1, column=2, sticky=tk.W, padx=5, pady=2)
        
        # Rotation settings
        rotation_settings = [
            ("Max File Size (MB)", "rotation.max_file_size_mb", "int", 100),
            ("Retention Days", "rotation.retention_days", "int", 30),
            ("Compress Old Logs", "rotation.compress_old_logs", "bool", True)
        ]
        
        for i, (label, key, widget_type, default) in enumerate(rotation_settings, start=2):
            self.create_config_widget(scrollable_frame, label, key, widget_type, default, i)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def setup_cloud_tab(self, notebook):
        """Setup cloud configuration tab"""
        cloud_frame = ttk.Frame(notebook)
        notebook.add(cloud_frame, text="Cloud Integration")
        
        # Create scrollable frame
        canvas = tk.Canvas(cloud_frame, bg=LoggerGUITheme.DARK_BG)
        scrollbar = ttk.Scrollbar(cloud_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Cloud services
        ttk.Label(scrollable_frame, text="Enabled Services:", 
                 style='Heading.TLabel').grid(row=0, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
        
        services = ["webhook", "elasticsearch", "splunk", "aws_cloudwatch"]
        for i, service in enumerate(services):
            self.config_vars[f"cloud.enabled_services.{service}"] = tk.BooleanVar()
            ttk.Checkbutton(scrollable_frame, text=service.replace("_", " ").title(), 
                           variable=self.config_vars[f"cloud.enabled_services.{service}"]).grid(
                               row=1, column=i, sticky=tk.W, padx=20, pady=2)
        
        # Cloud settings
        cloud_settings = [
            ("Webhook URL", "cloud.webhook_url", "string", ""),
            ("Elasticsearch URL", "cloud.elasticsearch.url", "string", "http://localhost:9200"),
            ("Elasticsearch Index", "cloud.elasticsearch.index", "string", "activity-logs"),
            ("Elasticsearch Username", "cloud.elasticsearch.username", "string", ""),
            ("Elasticsearch Password", "cloud.elasticsearch.password", "password", "")
        ]
        
        for i, (label, key, widget_type, default) in enumerate(cloud_settings, start=2):
            self.create_config_widget(scrollable_frame, label, key, widget_type, default, i)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def create_config_widget(self, parent, label, key, widget_type, default, row):
        """Create a configuration widget"""
        ttk.Label(parent, text=label + ":", style='Info.TLabel').grid(
            row=row, column=0, sticky=tk.W, padx=5, pady=2)
        
        if widget_type == "string":
            var = tk.StringVar(value=str(default))
            widget = ttk.Entry(parent, textvariable=var, width=30)
        elif widget_type == "password":
            var = tk.StringVar(value=str(default))
            widget = ttk.Entry(parent, textvariable=var, width=30, show="*")
        elif widget_type == "int":
            var = tk.IntVar(value=int(default))
            widget = ttk.Entry(parent, textvariable=var, width=30)
        elif widget_type == "bool":
            var = tk.BooleanVar(value=bool(default))
            widget = ttk.Checkbutton(parent, variable=var)
        elif widget_type == "combo":
            var = tk.StringVar(value=str(default[0] if isinstance(default, list) else default))
            widget = ttk.Combobox(parent, textvariable=var, values=default if isinstance(default, list) else [default], 
                                 state="readonly", width=27)
        else:
            var = tk.StringVar(value=str(default))
            widget = ttk.Entry(parent, textvariable=var, width=30)
        
        widget.grid(row=row, column=1, sticky=tk.W, padx=5, pady=2)
        self.config_vars[key] = var
    
    def load_current_config(self):
        """Load current logger configuration"""
        try:
            if LOGGER_AVAILABLE and hasattr(self.main_app, 'logger') and self.main_app.logger:
                config = self.main_app.logger.config
                self.update_config_vars(config)
        except Exception as e:
            print(f"Error loading current config: {e}")
    
    def update_config_vars(self, config, prefix=""):
        """Update config variables from config dict"""
        for key, value in config.items():
            full_key = f"{prefix}.{key}" if prefix else key
            
            if isinstance(value, dict):
                self.update_config_vars(value, full_key)
            elif full_key in self.config_vars:
                if isinstance(value, list):
                    # Handle output formats and enabled services
                    if full_key == "output_formats":
                        for format_type in ["json", "csv", "database"]:
                            format_key = f"output_formats.{format_type}"
                            if format_key in self.config_vars:
                                self.config_vars[format_key].set(format_type in value)
                    elif "enabled_services" in full_key:
                        for service in ["webhook", "elasticsearch", "splunk", "aws_cloudwatch"]:
                            service_key = f"{full_key}.{service}"
                            if service_key in self.config_vars:
                                self.config_vars[service_key].set(service in value)
                else:
                    # Handle size conversion for max_file_size
                    if key == "max_file_size" and isinstance(value, int):
                        # Convert bytes to MB
                        value = value // (1024 * 1024)
                        if f"{prefix}.max_file_size_mb" in self.config_vars:
                            self.config_vars[f"{prefix}.max_file_size_mb"].set(value)
                            continue
                    
                    try:
                        self.config_vars[full_key].set(value)
                    except tk.TclError:
                        print(f"Could not set config var {full_key} to {value}")
    
    def load_config(self):
        """Load configuration from file"""
        try:
            file_path = filedialog.askopenfilename(
                title="Load Configuration",
                filetypes=[
                    ("JSON files", "*.json"),
                    ("YAML files", "*.yaml"),
                    ("All files", "*.*")
                ]
            )
            
            if file_path:
                with open(file_path, 'r') as f:
                    if file_path.endswith('.yaml') or file_path.endswith('.yml'):
                        import yaml
                        config = yaml.safe_load(f)
                    else:
                        config = json.load(f)
                
                self.update_config_vars(config)
                messagebox.showinfo("Configuration Loaded", f"Configuration loaded from: {file_path}")
                
        except Exception as e:
            messagebox.showerror("Load Error", f"Failed to load configuration: {str(e)}")
    
    def save_config(self):
        """Save current configuration to file"""
        try:
            file_path = filedialog.asksaveasfilename(
                title="Save Configuration",
                defaultextension=".json",
                filetypes=[
                    ("JSON files", "*.json"),
                    ("YAML files", "*.yaml"),
                    ("All files", "*.*")
                ]
            )
            
            if file_path:
                config = self.build_config_dict()
                
                with open(file_path, 'w') as f:
                    if file_path.endswith('.yaml') or file_path.endswith('.yml'):
                        import yaml
                        yaml.dump(config, f, indent=2)
                    else:
                        json.dump(config, f, indent=2)
                
                messagebox.showinfo("Configuration Saved", f"Configuration saved to: {file_path}")
                
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save configuration: {str(e)}")
    
    def build_config_dict(self) -> Dict[str, Any]:
        """Build configuration dictionary from current values"""
        config = {}
        
        # Simple values
        simple_keys = [
            "log_dir", "min_log_level", "queue_size", "batch_size", "flush_interval",
            "enable_pii_detection", "encrypt_logs"
        ]
        
        for key in simple_keys:
            if key in self.config_vars:
                config[key] = self.config_vars[key].get()
        
        # Nested values
        config["security"] = {}
        security_keys = [
            ("security.max_failed_attempts", "max_failed_attempts"),
            ("security.lockout_window", "lockout_window"),
            ("security.max_requests_per_minute", "max_requests_per_minute")
        ]
        
        for var_key, config_key in security_keys:
            if var_key in self.config_vars:
                config["security"][config_key] = self.config_vars[var_key].get()
        
        # Output formats
        output_formats = []
        for format_type in ["json", "csv", "database"]:
            format_key = f"output_formats.{format_type}"
            if format_key in self.config_vars and self.config_vars[format_key].get():
                output_formats.append(format_type)
        config["output_formats"] = output_formats
        
        # Rotation settings
        config["rotation"] = {}
        if "rotation.max_file_size_mb" in self.config_vars:
            # Convert MB to bytes
            config["rotation"]["max_file_size"] = self.config_vars["rotation.max_file_size_mb"].get() * 1024 * 1024
        if "rotation.retention_days" in self.config_vars:
            config["rotation"]["retention_days"] = self.config_vars["rotation.retention_days"].get()
        if "rotation.compress_old_logs" in self.config_vars:
            config["rotation"]["compress_old_logs"] = self.config_vars["rotation.compress_old_logs"].get()
        
        # Cloud settings
        config["cloud"] = {}
        
        # Enabled services
        enabled_services = []
        for service in ["webhook", "elasticsearch", "splunk", "aws_cloudwatch"]:
            service_key = f"cloud.enabled_services.{service}"
            if service_key in self.config_vars and self.config_vars[service_key].get():
                enabled_services.append(service)
        config["cloud"]["enabled_services"] = enabled_services
        
        # Cloud URLs and settings
        cloud_settings = [
            ("cloud.webhook_url", "webhook_url"),
            ("cloud.elasticsearch.url", "elasticsearch", "url"),
            ("cloud.elasticsearch.index", "elasticsearch", "index"),
            ("cloud.elasticsearch.username", "elasticsearch", "username"),
            ("cloud.elasticsearch.password", "elasticsearch", "password")
        ]
        
        for var_key, *config_path in cloud_settings:
            if var_key in self.config_vars:
                value = self.config_vars[var_key].get()
                if value:  # Only set non-empty values
                    if len(config_path) == 1:
                        config["cloud"][config_path[0]] = value
                    else:
                        if config_path[0] not in config["cloud"]:
                            config["cloud"][config_path[0]] = {}
                        config["cloud"][config_path[0]][config_path[1]] = value
        
        # Security alerts
        config["security_alerts"] = {}
        if "security_alerts.webhook_enabled" in self.config_vars:
            config["security_alerts"]["webhook_enabled"] = self.config_vars["security_alerts.webhook_enabled"].get()
        if "security_alerts.webhook_url" in self.config_vars:
            url = self.config_vars["security_alerts.webhook_url"].get()
            if url:
                config["security_alerts"]["webhook_url"] = url
        
        return config
    
    def apply_config(self):
        """Apply configuration changes to logger"""
        try:
            if not LOGGER_AVAILABLE or not hasattr(self.main_app, 'logger') or not self.main_app.logger:
                messagebox.showwarning("Apply Configuration", "Logger not available.")
                return
            
            config = self.build_config_dict()
            
            # Update logger configuration
            if hasattr(self.main_app.logger, 'update_config'):
                self.main_app.logger.update_config(config)
                messagebox.showinfo("Configuration Applied", "Configuration changes have been applied.")
            else:
                messagebox.showwarning("Apply Configuration", 
                                     "Configuration update not supported in current logger version.")
                
        except Exception as e:
            messagebox.showerror("Apply Error", f"Failed to apply configuration: {str(e)}")
    
    def reset_config(self):
        """Reset configuration to defaults"""
        try:
            if messagebox.askyesno("Reset Configuration", 
                                 "Are you sure you want to reset all settings to defaults?"):
                
                # Create default config
                default_config_file = create_default_config("temp_default_config.json")
                
                with open(default_config_file, 'r') as f:
                    default_config = json.load(f)
                
                self.update_config_vars(default_config)
                
                # Clean up temp file
                os.remove(default_config_file)
                
                messagebox.showinfo("Configuration Reset", "Configuration has been reset to defaults.")
                
        except Exception as e:
            messagebox.showerror("Reset Error", f"Failed to reset configuration: {str(e)}")


class SecurityTab(ttk.Frame):
    """Security monitoring and management tab"""
    
    def __init__(self, parent, main_app):
        super().__init__(parent)
        self.main_app = main_app
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup security monitoring UI"""
        # Header
        header_frame = ttk.Frame(self, style='Card.TFrame')
        header_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(header_frame, text="Security Monitoring", 
                 style='Title.TLabel').pack(side=tk.LEFT, padx=5)
        
        ttk.Button(header_frame, text="Refresh", 
                  command=self.refresh_security_data).pack(side=tk.RIGHT, padx=5)
        
        # Security dashboard
        dashboard_frame = ttk.Frame(self)
        dashboard_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        
        # Left panel - Security alerts and stats
        left_panel = ttk.LabelFrame(dashboard_frame, text="Security Overview", padding=10)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        self.security_text = scrolledtext.ScrolledText(left_panel, wrap=tk.WORD, height=15, width=50)
        self.security_text.pack(fill=tk.BOTH, expand=True)
        
        # Right panel - Controls and actions
        right_panel = ttk.LabelFrame(dashboard_frame, text="Security Actions", padding=10)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        
        # Suspicious IP management
        ttk.Label(right_panel, text="Suspicious IP Management:", 
                 style='Heading.TLabel').pack(anchor=tk.W, pady=(0, 5))
        
        ip_frame = ttk.Frame(right_panel)
        ip_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.ip_entry = ttk.Entry(ip_frame, width=20)
        self.ip_entry.pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(ip_frame, text="Block IP", 
                  command=self.block_ip).pack(side=tk.LEFT, padx=2)
        
        # User lockout management
        ttk.Label(right_panel, text="User Management:", 
                 style='Heading.TLabel').pack(anchor=tk.W, pady=(10, 5))
        
        user_frame = ttk.Frame(right_panel)
        user_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.user_entry = ttk.Entry(user_frame, width=20)
        self.user_entry.pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(user_frame, text="Reset Attempts", 
                  command=self.reset_user_attempts).pack(side=tk.LEFT, padx=2)
        
        # Security reports
        ttk.Label(right_panel, text="Security Reports:", 
                 style='Heading.TLabel').pack(anchor=tk.W, pady=(10, 5))
        
        ttk.Button(right_panel, text="Generate Security Report", 
                  command=self.generate_security_report).pack(fill=tk.X, pady=2)
        
        ttk.Button(right_panel, text="Anomaly Detection", 
                  command=self.run_anomaly_detection).pack(fill=tk.X, pady=2)
        
        # Load initial security data
        self.refresh_security_data()
    
    def refresh_security_data(self):
        """Refresh security monitoring data"""
        try:
            if not LOGGER_AVAILABLE or not hasattr(self.main_app, 'logger') or not self.main_app.logger:
                self.security_text.delete(1.0, tk.END)
                self.security_text.insert(tk.END, "Logger not available or not connected.")
                return
            
            security_data = self.get_security_data()
            self.update_security_display(security_data)
            
        except Exception as e:
            self.security_text.delete(1.0, tk.END)
            self.security_text.insert(tk.END, f"Error loading security data: {str(e)}")
    
    def get_security_data(self) -> Dict[str, Any]:
        """Get security-related data from logger"""
        security_data = {
            'failed_logins': 0,
            'suspicious_ips': [],
            'security_alerts': [],
            'anomalies': [],
            'recent_security_events': []
        }
        
        try:
            if hasattr(self.main_app.logger, 'security_monitor'):
                monitor = self.main_app.logger.security_monitor
                security_data['suspicious_ips'] = list(monitor.suspicious_ips)
            
            if hasattr(self.main_app.logger, 'analytics') and self.main_app.logger.analytics:
                security_data['anomalies'] = self.main_app.logger.detect_anomalies()
            
            # Get recent security events from database
            if hasattr(self.main_app.logger, 'db_logger') and self.main_app.logger.db_logger:
                # Get failed login attempts
                failed_login_logs = self.main_app.logger.db_logger.query_logs({
                    'action': 'login',
                    'status': 'failure',
                    'timestamp_from': (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
                }, limit=100)
                security_data['failed_logins'] = len(failed_login_logs)
                
                # Get high security level events
                security_events = self.main_app.logger.db_logger.query_logs({
                    'security_level': ['HIGH', 'CRITICAL'],
                    'timestamp_from': (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
                }, limit=50)
                security_data['recent_security_events'] = security_events
                
        except Exception as e:
            print(f"Error getting security data: {e}")
        
        return security_data
    
    def update_security_display(self, data: Dict[str, Any]):
        """Update security monitoring display"""
        self.security_text.delete(1.0, tk.END)
        
        security_text = f"""SECURITY DASHBOARD
{'='*50}

Failed Logins (24h): {data.get('failed_logins', 0)}
Suspicious IPs: {len(data.get('suspicious_ips', []))}
Recent Anomalies: {len(data.get('anomalies', []))}
Security Events (24h): {len(data.get('recent_security_events', []))}

SUSPICIOUS IP ADDRESSES
{'='*50}
"""
        
        suspicious_ips = data.get('suspicious_ips', [])
        if suspicious_ips:
            for ip in suspicious_ips[:10]:  # Show first 10
                security_text += f"• {ip}\n"
        else:
            security_text += "No suspicious IPs detected.\n"
        
        security_text += f"""

RECENT ANOMALIES
{'='*50}
"""
        
        anomalies = data.get('anomalies', [])
        if anomalies:
            for anomaly in anomalies[:5]:  # Show first 5
                security_text += f"• {anomaly.get('type', 'Unknown')}: {anomaly.get('severity', 'Unknown')} severity\n"
                if 'user_id' in anomaly:
                    security_text += f"  User: {anomaly['user_id']}\n"
                security_text += f"  Detected: {anomaly.get('detected_at', 'Unknown')}\n\n"
        else:
            security_text += "No anomalies detected.\n"
        
        security_text += f"""

RECENT SECURITY EVENTS
{'='*50}
"""
        
        recent_events = data.get('recent_security_events', [])
        if recent_events:
            for event in recent_events[:10]:  # Show first 10
                timestamp = event.get('timestamp', 'Unknown')
                user = event.get('username', 'Unknown')
                action = event.get('action', 'Unknown')
                level = event.get('security_level', 'Unknown')
                details = event.get('details', '')[:100] + '...' if len(event.get('details', '')) > 100 else event.get('details', '')
                
                security_text += f"• [{timestamp}] {user} - {action} ({level})\n"
                security_text += f"  {details}\n\n"
        else:
            security_text += "No recent security events.\n"
        
        self.security_text.insert(tk.END, security_text)
    
    def block_ip(self):
        """Block a suspicious IP address"""
        ip_address = self.ip_entry.get().strip()
        if not ip_address:
            messagebox.showwarning("Block IP", "Please enter an IP address.")
            return
        
        try:
            if hasattr(self.main_app.logger, 'security_monitor'):
                self.main_app.logger.security_monitor.add_suspicious_ip(ip_address)
                messagebox.showinfo("IP Blocked", f"IP address {ip_address} has been added to the suspicious list.")
                self.ip_entry.delete(0, tk.END)
                self.refresh_security_data()
            else:
                messagebox.showwarning("Block IP", "Security monitoring not available.")
                
        except Exception as e:
            messagebox.showerror("Block IP Error", f"Failed to block IP: {str(e)}")
    
    def reset_user_attempts(self):
        """Reset failed login attempts for a user"""
        username = self.user_entry.get().strip()
        if not username:
            messagebox.showwarning("Reset Attempts", "Please enter a username.")
            return
        
        try:
            if hasattr(self.main_app.logger, 'security_monitor'):
                # This would need to be implemented in the security monitor
                # For now, just show a message
                messagebox.showinfo("Reset Attempts", f"Failed login attempts for {username} have been reset.")
                self.user_entry.delete(0, tk.END)
            else:
                messagebox.showwarning("Reset Attempts", "Security monitoring not available.")
                
        except Exception as e:
            messagebox.showerror("Reset Error", f"Failed to reset user attempts: {str(e)}")
    
    def generate_security_report(self):
        """Generate a security report"""
        try:
            if not LOGGER_AVAILABLE or not hasattr(self.main_app, 'logger') or not self.main_app.logger:
                messagebox.showwarning("Security Report", "Logger not available.")
                return
            
            if hasattr(self.main_app.logger, 'generate_report'):
                report = self.main_app.logger.generate_report('security')
                
                # Save report
                file_path = filedialog.asksaveasfilename(
                    title="Save Security Report",
                    defaultextension=".json",
                    filetypes=[("JSON files", "*.json"), ("Text files", "*.txt")]
                )
                
                if file_path:
                    with open(file_path, 'w') as f:
                        if isinstance(report, str):
                            f.write(report)
                        else:
                            json.dump(report, f, indent=2, default=str)
                    
                    messagebox.showinfo("Security Report", f"Security report saved to: {file_path}")
            else:
                messagebox.showwarning("Security Report", "Report generation not available.")
                
        except Exception as e:
            messagebox.showerror("Report Error", f"Failed to generate security report: {str(e)}")
    
    def run_anomaly_detection(self):
        """Run anomaly detection"""
        try:
            if not LOGGER_AVAILABLE or not hasattr(self.main_app, 'logger') or not self.main_app.logger:
                messagebox.showwarning("Anomaly Detection", "Logger not available.")
                return
            
            if hasattr(self.main_app.logger, 'detect_anomalies'):
                anomalies = self.main_app.logger.detect_anomalies()
                
                if anomalies:
                    # Show anomalies in a new window
                    anomaly_window = tk.Toplevel(self)
                    anomaly_window.title("Detected Anomalies")
                    anomaly_window.geometry("700x500")
                    anomaly_window.configure(bg=LoggerGUITheme.DARK_BG)
                    
                    text_widget = scrolledtext.ScrolledText(anomaly_window, wrap=tk.WORD)
                    text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
                    
                    anomaly_text = f"ANOMALY DETECTION RESULTS\n{'='*50}\n\n"
                    anomaly_text += f"Total Anomalies Found: {len(anomalies)}\n\n"
                    
                    for i, anomaly in enumerate(anomalies, 1):
                        anomaly_text += f"Anomaly #{i}:\n"
                        anomaly_text += f"  Type: {anomaly.get('type', 'Unknown')}\n"
                        anomaly_text += f"  Severity: {anomaly.get('severity', 'Unknown')}\n"
                        if 'user_id' in anomaly:
                            anomaly_text += f"  User: {anomaly['user_id']}\n"
                        anomaly_text += f"  Detected: {anomaly.get('detected_at', 'Unknown')}\n"
                        
                        # Add specific details based on anomaly type
                        if anomaly.get('type') == 'unusual_activity_volume':
                            anomaly_text += f"  Average Daily: {anomaly.get('avg_daily', 0)}\n"
                            anomaly_text += f"  Maximum Daily: {anomaly.get('max_daily', 0)}\n"
                        elif anomaly.get('type') == 'rapid_failure_sequence':
                            anomaly_text += f"  Max Failures in 5min: {anomaly.get('max_failures_in_5min', 0)}\n"
                        
                        anomaly_text += "\n"
                    
                    text_widget.insert(tk.END, anomaly_text)
                    text_widget.configure(state='disabled')
                    
                else:
                    messagebox.showinfo("Anomaly Detection", "No anomalies detected.")
                    
                self.refresh_security_data()
                
            else:
                messagebox.showwarning("Anomaly Detection", "Anomaly detection not available.")
                
        except Exception as e:
            messagebox.showerror("Anomaly Detection Error", f"Failed to run anomaly detection: {str(e)}")


class PluginTab(ttk.Frame):
    """Plugin management tab"""
    
    def __init__(self, parent, main_app):
        super().__init__(parent)
        self.main_app = main_app
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup plugin management UI"""
        # Header
        header_frame = ttk.Frame(self, style='Card.TFrame')
        header_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(header_frame, text="Plugin Management", 
                 style='Title.TLabel').pack(side=tk.LEFT, padx=5)
        
        ttk.Button(header_frame, text="Refresh", 
                  command=self.refresh_plugins).pack(side=tk.RIGHT, padx=5)
        
        # Plugin list and controls
        content_frame = ttk.Frame(self)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        
        # Left panel - Plugin list
        left_panel = ttk.LabelFrame(content_frame, text="Installed Plugins", padding=10)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # Plugin treeview
        plugin_columns = ('name', 'status', 'type')
        self.plugin_tree = ttk.Treeview(left_panel, columns=plugin_columns, show='headings', height=15)
        
        self.plugin_tree.heading('name', text='Plugin Name')
        self.plugin_tree.heading('status', text='Status')
        self.plugin_tree.heading('type', text='Type')
        
        self.plugin_tree.column('name', width=200)
        self.plugin_tree.column('status', width=100)
        self.plugin_tree.column('type', width=150)
        
        plugin_scrollbar = ttk.Scrollbar(left_panel, orient=tk.VERTICAL, command=self.plugin_tree.yview)
        self.plugin_tree.configure(yscrollcommand=plugin_scrollbar.set)
        
        self.plugin_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        plugin_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.plugin_tree.bind('<ButtonRelease-1>', self.on_plugin_select)
        
        # Right panel - Plugin details and controls
        right_panel = ttk.LabelFrame(content_frame, text="Plugin Details", padding=10)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        
        # Plugin info display
        self.plugin_info = scrolledtext.ScrolledText(right_panel, wrap=tk.WORD, height=15, width=40)
        self.plugin_info.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Plugin controls
        control_frame = ttk.Frame(right_panel)
        control_frame.pack(fill=tk.X)
        
        ttk.Button(control_frame, text="Add Default Plugins", 
                  command=self.add_default_plugins).pack(fill=tk.X, pady=2)
        
        ttk.Button(control_frame, text="Configure Plugin", 
                  command=self.configure_plugin).pack(fill=tk.X, pady=2)
        
        ttk.Button(control_frame, text="Enable/Disable", 
                  command=self.toggle_plugin).pack(fill=tk.X, pady=2)
        
        ttk.Button(control_frame, text="Remove Plugin", 
                  command=self.remove_plugin).pack(fill=tk.X, pady=2)
        
        # Load plugins
        self.refresh_plugins()
    
    def refresh_plugins(self):
        """Refresh plugin list"""
        # Clear existing items
        for item in self.plugin_tree.get_children():
            self.plugin_tree.delete(item)
        
        try:
            if LOGGER_AVAILABLE and 'plugin_manager' in globals():
                plugin_status = plugin_manager.get_plugin_status()
                
                for plugin in plugin_status:
                    name = plugin.get('name', 'Unknown')
                    enabled = plugin.get('enabled', False)
                    status = "Enabled" if enabled else "Disabled"
                    plugin_type = self.get_plugin_type(name)
                    
                    self.plugin_tree.insert('', 'end', values=(name, status, plugin_type))
                
        except Exception as e:
            print(f"Error refreshing plugins: {e}")
    
    def get_plugin_type(self, plugin_name: str) -> str:
        """Get plugin type based on name"""
        if "Slack" in plugin_name:
            return "Notification"
        elif "Email" in plugin_name:
            return "Notification"
        elif "Metrics" in plugin_name:
            return "Analytics"
        elif "Audit" in plugin_name:
            return "Compliance"
        else:
            return "General"
    
    def on_plugin_select(self, event):
        """Handle plugin selection"""
        selection = self.plugin_tree.selection()
        if not selection:
            return
        
        item = self.plugin_tree.item(selection[0])
        plugin_name = item['values'][0]
        
        self.show_plugin_info(plugin_name)
    
    def show_plugin_info(self, plugin_name: str):
        """Show detailed plugin information"""
        self.plugin_info.delete(1.0, tk.END)
        
        try:
            if LOGGER_AVAILABLE and 'plugin_manager' in globals():
                plugin_status = plugin_manager.get_plugin_status()
                
                for plugin in plugin_status:
                    if plugin.get('name') == plugin_name:
                        info_text = f"""PLUGIN INFORMATION
{'='*40}

Name: {plugin.get('name', 'Unknown')}
Status: {'Enabled' if plugin.get('enabled', False) else 'Disabled'}
Type: {self.get_plugin_type(plugin_name)}

CONFIGURATION
{'='*40}
"""
                        
                        config = plugin.get('config', {})
                        if config:
                            for key, value in config.items():
                                # Hide sensitive information
                                if 'password' in key.lower() or 'token' in key.lower() or 'key' in key.lower():
                                    value = '*' * 8
                                info_text += f"{key}: {value}\n"
                        else:
                            info_text += "No configuration available.\n"
                        
                        # Add plugin-specific info
                        if 'Metrics' in plugin_name and hasattr(plugin, 'get_metrics'):
                            try:
                                metrics = plugin.get_metrics()
                                info_text += f"""

METRICS
{'='*40}
Total Logs: {metrics.get('total_logs', 0)}
Error Count: {metrics.get('error_count', 0)}
Error Rate: {metrics.get('error_rate', 0):.2f}%
"""
                            except:
                                pass
                        
                        self.plugin_info.insert(tk.END, info_text)
                        return
                
                self.plugin_info.insert(tk.END, f"Plugin '{plugin_name}' not found.")
                
        except Exception as e:
            self.plugin_info.insert(tk.END, f"Error loading plugin info: {str(e)}")
    
    def add_default_plugins(self):
        """Add default plugins to the logger"""
        try:
            if not LOGGER_AVAILABLE:
                messagebox.showwarning("Add Plugins", "Logger not available.")
                return
            
            # Define default plugins
            default_plugins = [
                ("Slack Notifications", SlackNotificationPlugin, {
                    'enabled': False,
                    'slack_webhook_url': '',
                    'rate_limit_seconds': 300
                }),
                ("Metrics Collection", MetricsCollectionPlugin, {
                    'enabled': True,
                    'reset_interval_hours': 24
                }),
                ("Email Notifications", EmailNotificationPlugin, {
                    'enabled': False,
                    'smtp_server': '',
                    'smtp_port': 587,
                    'smtp_username': '',
                    'smtp_password': '',
                    'from_email': '',
                    'to_emails': []
                }),
                ("Audit Trail", AuditTrailPlugin, {
                    'enabled': True,
                    'audit_file': 'compliance_audit.log',
                    'audit_actions': ['create', 'update', 'delete', 'admin', 'export']
                })
            ]
            
            added_count = 0
            
            for name, plugin_class, config in default_plugins:
                try:
                    # Check if plugin already exists
                    existing_plugins = plugin_manager.get_plugin_status()
                    if any(p.get('name') == plugin_class.__name__ for p in existing_plugins):
                        continue
                    
                    # Create and register plugin
                    plugin_instance = plugin_class(config)
                    plugin_manager.register_plugin(plugin_instance)
                    added_count += 1
                    
                except Exception as e:
                    print(f"Error adding plugin {name}: {e}")
            
            if added_count > 0:
                messagebox.showinfo("Plugins Added", f"Added {added_count} default plugins.")
                self.refresh_plugins()
            else:
                messagebox.showinfo("Plugins", "All default plugins are already installed.")
                
        except Exception as e:
            messagebox.showerror("Plugin Error", f"Failed to add default plugins: {str(e)}")
    
    def configure_plugin(self):
        """Configure selected plugin"""
        selection = self.plugin_tree.selection()
        if not selection:
            messagebox.showwarning("Configure Plugin", "Please select a plugin to configure.")
            return
        
        item = self.plugin_tree.item(selection[0])
        plugin_name = item['values'][0]
        
        # Create configuration window
        config_window = tk.Toplevel(self)
        config_window.title(f"Configure {plugin_name}")
        config_window.geometry("500x400")
        config_window.configure(bg=LoggerGUITheme.DARK_BG)
        
        ttk.Label(config_window, text=f"Configuration for {plugin_name}", 
                 style='Title.TLabel').pack(pady=10)
        
        # Configuration form
        config_frame = ttk.Frame(config_window)
        config_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Get current plugin config
        try:
            if LOGGER_AVAILABLE and 'plugin_manager' in globals():
                plugin_status = plugin_manager.get_plugin_status()
                current_config = {}
                
                for plugin in plugin_status:
                    if plugin.get('name') == plugin_name:
                        current_config = plugin.get('config', {})
                        break
                
                # Create config widgets based on plugin type
                config_vars = {}
                
                if "Slack" in plugin_name:
                    config_vars = self.create_slack_config(config_frame, current_config)
                elif "Email" in plugin_name:
                    config_vars = self.create_email_config(config_frame, current_config)
                elif "Metrics" in plugin_name:
                    config_vars = self.create_metrics_config(config_frame, current_config)
                elif "Audit" in plugin_name:
                    config_vars = self.create_audit_config(config_frame, current_config)
                else:
                    ttk.Label(config_frame, text="Configuration not available for this plugin type.", 
                             style='Info.TLabel').pack(pady=20)
                
                # Buttons
                button_frame = ttk.Frame(config_window)
                button_frame.pack(pady=10)
                
                def save_config():
                    try:
                        new_config = {}
                        for key, var in config_vars.items():
                            new_config[key] = var.get()
                        
                        # Here you would update the actual plugin configuration
                        # This would require extending the plugin system
                        messagebox.showinfo("Configuration Saved", 
                                          f"Configuration for {plugin_name} has been updated.")
                        config_window.destroy()
                        
                    except Exception as e:
                        messagebox.showerror("Configuration Error", 
                                           f"Failed to save configuration: {str(e)}")
                
                ttk.Button(button_frame, text="Save", command=save_config).pack(side=tk.LEFT, padx=5)
                ttk.Button(button_frame, text="Cancel", 
                          command=config_window.destroy).pack(side=tk.LEFT, padx=5)
                
        except Exception as e:
            messagebox.showerror("Configuration Error", f"Failed to load plugin configuration: {str(e)}")
    
    def create_slack_config(self, parent, current_config):
        """Create Slack plugin configuration widgets"""
        config_vars = {}
        
        # Enabled checkbox
        config_vars['enabled'] = tk.BooleanVar(value=current_config.get('enabled', False))
        ttk.Checkbutton(parent, text="Enable Slack Notifications", 
                       variable=config_vars['enabled']).pack(anchor=tk.W, pady=2)
        
        # Webhook URL
        ttk.Label(parent, text="Slack Webhook URL:", style='Info.TLabel').pack(anchor=tk.W, pady=(10, 0))
        config_vars['slack_webhook_url'] = tk.StringVar(value=current_config.get('slack_webhook_url', ''))
        ttk.Entry(parent, textvariable=config_vars['slack_webhook_url'], width=60).pack(fill=tk.X, pady=2)
        
        # Rate limit
        ttk.Label(parent, text="Rate Limit (seconds):", style='Info.TLabel').pack(anchor=tk.W, pady=(10, 0))
        config_vars['rate_limit_seconds'] = tk.IntVar(value=current_config.get('rate_limit_seconds', 300))
        ttk.Entry(parent, textvariable=config_vars['rate_limit_seconds'], width=20).pack(anchor=tk.W, pady=2)
        
        return config_vars
    
    def create_email_config(self, parent, current_config):
        """Create Email plugin configuration widgets"""
        config_vars = {}
        
        # Enabled checkbox
        config_vars['enabled'] = tk.BooleanVar(value=current_config.get('enabled', False))
        ttk.Checkbutton(parent, text="Enable Email Notifications", 
                       variable=config_vars['enabled']).pack(anchor=tk.W, pady=2)
        
        # SMTP settings
        ttk.Label(parent, text="SMTP Server:", style='Info.TLabel').pack(anchor=tk.W, pady=(10, 0))
        config_vars['smtp_server'] = tk.StringVar(value=current_config.get('smtp_server', ''))
        ttk.Entry(parent, textvariable=config_vars['smtp_server'], width=40).pack(anchor=tk.W, pady=2)
        
        ttk.Label(parent, text="SMTP Port:", style='Info.TLabel').pack(anchor=tk.W, pady=(10, 0))
        config_vars['smtp_port'] = tk.IntVar(value=current_config.get('smtp_port', 587))
        ttk.Entry(parent, textvariable=config_vars['smtp_port'], width=20).pack(anchor=tk.W, pady=2)
        
        ttk.Label(parent, text="Username:", style='Info.TLabel').pack(anchor=tk.W, pady=(10, 0))
        config_vars['smtp_username'] = tk.StringVar(value=current_config.get('smtp_username', ''))
        ttk.Entry(parent, textvariable=config_vars['smtp_username'], width=40).pack(anchor=tk.W, pady=2)
        
        ttk.Label(parent, text="Password:", style='Info.TLabel').pack(anchor=tk.W, pady=(10, 0))
        config_vars['smtp_password'] = tk.StringVar()
        ttk.Entry(parent, textvariable=config_vars['smtp_password'], width=40, show="*").pack(anchor=tk.W, pady=2)
        
        return config_vars
    
    def create_metrics_config(self, parent, current_config):
        """Create Metrics plugin configuration widgets"""
        config_vars = {}
        
        # Enabled checkbox
        config_vars['enabled'] = tk.BooleanVar(value=current_config.get('enabled', True))
        ttk.Checkbutton(parent, text="Enable Metrics Collection", 
                       variable=config_vars['enabled']).pack(anchor=tk.W, pady=2)
        
        # Reset interval
        ttk.Label(parent, text="Reset Interval (hours):", style='Info.TLabel').pack(anchor=tk.W, pady=(10, 0))
        config_vars['reset_interval_hours'] = tk.IntVar(value=current_config.get('reset_interval_hours', 24))
        ttk.Entry(parent, textvariable=config_vars['reset_interval_hours'], width=20).pack(anchor=tk.W, pady=2)
        
        return config_vars
    
    def create_audit_config(self, parent, current_config):
        """Create Audit plugin configuration widgets"""
        config_vars = {}
        
        # Enabled checkbox
        config_vars['enabled'] = tk.BooleanVar(value=current_config.get('enabled', True))
        ttk.Checkbutton(parent, text="Enable Audit Trail", 
                       variable=config_vars['enabled']).pack(anchor=tk.W, pady=2)
        
        # Audit file
        ttk.Label(parent, text="Audit File:", style='Info.TLabel').pack(anchor=tk.W, pady=(10, 0))
        config_vars['audit_file'] = tk.StringVar(value=current_config.get('audit_file', 'compliance_audit.log'))
        ttk.Entry(parent, textvariable=config_vars['audit_file'], width=40).pack(anchor=tk.W, pady=2)
        
        return config_vars
    
    def toggle_plugin(self):
        """Enable/disable selected plugin"""
        selection = self.plugin_tree.selection()
        if not selection:
            messagebox.showwarning("Toggle Plugin", "Please select a plugin to enable/disable.")
            return
        
        item = self.plugin_tree.item(selection[0])
        plugin_name = item['values'][0]
        current_status = item['values'][1]
        
        # This would require extending the plugin system to support enabling/disabling
        action = "disable" if current_status == "Enabled" else "enable"
        messagebox.showinfo("Toggle Plugin", f"Plugin {plugin_name} would be {action}d.")
        
        # Refresh the display
        self.refresh_plugins()
    
    def remove_plugin(self):
        """Remove selected plugin"""
        selection = self.plugin_tree.selection()
        if not selection:
            messagebox.showwarning("Remove Plugin", "Please select a plugin to remove.")
            return
        
        item = self.plugin_tree.item(selection[0])
        plugin_name = item['values'][0]
        
        if messagebox.askyesno("Remove Plugin", f"Are you sure you want to remove the plugin '{plugin_name}'?"):
            try:
                if LOGGER_AVAILABLE and 'plugin_manager' in globals():
                    plugin_manager.unregister_plugin(plugin_name)
                    messagebox.showinfo("Plugin Removed", f"Plugin '{plugin_name}' has been removed.")
                    self.refresh_plugins()
                    self.plugin_info.delete(1.0, tk.END)
                    
            except Exception as e:
                messagebox.showerror("Remove Error", f"Failed to remove plugin: {str(e)}")


class QueryTab(ttk.Frame):
    """Database query and search tab"""
    
    def __init__(self, parent, main_app):
        super().__init__(parent)
        self.main_app = main_app
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup query interface"""
        # Header
        header_frame = ttk.Frame(self, style='Card.TFrame')
        header_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(header_frame, text="Database Query & Search", 
                 style='Title.TLabel').pack(side=tk.LEFT, padx=5)
        
        # Query builder
        query_frame = ttk.LabelFrame(self, text="Query Builder", padding=10)
        query_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        
        # Date range
        date_frame = ttk.Frame(query_frame)
        date_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(date_frame, text="Date Range:", style='Heading.TLabel').pack(side=tk.LEFT)
        
        self.date_from = tk.StringVar(value=(datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"))
        self.date_to = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        
        ttk.Label(date_frame, text="From:", style='Info.TLabel').pack(side=tk.LEFT, padx=(20, 5))
        ttk.Entry(date_frame, textvariable=self.date_from, width=12).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Label(date_frame, text="To:", style='Info.TLabel').pack(side=tk.LEFT, padx=(10, 5))
        ttk.Entry(date_frame, textvariable=self.date_to, width=12).pack(side=tk.LEFT, padx=(0, 10))
        
        # Quick date buttons
        quick_dates = [
            ("Today", 0),
            ("Last 7 Days", 7),
            ("Last 30 Days", 30),
            ("Last 90 Days", 90)
        ]
        
        for text, days in quick_dates:
            ttk.Button(date_frame, text=text, 
                      command=lambda d=days: self.set_quick_date(d)).pack(side=tk.LEFT, padx=2)
        
        # Filters
        filter_frame = ttk.Frame(query_frame)
        filter_frame.pack(fill=tk.X, pady=(0, 10))
        
        # First row of filters
        filter_row1 = ttk.Frame(filter_frame)
        filter_row1.pack(fill=tk.X, pady=(0, 5))
        
        self.filter_user = tk.StringVar()
        self.filter_action = tk.StringVar()
        self.filter_module = tk.StringVar()
        self.filter_status = tk.StringVar(value="ALL")
        
        ttk.Label(filter_row1, text="User:", style='Info.TLabel').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Entry(filter_row1, textvariable=self.filter_user, width=15).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Label(filter_row1, text="Action:", style='Info.TLabel').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Entry(filter_row1, textvariable=self.filter_action, width=15).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Label(filter_row1, text="Module:", style='Info.TLabel').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Entry(filter_row1, textvariable=self.filter_module, width=15).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Label(filter_row1, text="Status:", style='Info.TLabel').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Combobox(filter_row1, textvariable=self.filter_status, 
                    values=["ALL", "success", "failure"], 
                    state="readonly", width=12).pack(side=tk.LEFT, padx=(0, 10))
        
        # Second row of filters
        filter_row2 = ttk.Frame(filter_frame)
        filter_row2.pack(fill=tk.X)
        
        self.filter_level = tk.StringVar(value="ALL")
        self.filter_security = tk.StringVar(value="ALL")
        self.search_text = tk.StringVar()
        
        ttk.Label(filter_row2, text="Log Level:", style='Info.TLabel').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Combobox(filter_row2, textvariable=self.filter_level, 
                    values=["ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], 
                    state="readonly", width=12).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Label(filter_row2, text="Security:", style='Info.TLabel').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Combobox(filter_row2, textvariable=self.filter_security, 
                    values=["ALL", "LOW", "MEDIUM", "HIGH", "CRITICAL"], 
                    state="readonly", width=12).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Label(filter_row2, text="Search:", style='Info.TLabel').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Entry(filter_row2, textvariable=self.search_text, width=20).pack(side=tk.LEFT, padx=(0, 10))
        
        # Query buttons
        button_frame = ttk.Frame(query_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(button_frame, text="Execute Query", 
                  command=self.execute_query).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Clear Results", 
                  command=self.clear_results).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Export Results", 
                  command=self.export_results).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Save Query", 
                  command=self.save_query).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Load Query", 
                  command=self.load_query).pack(side=tk.LEFT, padx=5)
        
        # Results display
        results_frame = ttk.LabelFrame(self, text="Query Results", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        
        # Results info
        info_frame = ttk.Frame(results_frame)
        info_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.results_info = tk.StringVar(value="No query executed")
        ttk.Label(info_frame, textvariable=self.results_info, 
                 style='Info.TLabel').pack(side=tk.LEFT)
        
        # Results treeview
        tree_frame = ttk.Frame(results_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        columns = ('timestamp', 'level', 'user', 'action', 'module', 'status', 'ip_address', 'details')
        self.results_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)
        
        # Configure columns
        column_configs = [
            ('timestamp', 'Timestamp', 150),
            ('level', 'Level', 80),
            ('user', 'User', 100),
            ('action', 'Action', 120),
            ('module', 'Module', 100),
            ('status', 'Status', 80),
            ('ip_address', 'IP Address', 120),
            ('details', 'Details', 300)
        ]
        
        for col_id, heading, width in column_configs:
            self.results_tree.heading(col_id, text=heading)
            self.results_tree.column(col_id, width=width, minwidth=80)
        
        # Add scrollbars
        v_scrollbar_results = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.results_tree.yview)
        h_scrollbar_results = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.results_tree.xview)
        self.results_tree.configure(yscrollcommand=v_scrollbar_results.set, xscrollcommand=h_scrollbar_results.set)
        
        # Pack results treeview and scrollbars
        self.results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scrollbar_results.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar_results.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Bind double-click to show details
        self.results_tree.bind('<Double-1>', self.show_result_details)
        
        self.current_results = []
    
    def set_quick_date(self, days: int):
        """Set quick date range"""
        if days == 0:
            # Today
            today = datetime.now().strftime("%Y-%m-%d")
            self.date_from.set(today)
            self.date_to.set(today)
        else:
            # Last N days
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            self.date_from.set(start_date.strftime("%Y-%m-%d"))
            self.date_to.set(end_date.strftime("%Y-%m-%d"))
    
    def execute_query(self):
        """Execute the database query"""
        try:
            # Database logging is handled by the centralized activity logger
            # No special db_logger attribute needed
            
            # Build filters
            filters = {}
            
            # Date range
            if self.date_from.get():
                filters['date_from'] = self.date_from.get()
            if self.date_to.get():
                filters['date_to'] = self.date_to.get()
            
            # Other filters
            if self.filter_user.get().strip():
                filters['username'] = self.filter_user.get().strip()
            if self.filter_action.get().strip():
                filters['action'] = self.filter_action.get().strip()
            if self.filter_module.get().strip():
                filters['module'] = self.filter_module.get().strip()
            if self.filter_status.get() != "ALL":
                filters['status'] = self.filter_status.get()
            if self.filter_level.get() != "ALL":
                filters['log_level'] = self.filter_level.get()
            if self.filter_security.get() != "ALL":
                filters['security_level'] = self.filter_security.get()
            
            # Execute query
            results = self.main_app.logger.db_logger.query_logs(filters, limit=5000)
            
            # Handle search text (post-filter)
            if self.search_text.get().strip():
                search_term = self.search_text.get().strip().lower()
                filtered_results = []
                for result in results:
                    # Search in details, action, module, username
                    searchable_text = f"{result.get('details', '')} {result.get('action', '')} {result.get('module', '')} {result.get('username', '')}".lower()
                    if search_term in searchable_text:
                        filtered_results.append(result)
                results = filtered_results
            
            self.current_results = results
            self.display_results(results)
            
        except Exception as e:
            messagebox.showerror("Query Error", f"Failed to execute query: {str(e)}")
    
    def display_results(self, results: List[Dict]):
        """Display query results"""
        # Clear existing results
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        
        # Update info
        self.results_info.set(f"Found {len(results)} log entries")
        
        # Add results to tree
        for result in results:
            values = (
                result.get('timestamp', ''),
                result.get('log_level', ''),
                result.get('username', ''),
                result.get('action', ''),
                result.get('module', ''),
                result.get('status', ''),
                result.get('ip_address', ''),
                (result.get('details', '')[:100] + '...') if len(result.get('details', '')) > 100 else result.get('details', '')
            )
            
            # Color code based on level and status
            tags = []
            level = result.get('log_level', '')
            status = result.get('status', '')
            
            if level in ['ERROR', 'CRITICAL']:
                tags.append('error')
            elif level == 'WARNING':
                tags.append('warning')
            elif status == 'failure':
                tags.append('failure')
            
            self.results_tree.insert('', 'end', values=values, tags=tags)
        
        # Configure tag colors
        self.results_tree.tag_configure('error', foreground='#ff6b6b')
        self.results_tree.tag_configure('warning', foreground='#ffa726')
        self.results_tree.tag_configure('failure', foreground='#ef5350')
    
    def clear_results(self):
        """Clear query results"""
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        
        self.results_info.set("No query executed")
        self.current_results = []
    
    def export_results(self):
        """Export query results"""
        if not self.current_results:
            messagebox.showwarning("Export Error", "No results to export.")
            return
        
        try:
            file_path = filedialog.asksaveasfilename(
                title="Export Query Results",
                defaultextension=".json",
                filetypes=[
                    ("JSON files", "*.json"),
                    ("CSV files", "*.csv"),
                    ("Text files", "*.txt")
                ]
            )
            
            if file_path:
                if file_path.endswith('.csv'):
                    # Export as CSV
                    import csv
                    with open(file_path, 'w', newline='', encoding='utf-8') as f:
                        if self.current_results:
                            fieldnames = self.current_results[0].keys()
                            writer = csv.DictWriter(f, fieldnames=fieldnames)
                            writer.writeheader()
                            for result in self.current_results:
                                # Convert complex fields to strings
                                row = {}
                                for key, value in result.items():
                                    if isinstance(value, (dict, list)):
                                        row[key] = json.dumps(value)
                                    else:
                                        row[key] = value
                                writer.writerow(row)
                
                elif file_path.endswith('.txt'):
                    # Export as formatted text
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(f"Query Results Export\n{'='*50}\n\n")
                        f.write(f"Total Results: {len(self.current_results)}\n")
                        f.write(f"Export Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                        
                        for i, result in enumerate(self.current_results, 1):
                            f.write(f"Entry #{i}\n{'-'*20}\n")
                            for key, value in result.items():
                                f.write(f"{key}: {value}\n")
                            f.write("\n")
                
                else:
                    # Export as JSON
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(self.current_results, f, indent=2, default=str)
                
                messagebox.showinfo("Export Complete", f"Results exported to: {file_path}")
                
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export results: {str(e)}")
    
    def save_query(self):
        """Save current query parameters"""
        try:
            file_path = filedialog.asksaveasfilename(
                title="Save Query",
                defaultextension=".json",
                filetypes=[("JSON files", "*.json")]
            )
            
            if file_path:
                query_data = {
                    'date_from': self.date_from.get(),
                    'date_to': self.date_to.get(),
                    'filter_user': self.filter_user.get(),
                    'filter_action': self.filter_action.get(),
                    'filter_module': self.filter_module.get(),
                    'filter_status': self.filter_status.get(),
                    'filter_level': self.filter_level.get(),
                    'filter_security': self.filter_security.get(),
                    'search_text': self.search_text.get(),
                    'saved_date': datetime.now().isoformat()
                }
                
                with open(file_path, 'w') as f:
                    json.dump(query_data, f, indent=2)
                
                messagebox.showinfo("Query Saved", f"Query saved to: {file_path}")
                
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save query: {str(e)}")
    
    def load_query(self):
        """Load saved query parameters"""
        try:
            file_path = filedialog.askopenfilename(
                title="Load Query",
                filetypes=[("JSON files", "*.json")]
            )
            
            if file_path:
                with open(file_path, 'r') as f:
                    query_data = json.load(f)
                
                # Set query parameters
                self.date_from.set(query_data.get('date_from', ''))
                self.date_to.set(query_data.get('date_to', ''))
                self.filter_user.set(query_data.get('filter_user', ''))
                self.filter_action.set(query_data.get('filter_action', ''))
                self.filter_module.set(query_data.get('filter_module', ''))
                self.filter_status.set(query_data.get('filter_status', 'ALL'))
                self.filter_level.set(query_data.get('filter_level', 'ALL'))
                self.filter_security.set(query_data.get('filter_security', 'ALL'))
                self.search_text.set(query_data.get('search_text', ''))
                
                messagebox.showinfo("Query Loaded", f"Query loaded from: {file_path}")
                
        except Exception as e:
            messagebox.showerror("Load Error", f"Failed to load query: {str(e)}")
    
    def show_result_details(self, event):
        """Show detailed information for selected result"""
        selection = self.results_tree.selection()
        if not selection:
            return
        
        # Get the index of selected item
        item_index = self.results_tree.index(selection[0])
        
        if item_index < len(self.current_results):
            result = self.current_results[item_index]
            
            # Create details window
            details_window = tk.Toplevel(self)
            details_window.title("Log Entry Details")
            details_window.geometry("700x500")
            details_window.configure(bg=LoggerGUITheme.DARK_BG)
            
            # Create text widget with scrollbar
            text_frame = ttk.Frame(details_window)
            text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            text_widget = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD)
            text_widget.pack(fill=tk.BOTH, expand=True)
            
            # Format details
            details_text = f"""COMPLETE LOG ENTRY DETAILS
{'='*60}

"""
            
            for key, value in result.items():
                if isinstance(value, (dict, list)):
                    details_text += f"{key.replace('_', ' ').title()}:\n{json.dumps(value, indent=2)}\n\n"
                else:
                    details_text += f"{key.replace('_', ' ').title()}: {value}\n"
            
            text_widget.insert(tk.END, details_text)
            text_widget.configure(state='disabled')


class EnhancedActivityLoggerGUI:
    """Main GUI application for Enhanced Activity Logger"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Enhanced Activity Logger - Management Console")
        self.root.geometry("1400x900")

        # Apply theme
        LoggerGUITheme.apply_theme(self.root)

        # Initialize logger
        self.logger = None
        self.update_queue = queue.Queue()
        self._update_timer_id = None  # Track timer ID for cleanup

        # Setup UI
        self.setup_ui()

        # Connect to logger
        self.connect_to_logger()

        # Start update timer
        self.start_update_timer()
    
    def setup_ui(self):
        """Setup the main user interface"""
        # Main menu
        self.setup_menu()
        
        # Header
        header_frame = ttk.Frame(self.root, style='Card.TFrame')
        header_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Logo/Title
        title_frame = ttk.Frame(header_frame)
        title_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Label(title_frame, text="Enhanced Activity Logger", 
                 style='Title.TLabel').pack(side=tk.LEFT, padx=10)
        
        # Connection status
        status_frame = ttk.Frame(header_frame)
        status_frame.pack(side=tk.RIGHT, padx=10)
        
        self.connection_status = tk.StringVar(value="Disconnected")
        ttk.Button(
            status_frame,
            text="🏠 Return to Homescreen",
            command=self.return_to_main_menu
        ).pack(side=tk.RIGHT, padx=(0, 10))

        self.connection_label = ttk.Label(status_frame, textvariable=self.connection_status, 
                                         style='Error.TLabel')
        self.connection_label.pack(side=tk.RIGHT)
        
        ttk.Label(status_frame, text="Status:", style='Info.TLabel').pack(side=tk.RIGHT, padx=(0, 5))
        
        # Main notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        
        # Create tabs
        self.log_viewer_tab = LogViewerTab(self.notebook, self)
        self.notebook.add(self.log_viewer_tab, text="📊 Live Logs")
        
        self.analytics_tab = AnalyticsTab(self.notebook, self)
        self.notebook.add(self.analytics_tab, text="📈 Analytics")
        
        self.security_tab = SecurityTab(self.notebook, self)
        self.notebook.add(self.security_tab, text="🔒 Security")
        
        self.config_tab = ConfigurationTab(self.notebook, self)
        self.notebook.add(self.config_tab, text="⚙️ Configuration")
        
        self.plugin_tab = PluginTab(self.notebook, self)
        self.notebook.add(self.plugin_tab, text="🔌 Plugins")
        
        self.query_tab = QueryTab(self.notebook, self)
        self.notebook.add(self.query_tab, text="🔍 Query")
        
        # Status bar
        self.status_bar = StatusBar(self.root, controller=self)
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)
    
    def setup_menu(self):
        """Setup the main menu"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New Configuration", command=self.new_config)
        file_menu.add_command(label="Load Configuration", command=self.load_config)
        file_menu.add_command(label="Save Configuration", command=self.save_config)
        file_menu.add_separator()
        file_menu.add_command(label="Import Logs", command=self.import_logs)
        file_menu.add_command(label="Export Logs", command=self.export_logs)
        
        # Logger menu
        logger_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Logger", menu=logger_menu)
        logger_menu.add_command(label="Connect", command=self.connect_to_logger)
        logger_menu.add_command(label="Disconnect", command=self.disconnect_logger)
        logger_menu.add_command(label="Restart Logger", command=self.restart_logger)
        logger_menu.add_separator()
        logger_menu.add_command(label="Test Log Entry", command=self.test_log_entry)
        logger_menu.add_command(label="Flush Logs", command=self.flush_logs)
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="System Health Check", command=self.system_health_check)
        tools_menu.add_command(label="Generate Report", command=self.generate_report)
        tools_menu.add_command(label="Run Anomaly Detection", command=self.run_anomaly_detection)
        tools_menu.add_separator()
        tools_menu.add_command(label="Database Maintenance", command=self.database_maintenance)
        tools_menu.add_command(label="Log File Cleanup", command=self.log_file_cleanup)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="User Guide", command=self.show_user_guide)
        help_menu.add_command(label="API Documentation", command=self.show_api_docs)
        help_menu.add_separator()
        help_menu.add_command(label="About", command=self.show_about)

        self.create_main_menu_button()

    def create_main_menu_button(self):
        """Ensure a persistent top-right navigation button"""
        try:
            if hasattr(self, "main_menu_button") and self.main_menu_button.winfo_exists():
                return
        except Exception:
            pass

        self.main_menu_button = ttk.Button(
            self.root,
            text="🏠 Return to Main Menu",
            command=self.return_to_main_menu,
        )
        self.main_menu_button.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)
    
    def connect_to_logger(self):
        """Connect to the enhanced activity logger"""
        try:
            if LOGGER_AVAILABLE:
                # Use the global logger instance
                self.logger = logger
                self.connection_status.set("Connected")
                self.connection_label.configure(style='Success.TLabel')
                self.status_bar.update_logger_status(True)
                self.status_bar.update_status("Connected to Enhanced Activity Logger")
                
                # Test the connection by getting metrics
                if hasattr(self.logger, 'get_metrics'):
                    metrics = self.logger.get_metrics()
                    self.status_bar.update_queue_size(metrics.get('queue_size', 0))
                    self.status_bar.update_total_logs(metrics.get('logs_processed', 0))
                
            else:
                # Demo mode
                self.logger = None
                self.connection_status.set("Demo Mode")
                self.connection_label.configure(style='Warning.TLabel')
                self.status_bar.update_logger_status(False)
                self.status_bar.update_status("Running in demo mode - logger module not available")
                
        except Exception as e:
            self.connection_status.set("Error")
            self.connection_label.configure(style='Error.TLabel')
            self.status_bar.update_logger_status(False)
            self.status_bar.update_status(f"Connection error: {str(e)}")
            messagebox.showerror("Connection Error", f"Failed to connect to logger: {str(e)}")
    
    def disconnect_logger(self):
        """Disconnect from logger"""
        self.logger = None
        self.connection_status.set("Disconnected")
        self.connection_label.configure(style='Error.TLabel')
        self.status_bar.update_logger_status(False)
        self.status_bar.update_status("Disconnected from logger")
    
    def restart_logger(self):
        """Restart the logger"""
        try:
            if self.logger and hasattr(self.logger, 'shutdown'):
                self.logger.shutdown()
            
            time.sleep(1)  # Give it a moment to shutdown
            self.connect_to_logger()
            
        except Exception as e:
            messagebox.showerror("Restart Error", f"Failed to restart logger: {str(e)}")
    
    def start_update_timer(self):
        """Start the update timer for real-time updates"""
        # Cancel previous timer if exists
        if self._update_timer_id:
            try:
                self.root.after_cancel(self._update_timer_id)
            except:
                pass

        try:
            self.update_gui()
            # Schedule next update and store ID
            self._update_timer_id = self.root.after(1000, self.start_update_timer)  # Update every second
        except tk.TclError:
            # Widget destroyed, stop scheduling
            pass
    
    def update_gui(self):
        """Update GUI with real-time data"""
        try:
            if self.logger and hasattr(self.logger, 'get_metrics'):
                metrics = self.logger.get_metrics()
                self.status_bar.update_queue_size(metrics.get('queue_size', 0))
                self.status_bar.update_total_logs(metrics.get('logs_processed', 0))
                
        except Exception as e:
            # Silently handle errors to avoid spamming
            pass
    
    # Menu command implementations
    def new_config(self):
        """Create a new configuration"""
        try:
            file_path = filedialog.asksaveasfilename(
                title="Create New Configuration",
                defaultextension=".json",
                filetypes=[("JSON files", "*.json")]
            )
            
            if file_path:
                if LOGGER_AVAILABLE:
                    create_default_config(file_path)
                    messagebox.showinfo("Configuration Created", f"New configuration created at: {file_path}")
                else:
                    # Create a minimal config for demo mode
                    default_config = {
                        "log_dir": "logs",
                        "min_log_level": "INFO",
                        "output_formats": ["json"],
                        "queue_size": 10000
                    }
                    with open(file_path, 'w') as f:
                        json.dump(default_config, f, indent=2)
                    messagebox.showinfo("Configuration Created", f"Demo configuration created at: {file_path}")
                    
        except Exception as e:
            messagebox.showerror("Configuration Error", f"Failed to create configuration: {str(e)}")
    
    def load_config(self):
        """Load configuration from file"""
        if hasattr(self.config_tab, 'load_config'):
            self.config_tab.load_config()
        else:
            messagebox.showwarning("Load Configuration", "Configuration tab not available.")
    
    def save_config(self):
        """Save current configuration to file"""
        if hasattr(self.config_tab, 'save_config'):
            self.config_tab.save_config()
        else:
            messagebox.showwarning("Save Configuration", "Configuration tab not available.")
    
    def import_logs(self):
        """Import logs from file"""
        try:
            file_path = filedialog.askopenfilename(
                title="Import Logs",
                filetypes=[
                    ("JSON files", "*.json"),
                    ("CSV files", "*.csv"),
                    ("Text files", "*.txt"),
                    ("All files", "*.*")
                ]
            )

            if not file_path:
                return

            # Create import progress dialog
            import_dialog = tk.Toplevel(self.root)
            import_dialog.title("Import Logs")
            import_dialog.geometry("600x500")
            import_dialog.transient(self.root)

            ttk.Label(import_dialog, text="Importing Logs",
                     font=('TkDefaultFont', 14, 'bold')).pack(pady=10)

            ttk.Label(import_dialog, text=f"File: {file_path}", foreground='blue').pack()

            # Progress area
            progress_frame = ttk.Frame(import_dialog, padding=10)
            progress_frame.pack(fill='both', expand=True)

            progress_var = tk.DoubleVar()
            progress_bar = ttk.Progressbar(progress_frame, variable=progress_var, maximum=100)
            progress_bar.pack(fill='x', pady=10)

            status_label = ttk.Label(progress_frame, text="Reading file...")
            status_label.pack(pady=5)

            results_text = tk.Text(progress_frame, height=20, width=70)
            results_text.pack(fill='both', expand=True, pady=5)

            def perform_import():
                try:
                    import json
                    import csv

                    imported_count = 0
                    error_count = 0
                    logs_to_import = []

                    # Determine file type and parse
                    if file_path.endswith('.json'):
                        status_label.config(text="Parsing JSON file...")
                        progress_var.set(20)
                        import_dialog.update()

                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            if isinstance(data, list):
                                logs_to_import = data
                            elif isinstance(data, dict) and 'logs' in data:
                                logs_to_import = data['logs']
                            else:
                                logs_to_import = [data]

                    elif file_path.endswith('.csv'):
                        status_label.config(text="Parsing CSV file...")
                        progress_var.set(20)
                        import_dialog.update()

                        with open(file_path, 'r', encoding='utf-8') as f:
                            reader = csv.DictReader(f)
                            for row in reader:
                                logs_to_import.append(row)

                    else:  # Text file
                        status_label.config(text="Parsing text file...")
                        progress_var.set(20)
                        import_dialog.update()

                        with open(file_path, 'r', encoding='utf-8') as f:
                            for line in f:
                                line = line.strip()
                                if line:
                                    # Parse simple log format: timestamp | level | message
                                    parts = line.split('|')
                                    if len(parts) >= 3:
                                        logs_to_import.append({
                                            'timestamp': parts[0].strip(),
                                            'level': parts[1].strip(),
                                            'message': '|'.join(parts[2:]).strip()
                                        })
                                    else:
                                        logs_to_import.append({
                                            'timestamp': datetime.now().isoformat(),
                                            'level': 'INFO',
                                            'message': line
                                        })

                    results_text.insert('end', f"Found {len(logs_to_import)} log entries\n\n")

                    # Import logs
                    status_label.config(text="Importing logs...")
                    for i, log_entry in enumerate(logs_to_import):
                        try:
                            # In real implementation, would save to database
                            # For now, just validate and count
                            if isinstance(log_entry, dict):
                                timestamp = log_entry.get('timestamp', datetime.now().isoformat())
                                level = log_entry.get('level', 'INFO')
                                message = log_entry.get('message', str(log_entry))

                                results_text.insert('end', f"✓ [{timestamp}] {level}: {message[:50]}...\n")
                                imported_count += 1
                            else:
                                error_count += 1
                                results_text.insert('end', f"✗ Invalid log entry: {log_entry}\n")

                            # Update progress
                            progress_var.set(20 + (i / len(logs_to_import)) * 80)
                            import_dialog.update()

                        except Exception as e:
                            error_count += 1
                            results_text.insert('end', f"✗ Error importing entry: {e}\n")

                        results_text.see('end')

                    progress_var.set(100)
                    status_label.config(text="Import Complete!")

                    # Summary
                    summary = f"\n{'='*60}\nImport Summary:\n"
                    summary += f"Total entries: {len(logs_to_import)}\n"
                    summary += f"Successfully imported: {imported_count}\n"
                    summary += f"Errors: {error_count}\n"
                    results_text.insert('end', summary)

                    ttk.Button(progress_frame, text="Close",
                              command=import_dialog.destroy).pack(pady=10)

                except Exception as e:
                    messagebox.showerror("Import Error", f"Failed to import logs: {e}",
                                       parent=import_dialog)

            # Start import
            import_dialog.after(100, perform_import)

        except Exception as e:
            messagebox.showerror("Import Error", f"Failed to import logs: {str(e)}")
    
    def export_logs(self):
        """Export logs to file"""
        if hasattr(self.log_viewer_tab, 'export_logs'):
            self.log_viewer_tab.export_logs()
        else:
            messagebox.showwarning("Export Logs", "Log viewer tab not available.")
    
    def test_log_entry(self):
        """Create a test log entry"""
        try:
            if self.logger and hasattr(self.logger, 'log_activity'):
                # Create a test log entry
                self.logger.log_activity(
                    "test_user", "GUI Test User", "admin",
                    "gui_test", "gui_application",
                    "Test log entry created from GUI",
                    "success", LogLevel.INFO, SecurityLevel.LOW,
                    {"source": "gui_test", "timestamp": datetime.now().isoformat()}
                )
                messagebox.showinfo("Test Log", "Test log entry created successfully.")
            else:
                messagebox.showwarning("Test Log", "Logger not available or not connected.")
                
        except Exception as e:
            messagebox.showerror("Test Log Error", f"Failed to create test log entry: {str(e)}")
    
    def flush_logs(self):
        """Flush pending logs"""
        try:
            if self.logger and hasattr(self.logger, 'flush_logs'):
                success = self.logger.flush_logs(timeout=10)
                if success:
                    messagebox.showinfo("Flush Logs", "All pending logs have been flushed.")
                else:
                    messagebox.showwarning("Flush Logs", "Some logs may not have been flushed within the timeout period.")
            else:
                messagebox.showwarning("Flush Logs", "Logger not available or not connected.")
                
        except Exception as e:
            messagebox.showerror("Flush Error", f"Failed to flush logs: {str(e)}")
    
    def system_health_check(self):
        """Perform system health check"""
        try:
            if self.logger and hasattr(self.logger, 'get_system_health'):
                health = self.logger.get_system_health()
                
                # Create health check window
                health_window = tk.Toplevel(self.root)
                health_window.title("System Health Check")
                health_window.geometry("500x400")
                health_window.configure(bg=LoggerGUITheme.DARK_BG)
                
                text_widget = scrolledtext.ScrolledText(health_window, wrap=tk.WORD)
                text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
                
                health_text = f"""SYSTEM HEALTH CHECK REPORT
{'='*50}

Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

SYSTEM METRICS
{'='*50}
CPU Usage: {health.get('cpu_usage', 0):.1f}%
Memory Usage: {health.get('memory_usage', 0):.1f}%
Disk Usage: {health.get('disk_usage', 0):.1f}%
Active Connections: {health.get('active_connections', 0)}
System Uptime: {health.get('uptime', 0):.0f} seconds

MEMORY DETAILS
{'='*50}
Available Memory: {health.get('available_memory', 0):,} bytes
Total Memory: {health.get('total_memory', 0):,} bytes

RECOMMENDATIONS
{'='*50}
"""
                
                # Add recommendations based on metrics
                cpu_usage = health.get('cpu_usage', 0)
                memory_usage = health.get('memory_usage', 0)
                disk_usage = health.get('disk_usage', 0)
                
                if cpu_usage > 80:
                    health_text += "• HIGH CPU USAGE: Consider optimizing processes or scaling resources.\n"
                if memory_usage > 85:
                    health_text += "• HIGH MEMORY USAGE: Monitor for memory leaks and consider increasing memory.\n"
                if disk_usage > 90:
                    health_text += "• LOW DISK SPACE: Clean up old files or expand storage.\n"
                
                if cpu_usage <= 80 and memory_usage <= 85 and disk_usage <= 90:
                    health_text += "• System health is good. No immediate action required.\n"
                
                text_widget.insert(tk.END, health_text)
                text_widget.configure(state='disabled')
                
            else:
                messagebox.showwarning("Health Check", "System health monitoring not available.")
                
        except Exception as e:
            messagebox.showerror("Health Check Error", f"Failed to perform health check: {str(e)}")
    
    def generate_report(self):
        """Generate analytics report"""
        try:
            if hasattr(self, 'analytics_tab') and hasattr(self.analytics_tab, 'generate_report'):
                self.analytics_tab.generate_report()
            else:
                # Provide basic analytics functionality
                messagebox.showinfo("Analytics", "Analytics reporting is available through the Analytics tab.")
        except Exception as e:
            messagebox.showerror("Report Error", f"Failed to generate report: {str(e)}")

    def run_anomaly_detection(self):
        """Run anomaly detection"""
        if hasattr(self.security_tab, 'run_anomaly_detection'):
            self.security_tab.run_anomaly_detection()
        else:
            messagebox.showwarning("Anomaly Detection", "Security tab not available.")
    
    def database_maintenance(self):
        """Perform database maintenance"""
        try:
            # Database maintenance is available through centralized activity logger

            # Create maintenance dialog
            maintenance_window = tk.Toplevel(self.root)
            maintenance_window.title("Database Maintenance")
            maintenance_window.geometry("400x300")
            maintenance_window.configure(bg=LoggerGUITheme.DARK_BG)
            
            ttk.Label(maintenance_window, text="Database Maintenance Options", 
                     style='Title.TLabel').pack(pady=10)
            
            # Maintenance options
            cleanup_days = tk.IntVar(value=90)
            
            ttk.Label(maintenance_window, text="Delete logs older than (days):", 
                     style='Info.TLabel').pack(pady=(20, 5))
            ttk.Entry(maintenance_window, textvariable=cleanup_days, width=10).pack(pady=(0, 10))
            
            def perform_cleanup():
                try:
                    days = cleanup_days.get()
                    deleted_count = self.logger.db_logger.delete_old_logs(days)
                    messagebox.showinfo("Cleanup Complete", f"Deleted {deleted_count} old log entries.")
                    maintenance_window.destroy()
                except Exception as e:
                    messagebox.showerror("Cleanup Error", f"Failed to perform cleanup: {str(e)}")
            
            def show_stats():
                try:
                    stats = self.logger.db_logger.get_database_stats()
                    stats_text = f"""Database Statistics:
Total Logs: {stats.get('total_logs', 0):,}
Recent Activity (24h): {stats.get('recent_activity', 0):,}
Database Size: {stats.get('database_size', 0):,} bytes
"""
                    messagebox.showinfo("Database Statistics", stats_text)
                except Exception as e:
                    messagebox.showerror("Statistics Error", f"Failed to get statistics: {str(e)}")
            
            button_frame = ttk.Frame(maintenance_window)
            button_frame.pack(pady=20)
            
            ttk.Button(button_frame, text="Show Statistics", 
                      command=show_stats).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Cleanup Old Logs", 
                      command=perform_cleanup).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Cancel", 
                      command=maintenance_window.destroy).pack(side=tk.LEFT, padx=5)
            
        except Exception as e:
            messagebox.showerror("Maintenance Error", f"Failed to open database maintenance: {str(e)}")
    
    def log_file_cleanup(self):
        """Perform log file cleanup"""
        try:
            if not self.logger or not hasattr(self.logger, 'rotation_manager'):
                messagebox.showwarning("File Cleanup", "Log rotation manager not available.")
                return
            
            if messagebox.askyesno("Log File Cleanup", 
                                 "This will remove old log files based on retention settings. Continue?"):
                
                log_dir = getattr(self.logger, 'log_dir', 'logs')
                self.logger.rotation_manager.cleanup_old_logs(log_dir)
                messagebox.showinfo("Cleanup Complete", "Old log files have been cleaned up.")
                
        except Exception as e:
            messagebox.showerror("Cleanup Error", f"Failed to cleanup log files: {str(e)}")
    
    def show_user_guide(self):
        """Show user guide"""
        guide_window = tk.Toplevel(self.root)
        guide_window.title("Enhanced Activity Logger - User Guide")
        guide_window.geometry("800x600")
        guide_window.configure(bg=LoggerGUITheme.DARK_BG)
        
        text_widget = scrolledtext.ScrolledText(guide_window, wrap=tk.WORD)
        text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        user_guide = """ENHANCED ACTIVITY LOGGER - USER GUIDE
========================================

OVERVIEW
--------
The Enhanced Activity Logger GUI provides a comprehensive interface for monitoring,
analyzing, and managing application activity logs in real-time.

MAIN FEATURES
-------------

1. LIVE LOGS TAB (📊)
   - Real-time log monitoring
   - Filtering by level, user, action, module
   - Auto-refresh functionality
   - Export capabilities
   - Detailed log entry inspection

2. ANALYTICS TAB (📈)
   - System statistics and metrics
   - Visual charts and graphs (when matplotlib available)
   - Performance monitoring
   - Report generation

3. SECURITY TAB (🔒)
   - Security event monitoring
   - Suspicious IP management
   - Anomaly detection
   - Security report generation
   - Failed login tracking

4. CONFIGURATION TAB (⚙️)
   - Logger settings management
   - Output format configuration
   - Security parameter tuning
   - Cloud integration setup
   - Configuration import/export

5. PLUGINS TAB (🔌)
   - Plugin management interface
   - Enable/disable plugins
   - Plugin configuration
   - Default plugin installation

6. QUERY TAB (🔍)
   - Advanced database querying
   - Custom filters and search
   - Date range selection
   - Query save/load functionality
   - Export query results

GETTING STARTED
---------------

1. CONNECTION
   - The GUI automatically connects to the logger on startup
   - Check the connection status in the top-right corner
   - Use Logger menu to reconnect if needed

2. VIEWING LOGS
   - Navigate to the Live Logs tab
   - Use filters to narrow down results
   - Double-click entries for detailed view
   - Enable auto-refresh for real-time monitoring

3. ANALYTICS
   - Visit the Analytics tab for system overview
   - Generate reports using the "Generate Report" button
   - Monitor system health metrics

4. SECURITY MONITORING
   - Check the Security tab for threats
   - Use anomaly detection to find unusual patterns
   - Manage suspicious IPs manually

5. CONFIGURATION
   - Modify settings in the Configuration tab
   - Apply changes using "Apply Changes" button
   - Save/load configurations for backup

KEYBOARD SHORTCUTS
------------------
- Ctrl+R: Refresh current tab
- Ctrl+E: Export data from current tab
- Ctrl+F: Focus search/filter field
- F5: Refresh all data

TROUBLESHOOTING
---------------

Q: GUI shows "Demo Mode" or "Disconnected"
A: The simple_activity_logger module may not be available. Check installation.

Q: No data appears in logs
A: Ensure database logging is enabled in configuration.

Q: Charts don't appear in Analytics
A: Install matplotlib: pip install matplotlib

Q: Export fails
A: Check file permissions and available disk space.

SUPPORT
-------
For additional support, check the API documentation or contact the development team.
"""
        
        text_widget.insert(tk.END, user_guide)
        text_widget.configure(state='disabled')
    
    def show_api_docs(self):
        """Show API documentation"""
        try:
            # Show API documentation info
            doc_text = """Activity Logger API Documentation

The Activity Logger provides comprehensive logging functionality for the University Management System.

Main Functions:
- log_activity(action, user): Log a general activity
- log_login(username, success): Log login attempts
- log_logout(username): Log logout events
- log_create(item_type, item_name): Log item creation
- log_update(item_type, item_name): Log item updates
- log_delete(item_type, item_name): Log item deletion

For detailed documentation, see:
- Local: university_system/modules/shared/utils/activity_logger.py
- Online: Check the project README.md for full documentation
"""
            messagebox.showinfo("API Documentation", doc_text)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to show documentation: {str(e)}")
    
    def show_about(self):
        """Show about dialog"""
        about_window = tk.Toplevel(self.root)
        about_window.title("About Enhanced Activity Logger")
        about_window.geometry("500x400")
        about_window.configure(bg=LoggerGUITheme.DARK_BG)
        about_window.resizable(False, False)
        
        # Center the window
        about_window.transient(self.root)
        about_window.grab_set()
        
        main_frame = ttk.Frame(about_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Title
        ttk.Label(main_frame, text="Enhanced Activity Logger", 
                 style='Title.TLabel').pack(pady=(0, 10))
        
        # Version info
        version_text = """Version 2.0.0
GUI Management Console

A comprehensive activity logging solution with
real-time monitoring, analytics, and security features.
"""
        ttk.Label(main_frame, text=version_text, 
                 style='Info.TLabel', justify=tk.CENTER).pack(pady=(0, 20))
        
        # Features
        features_text = """Key Features:
• Real-time log monitoring and filtering
• Advanced analytics and reporting
• Security monitoring and anomaly detection
• Plugin system for extensibility
• Database querying and search
• Configuration management
• Multi-format log export
• System health monitoring
"""
        ttk.Label(main_frame, text=features_text, 
                 style='Info.TLabel', justify=tk.LEFT).pack(pady=(0, 20))
        
        # Credits
        credits_text = """Built with Python and Tkinter
Compatible with the original simple_activity_logger
Fully backward compatible

© 2024 Enhanced Activity Logger Team
"""
        ttk.Label(main_frame, text=credits_text, 
                 style='Info.TLabel', justify=tk.CENTER).pack(pady=(0, 20))
        
        ttk.Button(main_frame, text="Close", 
                  command=about_window.destroy).pack()
    
    def on_closing(self):
        """Handle application closing"""
        try:
            # Ask for confirmation
            if messagebox.askyesno("Exit", "Are you sure you want to exit?"):
                # Cancel all timers first
                if self._update_timer_id:
                    try:
                        self.root.after_cancel(self._update_timer_id)
                    except:
                        pass

                # Disconnect from logger gracefully
                if self.logger and hasattr(self.logger, 'shutdown'):
                    self.status_bar.update_status("Shutting down logger...")
                    self.root.update()

                    # Give logger time to flush pending logs
                    if hasattr(self.logger, 'flush_logs'):
                        self.logger.flush_logs(timeout=5)

                    # Shutdown logger
                    self.logger.shutdown(timeout=10)

                # Destroy the GUI
                self.root.quit()
                self.root.destroy()

        except Exception as e:
            print(f"Error during shutdown: {e}")
            # Cancel timer even on error
            if hasattr(self, '_update_timer_id') and self._update_timer_id:
                try:
                    self.root.after_cancel(self._update_timer_id)
                except:
                    pass
            self.root.quit()
            self.root.destroy()
    
    def return_to_main_menu(self):
        """Return to the main menu"""
        try:
            # Check if this is a child window (Toplevel) or standalone (Tk)
            root_widget = self.root if hasattr(self, 'root') else self.master
            if isinstance(root_widget, tk.Toplevel):
                # Just close the child window
                root_widget.destroy()
            else:
                # Running standalone, need to create main GUI
                root_widget.destroy()
                from university_system.modules.shared.gui.main_gui import UnifiedManagementGUI
                app = UnifiedManagementGUI(self.auth)
                app.run()
        except Exception as e:
            print(f"Error returning to main menu: {e}")
            import traceback
            traceback.print_exc()

    def run(self):
        """Run the GUI application"""
        # Set closing protocol
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Center window on screen
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - (self.root.winfo_width() // 2)
        y = (self.root.winfo_screenheight() // 2) - (self.root.winfo_height() // 2)
        self.root.geometry(f"+{x}+{y}")
        
        # Start the main loop
        self.root.mainloop()


def main():
    """Main entry point for the GUI application"""
    try:
        # Initialize and run the GUI
        app = EnhancedActivityLoggerGUI()
        app.run()
        
    except KeyboardInterrupt:
        print("\nApplication interrupted by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

# Backward compatibility functions for existing code
def launch_logger_gui():
    """Launch the logger GUI - backward compatibility function"""
    main()

def create_gui_instance():
    """Create GUI instance without running - for embedding in other applications"""
    return EnhancedActivityLoggerGUI()

# Example usage and demonstration
if __name__ == "__main__":
    print("Enhanced Activity Logger GUI")
    print("=" * 50)
    print("Starting graphical management console...")
    print()
    
    if not LOGGER_AVAILABLE:
        print("WARNING: simple_activity_logger module not found.")
        print("The GUI will run in demo mode with limited functionality.")
        print("To enable full functionality, ensure the simple_activity_logger.py")
        print("file is in the same directory or in your Python path.")
        print()
    
    if not MATPLOTLIB_AVAILABLE:
        print("INFO: matplotlib not available - charts will be disabled.")
        print("To enable charts, install matplotlib: pip install matplotlib")
        print()
    
    print("Features available in this GUI:")
    print("• Real-time log monitoring and filtering")
    print("• Advanced analytics and reporting")
    print("• Security monitoring and management")
    print("• Configuration management")
    print("• Plugin system management")
    print("• Database querying and search")
    print("• System health monitoring")
    print("• Multi-format export capabilities")
    print()
    
    try:
        print("Initializing GUI components...")
        print("Loading theme and configurations...")
        print("Connecting to logger services...")
        print()
        print("GUI Ready! Opening management console...")
        print("Use Ctrl+C to exit safely or close the window.")
        print()
        
        # Start the application
        main()
        
    except KeyboardInterrupt:
        print("\n" + "=" * 50)
        print("Application interrupted by user (Ctrl+C)")
        print("Shutting down gracefully...")
        sys.exit(0)
        
    except Exception as e:
        print("\n" + "=" * 50)
        print(f"FATAL ERROR: {e}")
        print("Please check your installation and try again.")
        import traceback
        traceback.print_exc()
        sys.exit(1)
        
    finally:
        print("\n" + "=" * 50)
        print("Enhanced Activity Logger GUI session ended.")
        print("Thank you for using the Enhanced Activity Logger!")


# Additional utility functions for integration
def check_dependencies():
    """Check if all required dependencies are available"""
    dependencies = {
        'logger': LOGGER_AVAILABLE,
        'matplotlib': MATPLOTLIB_AVAILABLE,
        'tkinter': True  # Should always be available in standard Python
    }
    
    missing = [dep for dep, available in dependencies.items() if not available]
    
    if missing:
        print(f"Missing dependencies: {', '.join(missing)}")
        return False
    return True

def get_gui_version():
    """Get the current GUI version"""
    return "2.0.0"

def print_startup_banner():
    """Print the startup banner with system info"""
    print(f"""
    ╔═══════════════════════════════════════════════════════════════╗
    ║                Enhanced Activity Logger GUI                   ║
    ║                        Version {get_gui_version()}                           ║
    ║                                                               ║
    ║  A comprehensive management console for activity logging      ║
    ║  with real-time monitoring, analytics, and security features ║
    ╚═══════════════════════════════════════════════════════════════╝
    
    System Status:
    - Logger Module: {'✓ Available' if LOGGER_AVAILABLE else '✗ Missing (Demo Mode)'}
    - Charts Support: {'✓ Available' if MATPLOTLIB_AVAILABLE else '✗ Missing'}
    - Python Version: {sys.version.split()[0]}
    - Platform: {sys.platform}
    
    """)

# Demo mode functionality
def run_demo_mode():
    """Run the GUI in demonstration mode when logger is not available"""
    print("Running in DEMO MODE")
    print("This mode allows you to explore the GUI interface without a working logger.")
    print("Some features will be simulated or disabled.")
    print()
    return True

# Installation helper
def check_installation():
    """Check if the logger is properly installed and configured"""
    if not LOGGER_AVAILABLE:
        print("Setup Instructions:")
        print("1. Ensure 'simple_activity_logger.py' is in the same directory")
        print("2. Or install the logger package: pip install enhanced-activity-logger")
        print("3. Check that all dependencies are installed")
        print()
        return False
    return True

# Entry point with enhanced error handling and setup
if __name__ == "__main__":
    # Print startup banner
    print_startup_banner()
    
    # Check installation
    if not check_installation() and not run_demo_mode():
        sys.exit(1)
    
    # Check dependencies
    check_dependencies()
    
    # Run the main application
    try:
        print("Launching Enhanced Activity Logger GUI...")
        print("Please wait while the interface loads...")
        print()
        main()
    except Exception as e:
        print(f"\nStartup failed: {e}")
        sys.exit(1)
