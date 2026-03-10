"""
Chart Generation Utility for Advanced Search GUI
Generates professional charts from database data using matplotlib and seaborn.
"""

import os
import tkinter as tk
from tkinter import ttk
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional
import tempfile

try:
    import matplotlib
    matplotlib.use('TkAgg')  # Use TkAgg backend for Tkinter integration
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
    from matplotlib.figure import Figure
    import seaborn as sns
    import numpy as np
    CHARTS_AVAILABLE = True
except ImportError:
    CHARTS_AVAILABLE = False
    plt = None
    Figure = None
    FigureCanvasTkAgg = None
    NavigationToolbar2Tk = None
    sns = None
    np = None

from education_system.university_system.infrastructure.database.db import get_connection

# Import email service for sending charts
try:
    from education_system.university_system.infrastructure.email.email_service import send_email, send_email_as_system
    from education_system.university_system.infrastructure.shared_context import get_auth
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    send_email = None
    send_email_as_system = None
    get_auth = None


class ChartGenerator:
    """Professional chart generation from database data"""

    def __init__(self):
        """Initialize chart generator with default styling"""
        self.available = CHARTS_AVAILABLE

        if self.available:
            # Set professional styling
            sns.set_style("whitegrid")
            sns.set_palette("husl")
            plt.rcParams['figure.figsize'] = (10, 6)
            plt.rcParams['font.size'] = 10
            plt.rcParams['axes.labelsize'] = 11
            plt.rcParams['axes.titlesize'] = 13
            plt.rcParams['xtick.labelsize'] = 9
            plt.rcParams['ytick.labelsize'] = 9
            plt.rcParams['legend.fontsize'] = 9
            plt.rcParams['figure.titlesize'] = 14

    def is_available(self) -> bool:
        """Check if chart generation is available"""
        return self.available

    def generate_chart(self, chart_type: str, data: Dict[str, Any],
                      title: str = None) -> Optional[Figure]:
        """
        Generate a chart based on type and data

        Args:
            chart_type: Type of chart (bar, line, pie, histogram, scatter, etc.)
            data: Dictionary containing chart data
            title: Chart title

        Returns:
            matplotlib Figure object or None if error
        """
        if not self.available:
            return None

        try:
            fig = Figure(figsize=(10, 6), dpi=100)
            ax = fig.add_subplot(111)

            if chart_type == "bar":
                self._create_bar_chart(ax, data, title)
            elif chart_type == "line":
                self._create_line_chart(ax, data, title)
            elif chart_type == "pie":
                self._create_pie_chart(ax, data, title)
            elif chart_type == "histogram":
                self._create_histogram(ax, data, title)
            elif chart_type == "scatter":
                self._create_scatter_plot(ax, data, title)
            elif chart_type == "heatmap":
                self._create_heatmap(fig, data, title)
            elif chart_type == "box":
                self._create_box_plot(ax, data, title)
            elif chart_type == "grouped_bar":
                self._create_grouped_bar_chart(ax, data, title)
            else:
                # Default to bar chart
                self._create_bar_chart(ax, data, title)

            fig.tight_layout()
            return fig

        except Exception as e:
            print(f"Error generating {chart_type} chart: {e}")
            return None

    def _create_bar_chart(self, ax, data: Dict, title: str):
        """Create a bar chart"""
        labels = data.get('labels', [])
        values = data.get('values', [])
        xlabel = data.get('xlabel', '')
        ylabel = data.get('ylabel', 'Count')
        color = data.get('color', 'steelblue')

        bars = ax.bar(range(len(labels)), values, color=color, alpha=0.7, edgecolor='black')
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=45, ha='right')
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.set_title(title or 'Bar Chart', fontweight='bold', pad=20)

        # Add value labels on top of bars
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{int(height)}',
                   ha='center', va='bottom', fontsize=9)

        ax.grid(axis='y', alpha=0.3)

    def _create_line_chart(self, ax, data: Dict, title: str):
        """Create a line chart"""
        x = data.get('x', [])
        y = data.get('y', [])
        xlabel = data.get('xlabel', '')
        ylabel = data.get('ylabel', 'Value')
        color = data.get('color', 'steelblue')
        marker = data.get('marker', 'o')

        ax.plot(x, y, color=color, marker=marker, linewidth=2, markersize=6)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.set_title(title or 'Line Chart', fontweight='bold', pad=20)

        # Rotate x-axis labels if they're strings
        if x and isinstance(x[0], str):
            ax.set_xticklabels(x, rotation=45, ha='right')

        ax.grid(alpha=0.3)

    def _create_pie_chart(self, ax, data: Dict, title: str):
        """Create a pie chart"""
        labels = data.get('labels', [])
        sizes = data.get('sizes', [])
        colors = data.get('colors', sns.color_palette("husl", len(labels)))
        explode = data.get('explode', [0.05] * len(labels))  # Slightly separate all slices

        # Create pie chart
        wedges, texts, autotexts = ax.pie(sizes, labels=labels, autopct='%1.1f%%',
                                           startangle=90, colors=colors, explode=explode,
                                           shadow=True)

        # Make percentage text bold and larger
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_weight('bold')
            autotext.set_fontsize(10)

        ax.set_title(title or 'Pie Chart', fontweight='bold', pad=20)
        ax.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle

    def _create_histogram(self, ax, data: Dict, title: str):
        """Create a histogram"""
        values = data.get('values', [])
        bins = data.get('bins', 20)
        xlabel = data.get('xlabel', 'Value')
        ylabel = data.get('ylabel', 'Frequency')
        color = data.get('color', 'steelblue')

        n, bins_edges, patches = ax.hist(values, bins=bins, color=color, alpha=0.7,
                                         edgecolor='black')
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.set_title(title or 'Histogram', fontweight='bold', pad=20)
        ax.grid(axis='y', alpha=0.3)

    def _create_scatter_plot(self, ax, data: Dict, title: str):
        """Create a scatter plot"""
        x = data.get('x', [])
        y = data.get('y', [])
        xlabel = data.get('xlabel', 'X')
        ylabel = data.get('ylabel', 'Y')
        color = data.get('color', 'steelblue')
        size = data.get('size', 50)

        ax.scatter(x, y, c=color, s=size, alpha=0.6, edgecolors='black')
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.set_title(title or 'Scatter Plot', fontweight='bold', pad=20)
        ax.grid(alpha=0.3)

    def _create_heatmap(self, fig, data: Dict, title: str):
        """Create a heatmap"""
        matrix = data.get('matrix', [])
        xlabels = data.get('xlabels', [])
        ylabels = data.get('ylabels', [])
        cmap = data.get('cmap', 'YlOrRd')

        ax = fig.add_subplot(111)
        im = ax.imshow(matrix, cmap=cmap, aspect='auto')

        # Set ticks and labels
        if xlabels:
            ax.set_xticks(range(len(xlabels)))
            ax.set_xticklabels(xlabels, rotation=45, ha='right')
        if ylabels:
            ax.set_yticks(range(len(ylabels)))
            ax.set_yticklabels(ylabels)

        # Add colorbar
        fig.colorbar(im, ax=ax)

        ax.set_title(title or 'Heatmap', fontweight='bold', pad=20)

    def _create_box_plot(self, ax, data: Dict, title: str):
        """Create a box plot"""
        values = data.get('values', [])
        labels = data.get('labels', [])
        ylabel = data.get('ylabel', 'Value')

        bp = ax.boxplot(values, labels=labels, patch_artist=True)

        # Customize box plot colors
        for patch in bp['boxes']:
            patch.set_facecolor('steelblue')
            patch.set_alpha(0.7)

        ax.set_ylabel(ylabel)
        ax.set_title(title or 'Box Plot', fontweight='bold', pad=20)
        ax.grid(axis='y', alpha=0.3)

        if labels:
            ax.set_xticklabels(labels, rotation=45, ha='right')

    def _create_grouped_bar_chart(self, ax, data: Dict, title: str):
        """Create a grouped bar chart"""
        labels = data.get('labels', [])
        groups = data.get('groups', {})  # Dict with group_name: values
        xlabel = data.get('xlabel', '')
        ylabel = data.get('ylabel', 'Count')

        x = np.arange(len(labels))
        width = 0.8 / len(groups)  # Width of bars

        for i, (group_name, values) in enumerate(groups.items()):
            offset = width * i - (len(groups) - 1) * width / 2
            ax.bar(x + offset, values, width, label=group_name, alpha=0.8)

        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.set_title(title or 'Grouped Bar Chart', fontweight='bold', pad=20)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=45, ha='right')
        ax.legend()
        ax.grid(axis='y', alpha=0.3)

    def save_chart(self, fig: Figure, filename: str = None) -> str:
        """
        Save chart to file

        Args:
            fig: matplotlib Figure object
            filename: Optional filename, defaults to temp file

        Returns:
            Path to saved file
        """
        if filename is None:
            # Create temp file
            fd, filename = tempfile.mkstemp(suffix='.png', prefix='chart_')
            os.close(fd)

        fig.savefig(filename, dpi=150, bbox_inches='tight', facecolor='white')
        return filename

    def email_chart(self, fig: Figure, recipient_email: str, chart_title: str = "Chart",
                   message: str = None) -> bool:
        """
        Email chart as attachment to specified recipient

        Args:
            fig: matplotlib Figure object
            recipient_email: Email address of recipient
            chart_title: Title for the chart (used in email subject and filename)
            message: Optional custom message body

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        if not EMAIL_AVAILABLE:
            print("Email service not available. Cannot send chart.")
            return False

        try:
            # Save chart to temporary file
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"chart_{chart_title.replace(' ', '_')}_{timestamp}.png"
            temp_path = os.path.join(tempfile.gettempdir(), filename)

            fig.savefig(temp_path, dpi=200, bbox_inches='tight', facecolor='white')

            # Prepare email content
            subject = f"Chart: {chart_title}"

            if message is None:
                body = f"""Dear Administrator,

Please find attached the requested chart: {chart_title}

Chart Details:
- Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- Format: PNG (High Resolution - 200 DPI)
- File: {filename}

This chart was automatically generated from the University Management System.

Best regards,
University System
"""
            else:
                body = message

            # Send email with attachment
            result = send_email_as_system(
                recipient_email=recipient_email,
                subject=subject,
                body=body,
                system_name="University Chart System",
                attachments=[temp_path]
            )

            if result:
                print(f"✓ Chart emailed successfully to {recipient_email}")
                return True
            else:
                print(f"✗ Failed to email chart to {recipient_email}")
                return False

        except Exception as e:
            print(f"Error emailing chart: {str(e)}")
            return False
        finally:
            # Clean up temp file (keep it for a bit in case of retry)
            pass


class ChartViewer:
    """Window for viewing charts with matplotlib integration"""

    def __init__(self, parent, fig: Figure, title: str = "Chart Viewer", chart_title: str = None):
        """
        Initialize chart viewer window

        Args:
            parent: Parent tkinter window
            fig: matplotlib Figure to display
            title: Window title
            chart_title: Chart title for email subject (defaults to window title)
        """
        self.window = tk.Toplevel(parent)
        self.window.title(title)
        self.window.geometry("1000x700")
        self.window.transient(parent)

        # Store chart title for email
        self.chart_title = chart_title or title

        # Create main container
        container = ttk.Frame(self.window)
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create canvas for matplotlib figure
        canvas = FigureCanvasTkAgg(fig, master=container)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Add navigation toolbar
        toolbar_frame = ttk.Frame(container)
        toolbar_frame.pack(fill=tk.X, pady=(5, 0))
        toolbar = NavigationToolbar2Tk(canvas, toolbar_frame)
        toolbar.update()

        # Add control buttons
        button_frame = ttk.Frame(container)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(button_frame, text="💾 Save Chart",
                  command=lambda: self._save_chart(fig)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="📧 Email Chart",
                  command=lambda: self._email_chart(fig)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="🖨️ Print",
                  command=lambda: self._print_chart()).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="❌ Close",
                  command=self.window.destroy).pack(side=tk.RIGHT, padx=5)

        self.canvas = canvas
        self.fig = fig

    def _save_chart(self, fig: Figure):
        """Save chart to file"""
        from tkinter import filedialog, messagebox

        filename = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[
                ("PNG Image", "*.png"),
                ("PDF Document", "*.pdf"),
                ("SVG Vector", "*.svg"),
                ("JPEG Image", "*.jpg")
            ]
        )

        if filename:
            try:
                fig.savefig(filename, dpi=300, bbox_inches='tight', facecolor='white')
                messagebox.showinfo("Success", f"Chart saved to:\n{filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save chart:\n{str(e)}")

    def _email_chart(self, fig: Figure):
        """Email chart to administrator"""
        from tkinter import messagebox, simpledialog

        if not EMAIL_AVAILABLE:
            messagebox.showerror("Email Unavailable",
                               "Email service is not available.\n"
                               "Please ensure the email infrastructure is configured.")
            return

        # Create email dialog
        email_dialog = tk.Toplevel(self.window)
        email_dialog.title("📧 Email Chart to Administrator")
        email_dialog.geometry("500x350")
        email_dialog.transient(self.window)
        email_dialog.grab_set()

        frame = ttk.Frame(email_dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        # Title
        ttk.Label(frame, text="Email Chart to Administrator",
                 font=('Arial', 12, 'bold')).pack(pady=(0, 20))

        # Recipient email
        ttk.Label(frame, text="Recipient Email Address:").pack(anchor=tk.W, pady=(0, 5))
        email_var = tk.StringVar(value="admin@university.edu")
        email_entry = ttk.Entry(frame, textvariable=email_var, width=50)
        email_entry.pack(fill=tk.X, pady=(0, 15))
        email_entry.focus()

        # Custom message (optional)
        ttk.Label(frame, text="Custom Message (optional):").pack(anchor=tk.W, pady=(0, 5))
        message_text = tk.Text(frame, height=6, width=50, wrap=tk.WORD)
        message_text.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        message_text.insert('1.0', f"Please find attached the chart: {self.chart_title}\n\nGenerated from Advanced Search GUI.")

        # Status label
        status_var = tk.StringVar(value="")
        status_label = ttk.Label(frame, textvariable=status_var, foreground="blue")
        status_label.pack(pady=(0, 10))

        def send_chart():
            """Send the chart via email"""
            recipient = email_var.get().strip()
            custom_message = message_text.get('1.0', tk.END).strip()

            if not recipient:
                messagebox.showerror("Error", "Please enter a recipient email address.")
                return

            # Validate email format
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, recipient):
                messagebox.showerror("Error", f"Invalid email format: {recipient}")
                return

            # Disable send button and show status
            send_btn.config(state='disabled')
            status_var.set("Sending email...")
            email_dialog.update()

            # Use ChartGenerator to send email
            chart_gen = ChartGenerator()
            result = chart_gen.email_chart(
                fig=fig,
                recipient_email=recipient,
                chart_title=self.chart_title,
                message=custom_message if custom_message else None
            )

            if result:
                status_var.set("✓ Email sent successfully!")
                messagebox.showinfo("Success",
                                   f"Chart emailed successfully to:\n{recipient}\n\n"
                                   f"Chart: {self.chart_title}\n"
                                   f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                email_dialog.destroy()
            else:
                status_var.set("✗ Failed to send email")
                send_btn.config(state='normal')
                messagebox.showerror("Error",
                                   f"Failed to send email to {recipient}.\n"
                                   "Please check the email service configuration.")

        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X)

        send_btn = ttk.Button(button_frame, text="📧 Send Email", command=send_chart)
        send_btn.pack(side=tk.LEFT, padx=5)

        ttk.Button(button_frame, text="❌ Cancel",
                  command=email_dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def _print_chart(self):
        """Print chart (placeholder)"""
        from tkinter import messagebox
        messagebox.showinfo("Print", "Print functionality would open system print dialog.\n"
                           "You can save the chart and print from an image viewer instead.")


class DatabaseChartGenerator:
    """Generate charts directly from database queries"""

    def __init__(self):
        """Initialize database chart generator"""
        self.chart_gen = ChartGenerator()

    def generate_age_distribution(self) -> Optional[Figure]:
        """Generate age distribution histogram"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT age FROM students WHERE age IS NOT NULL ORDER BY age")
            ages = [row[0] for row in cursor.fetchall()]
            conn.close()

            if not ages:
                return None

            data = {
                'values': ages,
                'bins': 20,
                'xlabel': 'Age',
                'ylabel': 'Number of Students',
                'color': 'steelblue'
            }

            return self.chart_gen.generate_chart('histogram', data,
                                                 'Student Age Distribution')
        except Exception as e:
            print(f"Error generating age distribution: {e}")
            return None

    def generate_course_distribution(self) -> Optional[Figure]:
        """Generate course distribution pie chart"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT course, COUNT(*)
                FROM students
                WHERE course IS NOT NULL
                GROUP BY course
                ORDER BY COUNT(*) DESC
            """)
            results = cursor.fetchall()
            conn.close()

            if not results:
                return None

            labels = [row[0] for row in results]
            sizes = [row[1] for row in results]

            data = {
                'labels': labels,
                'sizes': sizes
            }

            return self.chart_gen.generate_chart('pie', data,
                                                 'Course Distribution')
        except Exception as e:
            print(f"Error generating course distribution: {e}")
            return None

    def generate_registration_timeline(self) -> Optional[Figure]:
        """Generate registration timeline"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT strftime('%Y-%m', registration_datetime) as month, COUNT(*)
                FROM students
                WHERE registration_datetime IS NOT NULL
                GROUP BY month
                ORDER BY month
            """)
            results = cursor.fetchall()
            conn.close()

            if not results:
                return None

            months = [row[0] for row in results]
            counts = [row[1] for row in results]

            data = {
                'x': list(range(len(months))),
                'y': counts,
                'xlabel': 'Month',
                'ylabel': 'Registrations',
                'color': 'steelblue'
            }

            fig = self.chart_gen.generate_chart('line', data,
                                                'Registration Timeline')

            # Update x-axis labels
            if fig:
                ax = fig.axes[0]
                ax.set_xticks(range(len(months)))
                ax.set_xticklabels(months, rotation=45, ha='right')

            return fig
        except Exception as e:
            print(f"Error generating registration timeline: {e}")
            return None

    def generate_gender_course_distribution(self) -> Optional[Figure]:
        """Generate gender-course grouped bar chart"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT course, gender, COUNT(*)
                FROM students
                WHERE course IS NOT NULL AND gender IS NOT NULL
                GROUP BY course, gender
                ORDER BY course, gender
            """)
            results = cursor.fetchall()
            conn.close()

            if not results:
                return None

            # Organize data by course and gender
            courses = []
            gender_data = {}

            for course, gender, count in results:
                if course not in courses:
                    courses.append(course)
                if gender not in gender_data:
                    gender_data[gender] = {}
                gender_data[gender][course] = count

            # Convert to format needed for grouped bar chart
            groups = {}
            for gender, course_counts in gender_data.items():
                groups[gender.title()] = [course_counts.get(c, 0) for c in courses]

            data = {
                'labels': courses,
                'groups': groups,
                'xlabel': 'Course',
                'ylabel': 'Number of Students'
            }

            return self.chart_gen.generate_chart('grouped_bar', data,
                                                 'Gender Distribution by Course')
        except Exception as e:
            print(f"Error generating gender-course distribution: {e}")
            return None

    def generate_module_popularity(self) -> Optional[Figure]:
        """Generate module popularity bar chart"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT module_code, COUNT(*) as enrollment_count
                FROM student_modules
                WHERE module_code IS NOT NULL
                GROUP BY module_code
                ORDER BY enrollment_count DESC
                LIMIT 15
            """)
            results = cursor.fetchall()
            conn.close()

            if not results:
                return None

            modules = [row[0] for row in results]
            counts = [row[1] for row in results]

            data = {
                'labels': modules,
                'values': counts,
                'xlabel': 'Module Code',
                'ylabel': 'Enrollments',
                'color': 'coral'
            }

            return self.chart_gen.generate_chart('bar', data,
                                                 'Top 15 Most Popular Modules')
        except Exception as e:
            print(f"Error generating module popularity: {e}")
            return None

    def generate_grade_distribution(self) -> Optional[Figure]:
        """Generate grade distribution bar chart"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT grade, COUNT(*)
                FROM student_modules
                WHERE grade IS NOT NULL
                GROUP BY grade
                ORDER BY grade
            """)
            results = cursor.fetchall()
            conn.close()

            if not results:
                return None

            grades = [row[0] for row in results]
            counts = [row[1] for row in results]

            data = {
                'labels': grades,
                'values': counts,
                'xlabel': 'Grade',
                'ylabel': 'Number of Students',
                'color': 'mediumseagreen'
            }

            return self.chart_gen.generate_chart('bar', data,
                                                 'Overall Grade Distribution')
        except Exception as e:
            print(f"Error generating grade distribution: {e}")
            return None


# Convenience functions
def create_chart_viewer(parent, chart_type: str, db_generator: DatabaseChartGenerator = None):
    """
    Create and show chart viewer window

    Args:
        parent: Parent tkinter window
        chart_type: Type of chart to generate
        db_generator: DatabaseChartGenerator instance (creates new if None)
    """
    if not CHARTS_AVAILABLE:
        from tkinter import messagebox
        messagebox.showerror("Charts Unavailable",
                           "Chart generation requires matplotlib and seaborn.\n"
                           "Install with: pip install matplotlib seaborn")
        return

    if db_generator is None:
        db_generator = DatabaseChartGenerator()

    # Generate appropriate chart
    fig = None
    title = ""
    chart_title = ""

    if chart_type == "age_histogram":
        fig = db_generator.generate_age_distribution()
        title = "Age Distribution"
        chart_title = "Student_Age_Distribution"
    elif chart_type == "course_pie":
        fig = db_generator.generate_course_distribution()
        title = "Course Distribution"
        chart_title = "Course_Enrollment_Distribution"
    elif chart_type == "registration_timeline":
        fig = db_generator.generate_registration_timeline()
        title = "Registration Timeline"
        chart_title = "Registration_Timeline"
    elif chart_type == "gender_course":
        fig = db_generator.generate_gender_course_distribution()
        title = "Gender-Course Distribution"
        chart_title = "Gender_Course_Distribution"
    elif chart_type == "module_popularity":
        fig = db_generator.generate_module_popularity()
        title = "Module Popularity"
        chart_title = "Module_Popularity"
    elif chart_type == "grade_distribution":
        fig = db_generator.generate_grade_distribution()
        title = "Grade Distribution"
        chart_title = "Grade_Distribution"

    if fig:
        ChartViewer(parent, fig, f"📊 {title}", chart_title=chart_title)
    else:
        from tkinter import messagebox
        messagebox.showwarning("No Data",
                             f"No data available to generate {title} chart.\n"
                             "Please ensure the database contains relevant data.")


def get_admin_emails() -> List[str]:
    """
    Get list of administrator email addresses from database

    Returns:
        List of admin email addresses
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT email FROM users
            WHERE role = 'admin' AND email IS NOT NULL
            ORDER BY email
        """)
        results = cursor.fetchall()
        conn.close()

        return [row[0] for row in results if row[0]]
    except Exception as e:
        print(f"Error getting admin emails: {e}")
        return ["admin@university.edu"]  # Default fallback
