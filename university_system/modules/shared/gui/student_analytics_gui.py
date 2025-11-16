from university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import threading
import queue
import sys
from datetime import datetime
import os
from university_system.modules.shared.services.analytics.student_analytics import StudentAnalytics
from university_system.infrastructure.auth.user_authentication import UserAuth
import pandas as pd
import json
import matplotlib.pyplot as plt
import numpy as np
import json
import warnings
from scipy import stats
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, r2_score
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.naive_bayes import GaussianNB
from sklearn.decomposition import PCA
from sklearn.ensemble import RandomForestRegressor
import openpyxl
from openpyxl.styles import Font, Fill, PatternFill, Alignment
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

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

def configure_matplotlib():
    """Configure matplotlib backend with proper GUI support"""
    try:
        import matplotlib
        matplotlib.use('TkAgg')
        return True
    except:
        try:
            matplotlib.use('Agg')
            return False
        except:
            return False

class GUIStudentAnalytics:
    """GUI wrapper for the existing StudentAnalytics class"""

    def __init__(self, root=None, auth_manager=None):
        # Accept root window or create new one
        self.root = root if root else tk.Tk()
        self.root.title("Enhanced Student Analytics Dashboard")
        self.root.geometry("1400x900")

        # Initialize database paths
        import os
        from university_system.modules.shared.constants import paths
        self.db_path = str(paths.DEFAULT_DB_PATH)
        self.custom_filters = {}
        self.plots_dir = str(paths.ANALYTICS_PLOTS_DIR)
        self.reports_dir = str(paths.REPORTS_DIR)
        self.create_directories()

        # Import the original StudentAnalytics class
        # Pass gui_mode=True to prevent CLI output and enable GUI display
        self.analytics = StudentAnalytics(gui_mode=True)

        # Set auth context if provided
        self.auth = auth_manager

        # Queue for thread communication
        self.output_queue = queue.Queue()

        # Setup GUI components
        self.setup_styles()
        self.create_main_interface()
        self.setup_output_capture()

        # Start output monitoring
        self.monitor_output()

        # Register cleanup on window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        """Clean up matplotlib figures before closing"""
        try:
            import matplotlib.pyplot as plt
            plt.close('all')  # Close all matplotlib figures
        except:
            pass
        finally:
            self.root.destroy()

    def create_directories(self):
        """Create necessary directories for outputs"""
        import os
        os.makedirs(self.plots_dir, exist_ok=True)
        os.makedirs(self.reports_dir, exist_ok=True)

    def get_connection(self):
        """Get database connection"""
        from university_system.infrastructure.database.db import sqlite3
        return sqlite3.connect(str(DEFAULT_DB_PATH))

    def get_all_students(self, filters=None):
        """Get all students data with optional filters"""
        from university_system.infrastructure.database.db import sqlite3
        import pandas as pd
        try:
            conn = self.get_connection()
            query = "SELECT * FROM students"
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            if df.empty:
                return df
                
            # Simulate additional data if needed
            df = self.simulate_additional_data(df)
            
            # Apply filters if provided
            if filters or self.custom_filters:
                all_filters = {**(filters or {}), **self.custom_filters}
                df = self.apply_filters(df, all_filters)
                
            return df
        except Exception as e:
            print(f"Error loading students: {e}")
            return pd.DataFrame()

    def display_results_window(self, title, summary_text, figure=None):
        """Display analysis results in a GUI window with action buttons"""
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("900x700")
        dialog.transient(self.root)

        def on_dialog_close():
            """Clean up figure when dialog closes"""
            try:
                if figure:
                    plt.close(figure)
            except:
                pass
            dialog.destroy()

        dialog.protocol("WM_DELETE_WINDOW", on_dialog_close)

        # Create main frame
        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(main_frame, text=title, font=('Arial', 16, 'bold'))
        title_label.pack(pady=(0, 10))

        # Text results frame
        text_frame = ttk.LabelFrame(main_frame, text="Analysis Results", padding="10")
        text_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Scrolled text widget
        text_widget = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD, height=15, font=('Courier', 10))
        text_widget.pack(fill=tk.BOTH, expand=True)
        text_widget.insert('1.0', summary_text)
        text_widget.config(state='disabled')

        # Action buttons frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(button_frame, text="📊 View Chart",
                  command=lambda: plt.show() if figure else None).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="💾 Save Report",
                  command=lambda: self.save_analysis_report(title, summary_text, figure)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="📋 Copy to Clipboard",
                  command=lambda: self.copy_to_clipboard(summary_text)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="📧 Email Report",
                  command=lambda: self.email_report(title, summary_text)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="👤 Send to Admin",
                  command=lambda: self.send_to_admin(title, summary_text)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="✖ Close",
                  command=on_dialog_close).pack(side=tk.RIGHT, padx=5)

    def send_to_admin(self, title, summary_text):
        """Quick send report to admin email"""
        try:
            from university_system.infrastructure.database.db import get_db_connection

            # Get admin email
            admin_email = "admin@university.edu"  # Default
            try:
                with get_db_connection() as conn:
                    cursor = conn.execute("""
                        SELECT email FROM users
                        WHERE role = 'admin'
                        LIMIT 1
                    """)
                    admin_row = cursor.fetchone()
                    if admin_row and admin_row[0]:
                        admin_email = admin_row[0]
            except:
                pass

            # Confirm before sending
            if messagebox.askyesno("Confirm Send",
                                  f"Send this report to admin at {admin_email}?"):
                self._send_report_email(admin_email, title, summary_text)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to send to admin: {e}")

    def copy_to_clipboard(self, text):
        """Copy text to clipboard"""
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        messagebox.showinfo("Success", "Results copied to clipboard!")

    def save_analysis_report(self, title, summary_text, figure=None):
        """Save analysis report to file"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("PDF files", "*.pdf"), ("All files", "*.*")],
            title="Save Analysis Report"
        )
        if filename:
            try:
                with open(filename, 'w') as f:
                    f.write(f"{title}\n")
                    f.write("="*80 + "\n\n")
                    f.write(summary_text)
                    f.write(f"\n\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                messagebox.showinfo("Success", f"Report saved to {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save report: {e}")

    def email_report(self, title, summary_text, recipient=None):
        """Send report via email to admin or specified recipient"""
        try:
            from university_system.infrastructure.database.db import get_db_connection

            # If no recipient specified, get admin email from database
            if not recipient:
                # Create dialog to select recipient
                email_dialog = tk.Toplevel(self.root)
                email_dialog.title("Email Report")
                email_dialog.geometry("500x250")
                email_dialog.transient(self.root)
                email_dialog.grab_set()

                main_frame = ttk.Frame(email_dialog, padding="20")
                main_frame.pack(fill=tk.BOTH, expand=True)

                ttk.Label(main_frame, text="Send Report To:", font=('Arial', 12, 'bold')).pack(pady=(0, 10))

                # Radio buttons for recipient selection
                recipient_var = tk.StringVar(value="admin")

                # Get admin email
                admin_email = "admin@university.edu"  # Default
                try:
                    with get_db_connection() as conn:
                        cursor = conn.execute("""
                            SELECT email FROM users
                            WHERE role = 'admin'
                            LIMIT 1
                        """)
                        admin_row = cursor.fetchone()
                        if admin_row and admin_row[0]:
                            admin_email = admin_row[0]
                except:
                    pass

                ttk.Radiobutton(main_frame, text=f"Admin ({admin_email})",
                               variable=recipient_var, value="admin").pack(anchor=tk.W, pady=5)
                ttk.Radiobutton(main_frame, text="Current User",
                               variable=recipient_var, value="self").pack(anchor=tk.W, pady=5)
                ttk.Radiobutton(main_frame, text="Custom Email:",
                               variable=recipient_var, value="custom").pack(anchor=tk.W, pady=5)

                custom_email_entry = ttk.Entry(main_frame, width=40)
                custom_email_entry.pack(pady=5, padx=20)

                def send_email():
                    choice = recipient_var.get()

                    if choice == "admin":
                        final_recipient = admin_email
                    elif choice == "self":
                        # Get current user email
                        try:
                            from university_system.infrastructure.shared_context import get_auth
                            auth = get_auth()
                            if auth.current_user:
                                user = auth.current_user
                                final_recipient = user.get('email', '')
                                if not final_recipient:
                                    messagebox.showerror("Error", "Current user has no email address")
                                    return
                            else:
                                messagebox.showerror("Error", "No user logged in")
                                return
                        except Exception as e:
                            messagebox.showerror("Error", f"Failed to get user email: {e}")
                            return
                    else:  # custom
                        final_recipient = custom_email_entry.get().strip()
                        if not final_recipient:
                            messagebox.showerror("Error", "Please enter an email address")
                            return

                    # Send the email
                    self._send_report_email(final_recipient, title, summary_text)
                    email_dialog.destroy()

                button_frame = ttk.Frame(main_frame)
                button_frame.pack(pady=20)

                ttk.Button(button_frame, text="Send", command=send_email).pack(side=tk.LEFT, padx=5)
                ttk.Button(button_frame, text="Cancel", command=email_dialog.destroy).pack(side=tk.LEFT, padx=5)

            else:
                # Direct send to specified recipient
                self._send_report_email(recipient, title, summary_text)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to prepare email: {e}")

    def _send_report_email(self, recipient, title, summary_text):
        """Actually send the email report"""
        try:
            from university_system.infrastructure.email.email_service import send_email
            from datetime import datetime

            # Build email body
            email_body = f"""
Analytics Report: {title}
{'='*80}

{summary_text}

{'='*80}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
This is an automated report from the University Management System.
"""

            # Send email immediately using the email service
            subject = f"Analytics Report: {title}"
            success = send_email(recipient, subject, email_body)

            if success:
                messagebox.showinfo("Success",
                                  f"Report has been sent successfully to {recipient}")
            else:
                messagebox.showwarning("Warning",
                                     f"Email was logged but may not have been sent.\n"
                                     f"Check email configuration and logs.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to send email: {e}\n\n"
                               f"Please check email system configuration.")

    def simulate_additional_data(self, df):
        """Add only missing essential columns based on actual database data"""
        import numpy as np
        import pandas as pd
        from datetime import datetime, timedelta

        # Only add columns if they're truly missing from database
        # Try to derive from existing data rather than simulate

        if 'gpa' not in df.columns and 'grade' in df.columns:
            # Calculate GPA from grades if possible
            grade_map = {'A': 4.0, 'B': 3.0, 'C': 2.0, 'D': 1.0, 'F': 0.0}
            df['gpa'] = df['grade'].map(grade_map).fillna(3.0)

        if 'completion_status' not in df.columns and 'status' in df.columns:
            # Use existing status column
            df['completion_status'] = df['status']
        elif 'completion_status' not in df.columns:
            # Default to Active if no status
            df['completion_status'] = 'Active'

        return df

    def get_all_modules(self, filters=None):
        """Get all modules data with optional filters"""
        from university_system.infrastructure.database.db import sqlite3
        import pandas as pd
        
        conn = None
        try:
            conn = self.get_connection()
            query = "SELECT * FROM modules"
            df = pd.read_sql_query(query, conn)
        except sqlite3.Error as e:
            # If modules table doesn't exist, create sample data
            print(f"Database error loading modules: {e}")
            df = pd.DataFrame()
        except Exception as e:
            # Other errors
            print(f"Error loading modules: {e}")
            df = pd.DataFrame()
        finally:
            if conn:
                conn.close()
            
        if df.empty:
            df = self.simulate_module_data(df)
            
        if filters or self.custom_filters:
            all_filters = {**(filters or {}), **self.custom_filters}
            df = self.apply_filters(df, all_filters)
            
        return df

    def analyze_module_difficulty(self):
        """Analyze module difficulty and performance metrics - GUI compatible"""
        modules_df = self.get_all_modules(self.custom_filters)
        
        if modules_df.empty:
            print("No module data available for difficulty analysis.")
            return
        
        print("\nGenerating Module Difficulty Analysis...")
        
        # Calculate difficulty metrics
        module_stats = modules_df.groupby('module_name').agg({
            'module_grade': lambda x: (x.isin(['A', 'B'])).mean() * 100,  # Pass rate
            'difficulty_rating': 'mean',
            'attendance_rate': 'mean',
            'module_completion': lambda x: (x == 'Completed').mean() * 100,
            'student_id': 'count'  # Enrollment count
        }).round(2)
        
        module_stats.columns = ['Pass_Rate', 'Avg_Difficulty', 'Avg_Attendance', 'Completion_Rate', 'Enrollment']
        
        # Calculate overall difficulty score
        module_stats['Difficulty_Score'] = (
            (5 - module_stats['Avg_Difficulty']) * 0.3 +  # Lower difficulty rating = higher score
            module_stats['Pass_Rate'] * 0.4 +  # Higher pass rate = higher score
            module_stats['Completion_Rate'] * 0.3  # Higher completion rate = higher score
        ) / 100 * 5  # Normalize to 1-5 scale
        
        fig = plt.figure(figsize=(20, 15))
        fig.suptitle('Module Difficulty Analysis', fontsize=20)
        
        # 1. Module Difficulty vs Pass Rate
        ax1 = fig.add_subplot(331)
        scatter = ax1.scatter(module_stats['Avg_Difficulty'], module_stats['Pass_Rate'], 
                             s=module_stats['Enrollment']*10, alpha=0.6, c=module_stats['Completion_Rate'], 
                             cmap='RdYlBu_r')
        ax1.set_xlabel('Average Difficulty Rating')
        ax1.set_ylabel('Pass Rate (%)')
        ax1.set_title('Difficulty vs Pass Rate (sized by enrollment)')
        plt.colorbar(scatter, ax=ax1, label='Completion Rate (%)')
        
        # Continue with other subplots...
        plt.tight_layout(rect=[0, 0, 1, 0.95])
        
        # Print detailed analysis
        print("\n" + "="*60)
        print("MODULE DIFFICULTY ANALYSIS SUMMARY")
        print("="*60)
        
        print(f"Total modules analyzed: {len(module_stats)}")
        print(f"Average pass rate across all modules: {module_stats['Pass_Rate'].mean():.1f}%")
        print(f"Average difficulty rating: {module_stats['Avg_Difficulty'].mean():.1f}/5")
        print(f"Average completion rate: {module_stats['Completion_Rate'].mean():.1f}%")
        
        self.save_or_display_plot(fig, "module_difficulty_analysis")

    def analyze_performance_trends(self):
        """Analyze student performance trends over time - GUI compatible"""
        students_df = self.get_all_students(self.custom_filters)
        
        if students_df.empty:
            print("No student data available for performance trend analysis.")
            return
        
        # Clean data and handle missing values
        students_df = students_df.dropna(subset=['registration_datetime', 'gpa'])
        
        if students_df.empty:
            print("No valid registration or GPA data available for trend analysis.")
            return
        
        print("\nGenerating Performance Trends Analysis...")
        
        # Prepare time-based data with error handling
        try:
            students_df['registration_date'] = pd.to_datetime(students_df['registration_datetime'])
            students_df['year_month'] = students_df['registration_date'].dt.to_period('M')
        except Exception as e:
            print(f"Error processing dates: {e}")
            return
        
        # Remove any rows with invalid dates
        students_df = students_df.dropna(subset=['year_month'])
        
        if students_df.empty:
            print("No valid date data available for trend analysis.")
            return
        
        fig = plt.figure(figsize=(20, 15))
        fig.suptitle('Student Performance Trends Analysis', fontsize=20)
        
        # 1. GPA Trends Over Time
        ax1 = fig.add_subplot(331)
        monthly_gpa = students_df.groupby('year_month')['gpa'].mean().dropna()
        
        if len(monthly_gpa) > 0:
            ax1.plot(range(len(monthly_gpa)), monthly_gpa.values, marker='o', 
                    color=CONFIG['colors'][0], linewidth=2)
            ax1.set_xlabel('Time Period')
            ax1.set_ylabel('Average GPA')
            ax1.set_title('GPA Trends Over Time')
            
            # Set x-axis labels with proper bounds checking
            if len(monthly_gpa) > 1:
                step = max(1, len(monthly_gpa) // 5)
                tick_positions = list(range(0, len(monthly_gpa), step))
                if tick_positions[-1] != len(monthly_gpa) - 1:
                    tick_positions.append(len(monthly_gpa) - 1)
                ax1.set_xticks(tick_positions)
                ax1.set_xticklabels([str(monthly_gpa.index[i]) for i in tick_positions], rotation=45)
            
            # Add trend line only if we have enough data points
            if len(monthly_gpa) > 2:
                try:
                    z = np.polyfit(range(len(monthly_gpa)), monthly_gpa.values, 1)
                    p = np.poly1d(z)
                    ax1.plot(range(len(monthly_gpa)), p(range(len(monthly_gpa))), 
                            "r--", alpha=0.8, label=f'Trend: {z[0]:.4f}/month')
                    ax1.legend()
                except:
                    pass  # Skip trend line if fitting fails
        else:
            ax1.text(0.5, 0.5, 'No valid GPA data', ha='center', va='center', transform=ax1.transAxes)
            ax1.set_title('GPA Trends Over Time (No Data)')
        
        # Continue with other trend analyses...
        plt.tight_layout(rect=[0, 0, 1, 0.95])
        
        # Print detailed performance trends summary
        print("\n" + "="*60)
        print("PERFORMANCE TRENDS SUMMARY")
        print("="*60)
        
        if len(monthly_gpa) > 0:
            print(f"Analysis Period: {monthly_gpa.index[0]} to {monthly_gpa.index[-1]}")
            print(f"Number of periods analyzed: {len(monthly_gpa)}")
        
        self.save_or_display_plot(fig, "performance_trends")

    def analyze_cohorts(self):
        """Analyze student cohorts and retention patterns - GUI compatible"""
        students_df = self.get_all_students(self.custom_filters)
        
        if students_df.empty:
            print("No student data available for cohort analysis.")
            return
        
        print("\nGenerating Cohort Analysis...")
        
        # Create cohorts based on registration date
        students_df['registration_date'] = pd.to_datetime(students_df['registration_datetime'])
        students_df['cohort_month'] = students_df['registration_date'].dt.to_period('M')
        
        # Define current date for analysis
        current_date = students_df['registration_date'].max()
        students_df['months_since_registration'] = (
            (current_date - students_df['registration_date']).dt.days / 30.44
        ).round().astype(int)
        
        fig = plt.figure(figsize=(20, 15))
        fig.suptitle('Student Cohort Analysis', fontsize=20)
        
        # 1. Cohort Size Over Time
        ax1 = fig.add_subplot(331)
        cohort_sizes = students_df.groupby('cohort_month').size()
        ax1.plot(range(len(cohort_sizes)), cohort_sizes.values, marker='o', color=CONFIG['colors'][0])
        ax1.set_xlabel('Cohort Period')
        ax1.set_ylabel('Number of Students')
        ax1.set_title('Cohort Size Over Time')
        
        # Continue with other cohort analyses...
        plt.tight_layout(rect=[0, 0, 1, 0.95])
        
        # Print detailed cohort analysis
        print("\n" + "="*60)
        print("COHORT ANALYSIS SUMMARY")
        print("="*60)
        
        print(f"Total cohorts analyzed: {len(cohort_sizes)}")
        print(f"Average cohort size: {cohort_sizes.mean():.1f} students")
        
        self.save_or_display_plot(fig, "cohort_analysis")

    def analyze_correlations(self):
        """Perform comprehensive correlation analysis - GUI compatible"""
        students_df = self.get_all_students(self.custom_filters)
        
        if students_df.empty:
            print("No student data available for correlation analysis.")
            return
        
        # Clean data and ensure we have enough data points
        students_df = students_df.dropna(subset=['gpa'])
        
        if len(students_df) < 2:
            print("Insufficient data for correlation analysis (need at least 2 data points).")
            return
        
        print("\nGenerating Correlation Analysis...")
        
        # Prepare numerical data for correlation with validation
        numeric_cols = []
        if 'age' in students_df.columns and not students_df['age'].isna().all():
            numeric_cols.append('age')
        if 'gpa' in students_df.columns and not students_df['gpa'].isna().all():
            numeric_cols.append('gpa')
        if 'engagement_score' in students_df.columns and not students_df['engagement_score'].isna().all():
            numeric_cols.append('engagement_score')
        
        if len(numeric_cols) < 2:
            print("Insufficient numerical columns for correlation analysis.")
            return
        
        fig = plt.figure(figsize=(20, 15))
        fig.suptitle('Comprehensive Correlation Analysis', fontsize=20)
        
        # Create correlation matrix
        correlation_data = students_df[numeric_cols].dropna()
        correlation_matrix = correlation_data.corr()
        
        # 1. Main Correlation Heatmap
        ax1 = fig.add_subplot(331)
        im1 = ax1.imshow(correlation_matrix, cmap='RdBu_r', aspect='auto', vmin=-1, vmax=1)
        ax1.set_xticks(range(len(numeric_cols)))
        ax1.set_yticks(range(len(numeric_cols)))
        ax1.set_xticklabels(numeric_cols, rotation=45, ha='right')
        ax1.set_yticklabels(numeric_cols)
        ax1.set_title('Correlation Matrix')
        plt.colorbar(im1, ax=ax1)
        
        # Continue with other correlation analyses...
        plt.tight_layout(rect=[0, 0, 1, 0.95])
        
        print("\n" + "="*60)
        print("CORRELATION ANALYSIS SUMMARY")
        print("="*60)
        
        self.save_or_display_plot(fig, "correlation_analysis")

    def predictive_analytics(self):
        """Perform predictive analytics using machine learning - GUI compatible"""
        students_df = self.get_all_students(self.custom_filters)
        
        if students_df.empty or len(students_df) < 50:  # Need sufficient data for ML
            print("Insufficient data for predictive analytics (minimum 50 students required).")
            return
        
        print("\nGenerating Predictive Analytics...")
        
        # Prepare data for machine learning
        students_df['high_performer'] = (students_df['gpa'] >= 3.5).astype(int)
        students_df['at_risk'] = ((students_df['gpa'] < 2.0) | (students_df['engagement_score'] < 30)).astype(int)
        
        # Prepare features
        feature_columns = ['age', 'engagement_score']
        students_df['gender_encoded'] = pd.Categorical(students_df['gender']).codes
        students_df['course_encoded'] = pd.Categorical(students_df['course']).codes
        feature_columns.extend(['gender_encoded', 'course_encoded'])
        
        X = students_df[feature_columns].fillna(0)
        
        fig = plt.figure(figsize=(20, 15))
        fig.suptitle('Predictive Analytics Dashboard', fontsize=20)
        
        # Machine learning models and visualizations here...
        plt.tight_layout(rect=[0, 0, 1, 0.95])
        
        print("\n" + "="*60)
        print("PREDICTIVE ANALYTICS SUMMARY")
        print("="*60)
        
        self.save_or_display_plot(fig, "predictive_analytics")

    def custom_report_builder(self):
        """Custom report builder for GUI"""
        print("Custom report builder would open a dialog in GUI version")
        # This would trigger the CustomReportDialog in GUI

    def export_data(self):
        """Export data functionality for GUI"""
        print("Export data would open export dialog in GUI version")
        # This would trigger export dialogs in GUI

    def email_reports(self):
        """Email reports functionality for GUI"""
        print("Email functionality would be implemented here")
        print("This requires SMTP configuration and recipient setup")

    def data_quality_check(self):
        """Perform data quality check - GUI compatible"""
        print("Performing data quality check...")
        
        students_df = self.get_all_students()
        modules_df = self.get_all_modules()
        
        print(f"\nData Quality Report:")
        print(f"Students table: {len(students_df)} records")
        
        if not students_df.empty:
            # Check for missing values
            missing_data = students_df.isnull().sum()
            if missing_data.sum() > 0:
                print("Missing data found:")
                for col, count in missing_data.items():
                    if count > 0:
                        print(f"  {col}: {count} missing values")
            else:
                print("No missing data found in students table")
        
        print(f"Modules table: {len(modules_df)} records")
        print("Data quality check completed")

    def advanced_filtering(self):
        """Advanced filtering options - GUI compatible"""
        print("Advanced filtering options:")
        print("1. Age range filtering")
        print("2. GPA range filtering") 
        print("3. Course-specific filtering")
        print("4. Gender-based filtering")
        print("5. Engagement score filtering")
        print("Use the GUI filter dialog for interactive filtering")

    def configuration_settings(self):
        """Configuration settings - GUI compatible"""
        print("Configuration settings available:")
        print("- Plot dimensions and DPI")
        print("- Export formats")
        print("- Email settings")
        print("- Color schemes")
        print("Use the GUI configuration dialog for settings management")

    def generate_complete_report(self):
        """Generate a complete comprehensive report"""
        print("Generating complete analytics report...")
        
        try:
            # Run all major analyses
            print("Running demographic analysis...")
            self.analyze_student_demographics()
            
            print("Running grade distribution analysis...")
            self.analyze_grade_distribution()
            
            print("Running course enrollment analysis...")
            self.analyze_course_enrollments()
            
            print("Running performance trends analysis...")
            self.analyze_performance_trends()
            
            print("Running risk assessment...")
            self.analyze_academic_risk()
            
            print("Running module popularity analysis...")
            self.analyze_module_popularity()
            
            print("Running engagement analysis...")
            self.analyze_engagement()
            
            print("Complete report generation finished!")
            print("Check the plots and reports directories for outputs")
            
        except Exception as e:
            print(f"Error generating complete report: {e}")

    def run_module_difficulty(self):
        self.run_analysis_thread(self.analyze_module_difficulty, "Module Difficulty")
        
    def run_performance_trends(self):
        self.run_analysis_thread(self.analyze_performance_trends, "Performance Trends")

    def run_correlations(self):
        self.run_analysis_thread(self.analyze_correlations, "Correlation Analysis")
        
    def run_cohorts(self):
        self.run_analysis_thread(self.analyze_cohorts, "Cohort Analysis")
        
    def run_engagement(self):
        self.run_analysis_thread(self.analyze_engagement, "Engagement Analysis")
        
    def run_predictive(self):
        self.run_analysis_thread(self.predictive_analytics, "Predictive Analytics")

    def send_email_with_attachment(self, recipient, subject, report_type):
        """Send email with attachment - GUI compatible stub"""
        print(f"Would send {report_type} report to {recipient} with subject: {subject}")
        # Implementation would go here

    def generate_statistical_summary_report(self, students_df, modules_df, timestamp):
        """Generate statistical summary report"""
        import pandas as pd
        
        filename = f"{self.reports_dir}/statistical_summary_{timestamp}.txt"
        
        try:
            with open(filename, 'w') as f:
                f.write("STATISTICAL SUMMARY REPORT\n")
                f.write("="*50 + "\n\n")
                
                # Students summary
                f.write("STUDENT STATISTICS\n")
                f.write("-"*20 + "\n")
                f.write(f"Total Students: {len(students_df)}\n")
                
                if 'gpa' in students_df.columns:
                    f.write(f"Average GPA: {students_df['gpa'].mean():.2f}\n")
                    f.write(f"GPA Std Dev: {students_df['gpa'].std():.2f}\n")
                    f.write(f"Min GPA: {students_df['gpa'].min():.2f}\n")
                    f.write(f"Max GPA: {students_df['gpa'].max():.2f}\n")
                
                if 'age' in students_df.columns:
                    f.write(f"Average Age: {students_df['age'].mean():.1f}\n")
                    f.write(f"Age Range: {students_df['age'].min()}-{students_df['age'].max()}\n")
                
                if 'engagement_score' in students_df.columns:
                    f.write(f"Average Engagement: {students_df['engagement_score'].mean():.1f}\n")
                
                # Modules summary
                f.write(f"\nMODULE STATISTICS\n")
                f.write("-"*20 + "\n")
                f.write(f"Total Modules: {len(modules_df)}\n")
                
                if 'enrollment_count' in modules_df.columns:
                    f.write(f"Total Enrollments: {modules_df['enrollment_count'].sum()}\n")
                    f.write(f"Avg Enrollment per Module: {modules_df['enrollment_count'].mean():.1f}\n")
            
            print(f"Statistical summary saved: {filename}")
            
        except Exception as e:
            print(f"Error generating statistical summary: {e}")

    def simulate_module_data(self, df):
        """Simulate module data if not available"""
        import pandas as pd
        import numpy as np
        
        modules = ['Mathematics', 'Physics', 'Chemistry', 'Biology', 'Computer Science', 
                   'Literature', 'History', 'Economics', 'Psychology', 'Art']
        
        data = {
            'module_id': range(1, len(modules) + 1),
            'module_name': modules,
            'credits': np.random.choice([3, 4, 6], len(modules)),
            'difficulty_level': np.random.choice(['Beginner', 'Intermediate', 'Advanced'], len(modules)),
            'enrollment_count': np.random.randint(10, 200, len(modules)),
            'pass_rate': np.random.uniform(0.6, 0.95, len(modules))
        }
        
        return pd.DataFrame(data)

    def apply_filters(self, df, filters):
        """Apply filters to dataframe"""
        if not filters:
            return df
            
        filtered_df = df.copy()
        
        # Age range filter
        if 'age_range' in filters:
            min_age, max_age = filters['age_range']
            if 'age' in filtered_df.columns:
                filtered_df = filtered_df[(filtered_df['age'] >= min_age) & (filtered_df['age'] <= max_age)]
        
        # GPA range filter
        if 'gpa_range' in filters:
            min_gpa, max_gpa = filters['gpa_range']
            if 'gpa' in filtered_df.columns:
                filtered_df = filtered_df[(filtered_df['gpa'] >= min_gpa) & (filtered_df['gpa'] <= max_gpa)]
        
        # Course filter
        if 'course' in filters and 'course' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['course'] == filters['course']]
        
        # Gender filter
        if 'gender' in filters and 'gender' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['gender'] == filters['gender']]
        
        return filtered_df

    def safe_plot_data(self, x_data, y_data):
        """Safely plot data with error handling for GUI"""
        if len(x_data) == 0 or len(y_data) == 0:
            print("Warning: No data to plot")
            return False
        return True

    def save_or_display_plot(self, plt_figure, plot_type, export_format='png'):
        """Save plot for GUI compatibility"""
        import matplotlib.pyplot as plt
        from datetime import datetime
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{self.plots_dir}/{plot_type}_{timestamp}.{export_format}"
        
        try:
            plt.tight_layout()
            plt.savefig(filename, dpi=300, bbox_inches='tight')
            print(f"Plot saved: {filename}")
            # Don't call plt.show() in GUI mode - let the GUI handle display
        except Exception as e:
            print(f"Error saving plot: {e}")

    def email_reports(self):
        """Send email reports - GUI compatible stub"""
        print("Email functionality would be implemented here")
        print("This requires SMTP configuration and recipient setup")
        # Implementation would go here for actual email sending

    def send_email_with_attachment(self, recipient, subject, report_type):
        """Send email with attachment - GUI compatible stub"""
        print(f"Would send {report_type} report to {recipient} with subject: {subject}")
        # Implementation would go here

    def data_quality_check(self):
        """Perform data quality check"""
        print("Performing data quality check...")
        
        students_df = self.get_all_students()
        modules_df = self.get_all_modules()
        
        print(f"\nData Quality Report:")
        print(f"Students table: {len(students_df)} records")
        
        if not students_df.empty:
            # Check for missing values
            missing_data = students_df.isnull().sum()
            if missing_data.sum() > 0:
                print("Missing data found:")
                for col, count in missing_data.items():
                    if count > 0:
                        print(f"  {col}: {count} missing values")
            else:
                print("No missing data found in students table")
        
        print(f"Modules table: {len(modules_df)} records")
        print("Data quality check completed")

    def advanced_filtering(self):
        """Advanced filtering options - GUI compatible"""
        print("Advanced filtering options:")
        print("1. Age range filtering")
        print("2. GPA range filtering") 
        print("3. Course-specific filtering")
        print("4. Gender-based filtering")
        print("5. Engagement score filtering")
        print("Use the GUI filter dialog for interactive filtering")

    def configuration_settings(self):
        """Configuration settings - GUI compatible"""
        print("Configuration settings available:")
        print("- Plot dimensions and DPI")
        print("- Export formats")
        print("- Email settings")
        print("- Color schemes")
        print("Use the GUI configuration dialog for settings management")

    def generate_complete_report(self):
        """Generate a complete comprehensive report"""
        print("Generating complete analytics report...")
        
        try:
            # Run all major analyses
            print("Running demographic analysis...")
            self.analyze_student_demographics()
            
            print("Running grade distribution analysis...")
            self.analyze_grade_distribution()
            
            print("Running course enrollment analysis...")
            self.analyze_course_enrollments()
            
            print("Running performance trends analysis...")
            self.analyze_performance_trends()
            
            print("Running risk assessment...")
            self.analyze_academic_risk()
            
            print("Running module popularity analysis...")
            self.analyze_module_popularity()
            
            print("Running engagement analysis...")
            self.analyze_engagement()
            
            print("Complete report generation finished!")
            print("Check the plots and reports directories for outputs")
            
        except Exception as e:
            print(f"Error generating complete report: {e}")

    def generate_statistical_summary_report(self, students_df, modules_df, timestamp):
        """Generate statistical summary report"""
        import pandas as pd
        
        filename = f"{self.reports_dir}/statistical_summary_{timestamp}.txt"
        
        try:
            with open(filename, 'w') as f:
                f.write("STATISTICAL SUMMARY REPORT\n")
                f.write("="*50 + "\n\n")
                
                # Students summary
                f.write("STUDENT STATISTICS\n")
                f.write("-"*20 + "\n")
                f.write(f"Total Students: {len(students_df)}\n")
                
                if 'gpa' in students_df.columns:
                    f.write(f"Average GPA: {students_df['gpa'].mean():.2f}\n")
                    f.write(f"GPA Std Dev: {students_df['gpa'].std():.2f}\n")
                    f.write(f"Min GPA: {students_df['gpa'].min():.2f}\n")
                    f.write(f"Max GPA: {students_df['gpa'].max():.2f}\n")
                
                if 'age' in students_df.columns:
                    f.write(f"Average Age: {students_df['age'].mean():.1f}\n")
                    f.write(f"Age Range: {students_df['age'].min()}-{students_df['age'].max()}\n")
                
                if 'engagement_score' in students_df.columns:
                    f.write(f"Average Engagement: {students_df['engagement_score'].mean():.1f}\n")
                
                # Modules summary
                f.write(f"\nMODULE STATISTICS\n")
                f.write("-"*20 + "\n")
                f.write(f"Total Modules: {len(modules_df)}\n")
                
                if 'enrollment_count' in modules_df.columns:
                    f.write(f"Total Enrollments: {modules_df['enrollment_count'].sum()}\n")
                    f.write(f"Avg Enrollment per Module: {modules_df['enrollment_count'].mean():.1f}\n")
                
            print(f"Statistical summary saved: {filename}")
            
        except Exception as e:
            print(f"Error generating statistical summary: {e}")
    
    def setup_styles(self):
        """Configure the GUI styling"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure custom styles
        style.configure('Title.TLabel', font=('Arial', 16, 'bold'))
        style.configure('Heading.TLabel', font=('Arial', 12, 'bold'))
        style.configure('Action.TButton', font=('Arial', 10, 'bold'))
        
    def create_main_interface(self):
        """Create the main GUI interface"""
        # Create main frames
        self.create_header()
        self.create_main_content()
        self.create_status_bar()
        
    def create_header(self):
        """Create header with title and quick stats"""
        header_frame = ttk.Frame(self.root)
        header_frame.pack(fill='x', padx=10, pady=5)
        
        # Title
        title_label = ttk.Label(header_frame, text="🎓 Enhanced Student Analytics Dashboard 🎓", 
                               style='Title.TLabel')
        title_label.pack(pady=5)
        
        # Quick stats frame
        stats_frame = ttk.Frame(header_frame)
        stats_frame.pack(fill='x', pady=5)
        
        # Quick stats (will be updated dynamically)
        self.stats_labels = {}
        stats_info = [
            ("Total Students", "total_students"),
            ("Avg GPA", "avg_gpa"),
            ("Completion Rate", "completion_rate"),
            ("At Risk", "at_risk")
        ]
        
        for i, (label, key) in enumerate(stats_info):
            frame = ttk.Frame(stats_frame)
            frame.pack(side='left', expand=True, fill='x', padx=5)
            
            ttk.Label(frame, text=label, style='Heading.TLabel').pack()
            self.stats_labels[key] = ttk.Label(frame, text="Loading...", 
                                              font=('Arial', 11, 'bold'))
            self.stats_labels[key].pack()
        
        # Return to Home button
        ttk.Button(stats_frame, text="🏠 Return to Main Menu",
                  command=self.return_to_main_menu).pack(side='right', padx=5)

        # Refresh button
        ttk.Button(stats_frame, text="Refresh Stats",
                  command=self.refresh_stats).pack(side='right', padx=5)
        
    def create_main_content(self):
        """Create the main content area with tabs and controls"""
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Analysis tabs
        self.create_basic_analytics_tab()
        self.create_performance_tab()
        self.create_advanced_tab()
        self.create_reports_tab()
        self.create_utilities_tab()
        self.create_output_tab()

    def create_basic_analytics_tab(self):
        """Create basic analytics tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="📊 Basic Analytics")
        
        # Create scrollable frame
        canvas = tk.Canvas(tab)
        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Basic analytics buttons - FIXED: Remove duplicate list and fix tuple formatting
        basic_analyses = [
            ("Student Demographics", self.run_demographics, 
             "Analyze age, gender, course distribution and geographic data"),
            ("Module Popularity Analysis", self.run_module_popularity,
             "Examine which modules are most popular and successful"),
            ("Course Enrollment Statistics", self.run_course_enrollments,
             "Review enrollment patterns across different courses"),
            ("Registration Timeline", self.run_registration_timeline,
             "Track registration patterns over time"),
            ("Grade Distribution Analysis", self.run_grade_distribution,
             "Analyze grade patterns and academic performance distribution"),
        ]
        
        for i, (title, command, description) in enumerate(basic_analyses):
            self.create_analysis_button(scrollable_frame, title, command, description, i)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
               
    def create_performance_tab(self):
        """Create performance analytics tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="📈 Performance")
        
        # Create scrollable frame
        canvas = tk.Canvas(tab)
        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        performance_analyses = [
            ("Grade Distribution Analysis", self.run_grade_distribution,
             "Analyze grade patterns and academic performance"),
            ("Academic Risk Assessment", self.run_academic_risk,
             "Identify students at risk of academic failure"),
            ("Module Difficulty Analysis", self.run_module_difficulty,
             "Evaluate module difficulty and success rates"),
            ("Student Performance Trends", self.run_performance_trends,
             "Track performance changes over time")
        ]
        
        for i, (title, command, description) in enumerate(performance_analyses):
            self.create_analysis_button(scrollable_frame, title, command, description, i)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def run_grade_distribution(self):
            self.run_analysis_thread(self.analyze_grade_distribution, "Grade Distribution")
            
        def run_course_enrollments(self):
            self.run_analysis_thread(self.analyze_course_enrollments, "Course Enrollments")
            
        def run_registration_timeline(self):
            self.run_analysis_thread(self.analyze_registration_timeline, "Registration Timeline")   
        
    def create_advanced_tab(self):
        """Create advanced analytics tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="🔬 Advanced")
        
        # Create scrollable frame
        canvas = tk.Canvas(tab)
        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        advanced_analyses = [
            ("Correlation Analysis", self.run_correlations,
             "Examine relationships between different variables"),
            ("Cohort Analysis", self.run_cohorts,
             "Analyze student cohorts and retention patterns"),
            ("Engagement Scoring", self.run_engagement,
             "Evaluate student engagement levels and patterns"),
            ("Predictive Analytics", self.run_predictive,
             "Use machine learning for predictive insights")
        ]
        
        for i, (title, command, description) in enumerate(advanced_analyses):
            self.create_analysis_button(scrollable_frame, title, command, description, i)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
    def create_reports_tab(self):
        """Create reporting and export tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="📋 Reports")
        
        # Create two columns
        left_frame = ttk.Frame(tab)
        left_frame.pack(side='left', fill='both', expand=True, padx=5, pady=5)
        
        right_frame = ttk.Frame(tab)
        right_frame.pack(side='right', fill='both', expand=True, padx=5, pady=5)
        
        # Report generation
        ttk.Label(left_frame, text="Report Generation", style='Heading.TLabel').pack(pady=5)
        
        report_buttons = [
            ("Generate Complete Report", self.run_complete_report),
            ("Custom Report Builder", self.run_custom_report),
            ("🏠 Return to Main Menu", self.return_to_main_menu)
        ]
        
        for title, command in report_buttons:
            ttk.Button(left_frame, text=title, command=command, 
                      style='Action.TButton').pack(fill='x', pady=2)
        
        # Export options
        ttk.Label(right_frame, text="Export Options", style='Heading.TLabel').pack(pady=5)
        
        export_buttons = [
            ("Export to Excel", lambda: self.run_export('excel')),
            ("Export to CSV", lambda: self.run_export('csv')),
            ("Export to JSON", lambda: self.run_export('json')),
            ("Statistical Summary", lambda: self.run_export('summary'))
        ]
        
        for title, command in export_buttons:
            ttk.Button(right_frame, text=title, command=command,
                      style='Action.TButton').pack(fill='x', pady=2)
        
        # Filters frame
        filters_frame = ttk.LabelFrame(tab, text="Filters", padding=10)
        filters_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(filters_frame, text="Advanced Filtering", 
                  command=self.show_filters_dialog).pack(side='left', padx=5)
        ttk.Button(filters_frame, text="Clear Filters", 
                  command=self.clear_filters).pack(side='left', padx=5)
        
        self.filter_status = ttk.Label(filters_frame, text="No filters applied")
        self.filter_status.pack(side='left', padx=10)
        
    def create_utilities_tab(self):
        """Create utilities tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="🔧 Utilities")
        
        # Create sections
        sections = [
            ("Data Management", [
                ("Data Quality Check", self.run_data_quality),
                ("Database Connection Test", self.test_database),
            ("🏠 Return to Main Menu", self.return_to_main_menu)
        ]),
            ("Configuration", [
                ("Configuration Settings", self.show_config_dialog),
                ("Color Scheme Settings", self.show_color_dialog),
            ("🏠 Return to Main Menu", self.return_to_main_menu)
        ]),
            ("Help & About", [
                ("View Help Documentation", self.show_help),
                ("About This Application", self.show_about),
            ("🏠 Return to Main Menu", self.return_to_main_menu)
        ])
        ]
        
        for section_title, buttons in sections:
            frame = ttk.LabelFrame(tab, text=section_title, padding=10)
            frame.pack(fill='x', padx=10, pady=5)
            
            for title, command in buttons:
                ttk.Button(frame, text=title, command=command).pack(side='left', padx=5)
    
    def create_output_tab(self):
        """Create output/console tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="📝 Output")
        
        # Create output text area
        self.output_text = scrolledtext.ScrolledText(tab, wrap='word', height=30)
        self.output_text.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Control buttons
        button_frame = ttk.Frame(tab)
        button_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(button_frame, text="Clear Output", 
                  command=self.clear_output).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Save Output", 
                  command=self.save_output).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Copy to Clipboard", 
                  command=self.copy_output).pack(side='left', padx=5)
        
    def create_analysis_button(self, parent, title, command, description, row):
        """Create a styled analysis button with description"""
        frame = ttk.Frame(parent)
        frame.pack(fill='x', padx=10, pady=5)
        
        # Button
        btn = ttk.Button(frame, text=title, command=command, 
                        style='Action.TButton', width=30)
        btn.pack(side='left', padx=5)
        
        # Description
        desc_label = ttk.Label(frame, text=description, foreground='gray')
        desc_label.pack(side='left', padx=10)
        
    def create_status_bar(self):
        """Create status bar at bottom"""
        self.status_frame = ttk.Frame(self.root)
        self.status_frame.pack(fill='x', side='bottom')
        
        self.status_label = ttk.Label(self.status_frame, text="Ready", relief='sunken')
        self.status_label.pack(side='left', fill='x', expand=True)
        
        self.progress = ttk.Progressbar(self.status_frame, mode='indeterminate')
        self.progress.pack(side='right', padx=5)
        
    def setup_output_capture(self):
        """Setup output capture for console messages"""
        class OutputCapture:
            def __init__(self, queue_obj):
                self.queue = queue_obj
                self.original_stdout = sys.stdout
                
            def write(self, text):
                self.queue.put(text)
                self.original_stdout.write(text)
                
            def flush(self):
                self.original_stdout.flush()
        
        # Redirect stdout to capture print statements
        sys.stdout = OutputCapture(self.output_queue)
        
    def monitor_output(self):
        """Monitor the output queue and update GUI"""
        try:
            while True:
                text = self.output_queue.get_nowait()
                self.output_text.insert('end', text)
                self.output_text.see('end')
        except queue.Empty:
            pass
        
        # Schedule next check
        self.root.after(100, self.monitor_output)
        
    def run_analysis_thread(self, analysis_func, analysis_name):
        """Run analysis in main thread to avoid matplotlib threading issues"""
        try:
            self.update_status(f"Running {analysis_name}...")
            self.progress.start()
            self.root.update()  # Process pending events

            # Run analysis in main thread (not daemon thread)
            # This prevents matplotlib from crashing
            result = analysis_func()

            # If result is a dictionary with GUI data, display it in a GUI window
            if isinstance(result, dict) and 'figure' in result:
                self.display_results_window(
                    result.get('title', analysis_name),
                    result.get('summary', ''),
                    result.get('figure')
                )
            else:
                # Old-style analysis that doesn't return data
                self.update_status(f"{analysis_name} completed successfully")
                messagebox.showinfo("Analysis Complete",
                                  f"{analysis_name} has been completed successfully!")
        except Exception as e:
            import traceback
            error_msg = f"Error in {analysis_name}: {str(e)}\n\n{traceback.format_exc()}"
            self.update_status(f"Error in {analysis_name}")
            messagebox.showerror("Analysis Error", error_msg)
            print(error_msg)
        finally:
            self.progress.stop()
        
    def update_status(self, message):
        """Update status bar message"""
        self.status_label.config(text=message)
        self.root.update_idletasks()
        
    def refresh_stats(self):
        """Refresh the quick stats in header"""
        try:
            students_df = self.analytics.get_all_students()
            
            if not students_df.empty:
                total_students = len(students_df)
                avg_gpa = students_df['gpa'].mean()
                completion_rate = (students_df['completion_status'] == 'Completed').mean() * 100
                at_risk = (students_df['gpa'] < 2.0).sum()
                
                self.stats_labels['total_students'].config(text=f"{total_students}")
                self.stats_labels['avg_gpa'].config(text=f"{avg_gpa:.2f}")
                self.stats_labels['completion_rate'].config(text=f"{completion_rate:.1f}%")
                self.stats_labels['at_risk'].config(text=f"{at_risk}")
            else:
                for label in self.stats_labels.values():
                    label.config(text="No Data")
                    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh stats: {str(e)}")
            
    # Analysis method wrappers
    def run_demographics(self):
        self.run_analysis_thread(self.analytics.analyze_student_demographics, "Student Demographics")
        
    def run_module_popularity(self):
        self.run_analysis_thread(self.analytics.analyze_module_popularity, "Module Popularity")
        
    def run_course_enrollments(self):
        self.run_analysis_thread(self.analytics.analyze_course_enrollments, "Course Enrollments")
        
    def run_registration_timeline(self):
        self.run_analysis_thread(self.analytics.analyze_registration_timeline, "Registration Timeline")
        
    def run_grade_distribution(self):
        self.run_analysis_thread(self.analytics.analyze_grade_distribution, "Grade Distribution")
        
    def run_academic_risk(self):
        self.run_analysis_thread(self.analytics.analyze_academic_risk, "Academic Risk Assessment")
        
    def run_module_difficulty(self):
        self.run_analysis_thread(self.analytics.analyze_module_difficulty, "Module Difficulty")
        
    def run_performance_trends(self):
        self.run_analysis_thread(self.analytics.analyze_performance_trends, "Performance Trends")
        
    def run_correlations(self):
        self.run_analysis_thread(self.analytics.analyze_correlations, "Correlation Analysis")
        
    def run_cohorts(self):
        self.run_analysis_thread(self.analytics.analyze_cohorts, "Cohort Analysis")
        
    def run_engagement(self):
        self.run_analysis_thread(self.analytics.analyze_engagement, "Engagement Analysis")
        
    def run_predictive(self):
        self.run_analysis_thread(self.analytics.predictive_analytics, "Predictive Analytics")
        
    def run_complete_report(self):
        self.run_analysis_thread(self.analytics.generate_complete_report, "Complete Report")
        
    def run_custom_report(self):
        self.show_custom_report_dialog()
        
    def run_email_reports(self):
        self.run_analysis_thread(self.analytics.email_reports, "Email Reports")
        
    def run_export(self, export_type):
        if export_type == 'excel':
            self.run_analysis_thread(lambda: self.analytics.export_data_choice('1'), "Excel Export")
        elif export_type == 'csv':
            self.run_analysis_thread(lambda: self.analytics.export_data_choice('2'), "CSV Export")
        elif export_type == 'json':
            self.run_analysis_thread(lambda: self.analytics.export_data_choice('3'), "JSON Export")
        elif export_type == 'summary':
            self.run_analysis_thread(lambda: self.analytics.export_data_choice('4'), "Summary Export")
            
    def run_data_quality(self):
        self.run_analysis_thread(self.analytics.data_quality_check, "Data Quality Check")
        
    # Dialog methods
    def show_filters_dialog(self):
        """Show advanced filters dialog"""
        dialog = FilterDialog(self.root, self.analytics)
        self.root.wait_window(dialog.dialog)
        self.update_filter_status()
        
    def show_custom_report_dialog(self):
        """Show custom report builder dialog"""
        dialog = CustomReportDialog(self.root, self.analytics)
        self.root.wait_window(dialog.dialog)
        
    def show_config_dialog(self):
        """Show configuration dialog"""
        dialog = ConfigDialog(self.root, self.analytics)
        self.root.wait_window(dialog.dialog)
        
    def show_color_dialog(self):
        """Show color scheme dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Color Scheme Settings")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()

        # Create main frame
        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Color Scheme Settings", font=('Arial', 14, 'bold')).pack(pady=10)

        # Color scheme selection
        ttk.Label(main_frame, text="Select Color Scheme:").pack(pady=5)

        schemes = {
            "Default": ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b'],
            "Viridis": ['#440154', '#31688e', '#35b779', '#fde724', '#90d743', '#21918c'],
            "Pastel": ['#aec7e8', '#ffbb78', '#98df8a', '#ff9896', '#c5b0d5', '#c49c94'],
            "Bold": ['#e41a1c', '#377eb8', '#4daf4a', '#984ea3', '#ff7f00', '#ffff33']
        }

        selected_scheme = tk.StringVar(value="Default")

        for scheme_name in schemes.keys():
            ttk.Radiobutton(main_frame, text=scheme_name, variable=selected_scheme,
                          value=scheme_name).pack(anchor=tk.W, padx=20)

        # Preview frame
        preview_frame = ttk.LabelFrame(main_frame, text="Preview", padding="10")
        preview_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        preview_canvas = tk.Canvas(preview_frame, height=100)
        preview_canvas.pack(fill=tk.BOTH, expand=True)

        def update_preview(*args):
            preview_canvas.delete("all")
            colors = schemes[selected_scheme.get()]
            width = 400 // len(colors)
            for i, color in enumerate(colors):
                preview_canvas.create_rectangle(i*width, 0, (i+1)*width, 100, fill=color, outline="")

        selected_scheme.trace('w', update_preview)
        update_preview()

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)

        def apply_colors():
            CONFIG['colors'] = schemes[selected_scheme.get()]
            messagebox.showinfo("Success", "Color scheme applied successfully!")
            dialog.destroy()

        ttk.Button(button_frame, text="Apply", command=apply_colors).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
        
    def show_export_dialog(self):
        """Show export preferences dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Export Preferences")
        dialog.geometry("500x450")
        dialog.transient(self.root)
        dialog.grab_set()

        # Create main frame
        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Export Preferences", font=('Arial', 14, 'bold')).pack(pady=10)

        # Export format section
        format_frame = ttk.LabelFrame(main_frame, text="Export Formats", padding="10")
        format_frame.pack(fill=tk.X, pady=10)

        formats = {
            'PNG': tk.BooleanVar(value=True),
            'PDF': tk.BooleanVar(value=False),
            'SVG': tk.BooleanVar(value=False),
            'Excel': tk.BooleanVar(value=False)
        }

        for fmt, var in formats.items():
            ttk.Checkbutton(format_frame, text=fmt, variable=var).pack(anchor=tk.W)

        # Quality settings
        quality_frame = ttk.LabelFrame(main_frame, text="Quality Settings", padding="10")
        quality_frame.pack(fill=tk.X, pady=10)

        ttk.Label(quality_frame, text="DPI:").grid(row=0, column=0, sticky=tk.W, pady=5)
        dpi_var = tk.StringVar(value=str(CONFIG['dpi']))
        dpi_combo = ttk.Combobox(quality_frame, textvariable=dpi_var, values=['150', '300', '600'], width=10)
        dpi_combo.grid(row=0, column=1, sticky=tk.W, pady=5)

        ttk.Label(quality_frame, text="Figure Size:").grid(row=1, column=0, sticky=tk.W, pady=5)
        size_var = tk.StringVar(value="15x10")
        size_combo = ttk.Combobox(quality_frame, textvariable=size_var, values=['10x8', '15x10', '20x15'], width=10)
        size_combo.grid(row=1, column=1, sticky=tk.W, pady=5)

        # File naming
        naming_frame = ttk.LabelFrame(main_frame, text="File Naming", padding="10")
        naming_frame.pack(fill=tk.X, pady=10)

        ttk.Label(naming_frame, text="Prefix:").grid(row=0, column=0, sticky=tk.W, pady=5)
        prefix_var = tk.StringVar(value="analytics_")
        ttk.Entry(naming_frame, textvariable=prefix_var, width=20).grid(row=0, column=1, sticky=tk.W, pady=5)

        include_timestamp = tk.BooleanVar(value=True)
        ttk.Checkbutton(naming_frame, text="Include timestamp in filename",
                       variable=include_timestamp).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=5)

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)

        def apply_settings():
            # Parse figure size
            width, height = map(int, size_var.get().split('x'))
            CONFIG['figure_size'] = (width, height)
            CONFIG['dpi'] = int(dpi_var.get())
            CONFIG['export_formats'] = [fmt.lower() for fmt, var in formats.items() if var.get()]

            messagebox.showinfo("Success", "Export preferences saved successfully!")
            dialog.destroy()

        ttk.Button(button_frame, text="Apply", command=apply_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
        
    def show_help(self):
        """Show help documentation"""
        help_text = """
        Enhanced Student Analytics Dashboard Help
        
        Basic Analytics:
        - Student Demographics: Analyze student population characteristics
        - Module Popularity: See which modules are most popular
        - Course Enrollments: Track enrollment patterns
        - Registration Timeline: View registration trends
        
        Performance Analytics:
        - Grade Distribution: Analyze academic performance
        - Academic Risk: Identify at-risk students
        - Module Difficulty: Evaluate module difficulty
        - Performance Trends: Track changes over time
        
        Advanced Analytics:
        - Correlation Analysis: Find relationships between variables
        - Cohort Analysis: Analyze student cohorts
        - Engagement Scoring: Measure student engagement
        - Predictive Analytics: Machine learning insights
        
        Tips:
        - Use filters to focus on specific student groups
        - Check the Output tab for detailed analysis results
        - Export data in multiple formats for further analysis
        """
        
        help_window = tk.Toplevel(self.root)
        help_window.title("Help Documentation")
        help_window.geometry("600x500")
        
        text_widget = scrolledtext.ScrolledText(help_window, wrap='word')
        text_widget.pack(fill='both', expand=True, padx=10, pady=10)
        text_widget.insert('1.0', help_text)
        text_widget.config(state='disabled')
        
    def show_about(self):
        """Show about dialog"""
        about_text = """
        Enhanced Student Analytics Dashboard
        Version 2.0
        
        A comprehensive analytics platform for educational institutions
        to analyze student performance, engagement, and trends.
        
        Features:
        - Comprehensive demographic analysis
        - Performance tracking and prediction
        - Risk assessment and intervention planning
        - Advanced statistical analysis
        - Machine learning capabilities
        - Professional reporting
        
        Compatible with existing command-line interface.
        """
        messagebox.showinfo("About", about_text)


    def analyze_student_demographics(self):
        """Enhanced student demographics analysis - GUI compatible version"""
        students_df = self.get_all_students(self.custom_filters)
        
        if students_df.empty:
            print("No student data available for analysis.")
            return
        
        print("\nGenerating Enhanced Student Demographics Analysis...")
        
        # Create comprehensive demographics analysis
        fig = plt.figure(figsize=(20, 15))
        fig.suptitle('Enhanced Student Demographics Analysis', fontsize=20)
        
        # 1. Gender Distribution
        ax1 = fig.add_subplot(331)
        gender_counts = students_df['gender'].value_counts()
        colors = CONFIG['colors'][:len(gender_counts)]
        ax1.pie(gender_counts, labels=gender_counts.index, autopct='%1.1f%%', 
                startangle=90, colors=colors)
        ax1.set_title('Gender Distribution')
        
        # 2. Age Distribution with statistics
        ax2 = fig.add_subplot(332)
        ax2.hist(students_df['age'], bins=range(int(min(students_df['age'])), int(max(students_df['age']))+2),
                edgecolor='black', alpha=0.7)
        ax2.axvline(students_df['age'].mean(), color='red', linestyle='--', label=f'Mean: {students_df["age"].mean():.1f}')
        ax2.axvline(students_df['age'].median(), color='green', linestyle='--', label=f'Median: {students_df["age"].median():.1f}')
        ax2.set_xlabel('Age')
        ax2.set_ylabel('Number of Students')
        ax2.set_title('Age Distribution')
        ax2.legend()
        
        # 3. Course Distribution
        ax3 = fig.add_subplot(333)
        course_counts = students_df['course'].value_counts()
        ax3.bar(course_counts.index, course_counts.values, color=colors)
        ax3.set_xlabel('Course')
        ax3.set_ylabel('Number of Students')
        ax3.set_title('Course Distribution')
        
        # 4. GPA Distribution
        ax4 = fig.add_subplot(334)
        ax4.hist(students_df['gpa'], bins=20, edgecolor='black', alpha=0.7)
        ax4.axvline(students_df['gpa'].mean(), color='red', linestyle='--', label=f'Mean GPA: {students_df["gpa"].mean():.2f}')
        ax4.set_xlabel('GPA')
        ax4.set_ylabel('Number of Students')
        ax4.set_title('GPA Distribution')
        ax4.legend()
        
        # 5. Location Distribution
        ax5 = fig.add_subplot(335)
        location_counts = students_df['location'].value_counts()
        ax5.bar(location_counts.index, location_counts.values, color=colors)
        plt.xticks(rotation=45, ha='right')
        ax5.set_xlabel('Location')
        ax5.set_ylabel('Number of Students')
        ax5.set_title('Geographic Distribution')
        
        # 6. Previous Education
        ax6 = fig.add_subplot(336)
        edu_counts = students_df['previous_education'].value_counts()
        ax6.pie(edu_counts, labels=edu_counts.index, autopct='%1.1f%%', startangle=90)
        ax6.set_title('Previous Education Level')
        
        # 7. Completion Status
        ax7 = fig.add_subplot(337)
        status_counts = students_df['completion_status'].value_counts()
        ax7.bar(status_counts.index, status_counts.values, color=colors)
        plt.xticks(rotation=45, ha='right')
        ax7.set_xlabel('Status')
        ax7.set_ylabel('Number of Students')
        ax7.set_title('Completion Status')
        
        # 8. Engagement Score Distribution
        ax8 = fig.add_subplot(338)
        ax8.hist(students_df['engagement_score'], bins=20, edgecolor='black', alpha=0.7)
        ax8.axvline(students_df['engagement_score'].mean(), color='red', linestyle='--', 
                   label=f'Mean: {students_df["engagement_score"].mean():.1f}')
        ax8.set_xlabel('Engagement Score')
        ax8.set_ylabel('Number of Students')
        ax8.set_title('Student Engagement Distribution')
        ax8.legend()
        
        # 9. Age vs GPA Scatter
        ax9 = fig.add_subplot(339)
        scatter = ax9.scatter(students_df['age'], students_df['gpa'], 
                             c=students_df['engagement_score'], cmap='viridis', alpha=0.6)
        ax9.set_xlabel('Age')
        ax9.set_ylabel('GPA')
        ax9.set_title('Age vs GPA (colored by Engagement)')
        plt.colorbar(scatter, ax=ax9, label='Engagement Score')
        
        plt.tight_layout(rect=[0, 0, 1, 0.95])

        # Build enhanced summary statistics for GUI display
        summary_text = "="*60 + "\n"
        summary_text += "ENHANCED DEMOGRAPHICS SUMMARY\n"
        summary_text += "="*60 + "\n"
        summary_text += f"Total students: {len(students_df)}\n"
        summary_text += f"Active students: {len(students_df[students_df['completion_status'] == 'Active'])}\n"
        summary_text += f"Completion rate: {len(students_df[students_df['completion_status'] == 'Completed']) / len(students_df) * 100:.1f}%\n"

        summary_text += f"\n📊 Statistical Summary:\n"
        summary_text += f"Average age: {students_df['age'].mean():.1f} (±{students_df['age'].std():.1f})\n"
        summary_text += f"Average GPA: {students_df['gpa'].mean():.2f} (±{students_df['gpa'].std():.2f})\n"
        summary_text += f"Average engagement: {students_df['engagement_score'].mean():.1f} (±{students_df['engagement_score'].std():.1f})\n"

        summary_text += f"\n🎯 Top Performing Segments:\n"
        high_performers = students_df[students_df['gpa'] >= 3.5]
        if not high_performers.empty:
            summary_text += f"High performers (GPA ≥ 3.5): {len(high_performers)} ({len(high_performers)/len(students_df)*100:.1f}%)\n"
            summary_text += f"Most common course among high performers: {high_performers['course'].mode().iloc[0]}\n"
            summary_text += f"Average age of high performers: {high_performers['age'].mean():.1f}\n"

        # Display results in GUI window
        self.display_results_window("Student Demographics Analysis", summary_text, fig)

        self.save_or_display_plot(fig, "enhanced_student_demographics")
    
    def analyze_grade_distribution(self):
        """Analyze grade distributions across modules and courses - GUI compatible"""
        students_df = self.get_all_students(self.custom_filters)
        modules_df = self.get_all_modules(self.custom_filters)
        
        if students_df.empty:
            print("Insufficient data for grade analysis.")
            return
        
        # Clean data and handle NaN values
        students_df = students_df.dropna(subset=['overall_grade', 'gpa'])
        
        print("\nGenerating Grade Distribution Analysis...")
        
        fig = plt.figure(figsize=(20, 15))
        fig.suptitle('Grade Distribution Analysis', fontsize=20)
        
        # 1. Overall Grade Distribution
        ax1 = fig.add_subplot(331)
        grade_counts = students_df['overall_grade'].value_counts().reindex(['A', 'B', 'C', 'D', 'F'], fill_value=0)
        ax1.bar(grade_counts.index, grade_counts.values, color=CONFIG['colors'])
        ax1.set_xlabel('Grade')
        ax1.set_ylabel('Number of Students')
        ax1.set_title('Overall Grade Distribution')
        
        # Add percentage labels with null check
        total_students = len(students_df)
        if total_students > 0:
            for i, v in enumerate(grade_counts.values):
                if v > 0:  # Only add labels for non-zero values
                    percentage = v / total_students * 100
                    if not (np.isnan(percentage) or np.isinf(percentage)):
                        ax1.text(i, v + 0.5, f'{percentage:.1f}%', ha='center')
        
        # 2. GPA by Course
        ax2 = fig.add_subplot(332)
        course_gpa = students_df.groupby('course')['gpa'].mean().dropna()
        if not course_gpa.empty:
            ax2.bar(course_gpa.index, course_gpa.values, color=CONFIG['colors'])
            ax2.set_xlabel('Course')
            ax2.set_ylabel('Average GPA')
            ax2.set_title('Average GPA by Course')
        else:
            ax2.text(0.5, 0.5, 'No valid GPA data', ha='center', va='center', transform=ax2.transAxes)
            ax2.set_title('Average GPA by Course (No Data)')
        
        # 3. Grade Distribution by Gender
        ax3 = fig.add_subplot(333)
        if 'gender' in students_df.columns and not students_df['gender'].isna().all():
            grade_gender = pd.crosstab(students_df['gender'], students_df['overall_grade'])
            if not grade_gender.empty:
                grade_gender.plot(kind='bar', ax=ax3, color=CONFIG['colors'])
                ax3.set_xlabel('Gender')
                ax3.set_ylabel('Number of Students')
                ax3.set_title('Grade Distribution by Gender')
                ax3.legend(title='Grade')
                plt.setp(ax3.xaxis.get_majorticklabels(), rotation=0)
            else:
                ax3.text(0.5, 0.5, 'No gender data', ha='center', va='center', transform=ax3.transAxes)
        else:
            ax3.text(0.5, 0.5, 'Gender column not available', ha='center', va='center', transform=ax3.transAxes)
            ax3.set_title('Grade Distribution by Gender (No Data)')
        
        # 4. Module Grade Distribution
        ax4 = fig.add_subplot(334)
        if not modules_df.empty and 'module_grade' in modules_df.columns:
            module_grades = modules_df['module_grade'].value_counts().reindex(['A', 'B', 'C', 'D', 'F'], fill_value=0)
            ax4.bar(module_grades.index, module_grades.values, color=CONFIG['colors'])
            ax4.set_xlabel('Module Grade')
            ax4.set_ylabel('Number of Module Enrollments')
            ax4.set_title('Module Grade Distribution')
        else:
            ax4.text(0.5, 0.5, 'No module grade data', ha='center', va='center', transform=ax4.transAxes)
            ax4.set_title('Module Grade Distribution (No Data)')
        
        # 5. GPA Distribution by Age Group
        ax5 = fig.add_subplot(335)
        if 'age' in students_df.columns and not students_df['age'].isna().all():
            students_df['age_group'] = pd.cut(students_df['age'], bins=[0, 25, 35, 45, 100], 
                                             labels=['18-25', '26-35', '36-45', '46+'])
            age_gpa = students_df.groupby('age_group')['gpa'].mean().dropna()
            if not age_gpa.empty:
                ax5.bar(age_gpa.index, age_gpa.values, color=CONFIG['colors'])
                ax5.set_xlabel('Age Group')
                ax5.set_ylabel('Average GPA')
                ax5.set_title('Average GPA by Age Group')
            else:
                ax5.text(0.5, 0.5, 'No valid age/GPA data', ha='center', va='center', transform=ax5.transAxes)
        else:
            ax5.text(0.5, 0.5, 'Age column not available', ha='center', va='center', transform=ax5.transAxes)
            ax5.set_title('Average GPA by Age Group (No Data)')
        
        # 6. Pass/Fail Rate by Course
        ax6 = fig.add_subplot(336)
        students_df['pass_fail'] = students_df['overall_grade'].apply(lambda x: 'Pass' if x != 'F' else 'Fail')
        pass_rate = students_df.groupby('course')['pass_fail'].apply(lambda x: (x == 'Pass').mean() * 100)
        pass_rate = pass_rate.dropna()
        if not pass_rate.empty:
            ax6.bar(pass_rate.index, pass_rate.values, color=CONFIG['colors'])
            ax6.set_xlabel('Course')
            ax6.set_ylabel('Pass Rate (%)')
            ax6.set_title('Pass Rate by Course')
            ax6.set_ylim(0, 100)
        else:
            ax6.text(0.5, 0.5, 'No valid course data', ha='center', va='center', transform=ax6.transAxes)
            ax6.set_title('Pass Rate by Course (No Data)')
        
        # 7. GPA vs Engagement Correlation
        ax7 = fig.add_subplot(337)
        if 'engagement_score' in students_df.columns and not students_df['engagement_score'].isna().all():
            valid_data = students_df.dropna(subset=['engagement_score', 'gpa', 'age'])
            if len(valid_data) > 0:
                scatter = ax7.scatter(valid_data['engagement_score'], valid_data['gpa'], 
                                     c=valid_data['age'], cmap='viridis', alpha=0.6)
                ax7.set_xlabel('Engagement Score')
                ax7.set_ylabel('GPA')
                ax7.set_title('GPA vs Engagement (colored by Age)')
                plt.colorbar(scatter, ax=ax7, label='Age')
                
                # Add correlation coefficient with null check
                correlation = valid_data['engagement_score'].corr(valid_data['gpa'])
                if not (np.isnan(correlation) or np.isinf(correlation)):
                    ax7.text(0.05, 0.95, f'Correlation: {correlation:.3f}', transform=ax7.transAxes, 
                            bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))
            else:
                ax7.text(0.5, 0.5, 'No valid engagement data', ha='center', va='center', transform=ax7.transAxes)
        else:
            ax7.text(0.5, 0.5, 'Engagement score not available', ha='center', va='center', transform=ax7.transAxes)
            ax7.set_title('GPA vs Engagement (No Data)')
        
        # 8. Top Performing Modules
        ax8 = fig.add_subplot(338)
        if not modules_df.empty and 'module_name' in modules_df.columns:
            module_avg_grades = modules_df.groupby('module_name')['module_grade'].apply(
                lambda x: (x.isin(['A', 'B'])).mean() * 100
            ).dropna().sort_values(ascending=False).head(10)
            
            if not module_avg_grades.empty:
                ax8.barh(range(len(module_avg_grades)), module_avg_grades.values, color=CONFIG['colors'][0])
                ax8.set_yticks(range(len(module_avg_grades)))
                ax8.set_yticklabels(module_avg_grades.index)
                ax8.set_xlabel('% Students with A or B')
                ax8.set_title('Top Performing Modules')
            else:
                ax8.text(0.5, 0.5, 'No valid module data', ha='center', va='center', transform=ax8.transAxes)
                ax8.set_title('Top Performing Modules (No Data)')
        else:
            ax8.text(0.5, 0.5, 'Module name not available', ha='center', va='center', transform=ax8.transAxes)
            ax8.set_title('Top Performing Modules (No Data)')
        
        # 9. Grade Trend Analysis
        ax9 = fig.add_subplot(339)
        if 'registration_datetime' in students_df.columns and not students_df['registration_datetime'].isna().all():
            try:
                students_df['registration_month'] = pd.to_datetime(students_df['registration_datetime']).dt.to_period('M')
                monthly_gpa = students_df.groupby('registration_month')['gpa'].mean().dropna()
                
                if len(monthly_gpa) > 0:
                    ax9.plot(range(len(monthly_gpa)), monthly_gpa.values, marker='o', color=CONFIG['colors'][0])
                    ax9.set_xlabel('Registration Period')
                    ax9.set_ylabel('Average GPA')
                    ax9.set_title('GPA Trend Over Time')
                    
                    # Set x-axis labels with proper spacing
                    if len(monthly_gpa) > 5:
                        step = max(1, len(monthly_gpa) // 5)
                        tick_positions = range(0, len(monthly_gpa), step)
                        ax9.set_xticks(tick_positions)
                        ax9.set_xticklabels([str(monthly_gpa.index[i]) for i in tick_positions], rotation=45)
                    else:
                        ax9.set_xticks(range(len(monthly_gpa)))
                        ax9.set_xticklabels([str(idx) for idx in monthly_gpa.index], rotation=45)
                else:
                    ax9.text(0.5, 0.5, 'No valid time series data', ha='center', va='center', transform=ax9.transAxes)
            except Exception as e:
                ax9.text(0.5, 0.5, f'Error processing dates: {str(e)}', ha='center', va='center', transform=ax9.transAxes)
                ax9.set_title('GPA Trend Over Time (Error)')
        else:
            ax9.text(0.5, 0.5, 'Registration datetime not available', ha='center', va='center', transform=ax9.transAxes)
            ax9.set_title('GPA Trend Over Time (No Data)')
        
        plt.tight_layout(rect=[0, 0, 1, 0.95])
        
        # Print detailed statistics
        print("\n" + "="*60)
        print("GRADE DISTRIBUTION SUMMARY")
        print("="*60)
        
        if len(students_df) > 0:
            avg_gpa = students_df['gpa'].mean()
            median_gpa = students_df['gpa'].median()
            std_gpa = students_df['gpa'].std()
            pass_rate = (students_df['overall_grade'] != 'F').mean() * 100
            
            print(f"Overall Statistics:")
            print(f"  Average GPA: {avg_gpa:.2f}" if not np.isnan(avg_gpa) else "  Average GPA: N/A")
            print(f"  Median GPA: {median_gpa:.2f}" if not np.isnan(median_gpa) else "  Median GPA: N/A")
            print(f"  GPA Standard Deviation: {std_gpa:.2f}" if not np.isnan(std_gpa) else "  GPA Standard Deviation: N/A")
            print(f"  Pass Rate: {pass_rate:.1f}%" if not np.isnan(pass_rate) else "  Pass Rate: N/A")
        
        self.save_or_display_plot(fig, "grade_distribution_analysis")
    
    def analyze_course_enrollments(self):
        """Analyze course enrollment patterns and statistics - GUI compatible"""
        students_df = self.get_all_students(self.custom_filters)
        
        if students_df.empty:
            print("No student data available for course enrollment analysis.")
            return
        
        print("\nGenerating Course Enrollment Analysis...")
        
        fig = plt.figure(figsize=(20, 15))
        fig.suptitle('Course Enrollment Analysis', fontsize=20)
        
        # 1. Course Enrollment Distribution
        ax1 = fig.add_subplot(331)
        course_counts = students_df['course'].value_counts()
        ax1.pie(course_counts.values, labels=course_counts.index, autopct='%1.1f%%', 
               startangle=90, colors=CONFIG['colors'])
        ax1.set_title('Course Enrollment Distribution')
        
        # 2. Course Enrollment Trends Over Time
        ax2 = fig.add_subplot(332)
        if 'registration_datetime' in students_df.columns:
            students_df['reg_month'] = pd.to_datetime(students_df['registration_datetime']).dt.to_period('M')
            course_timeline = students_df.groupby(['reg_month', 'course']).size().unstack(fill_value=0)
            
            for course in course_timeline.columns:
                ax2.plot(range(len(course_timeline)), course_timeline[course], 
                        marker='o', label=course, linewidth=2)
            
            ax2.set_xlabel('Time Period')
            ax2.set_ylabel('Number of Enrollments')
            ax2.set_title('Course Enrollment Trends')
            ax2.legend()
            ax2.set_xticks(range(0, len(course_timeline), max(1, len(course_timeline)//5)))
            ax2.set_xticklabels([str(course_timeline.index[i]) for i in range(0, len(course_timeline), max(1, len(course_timeline)//5))], rotation=45)
        else:
            ax2.text(0.5, 0.5, 'Registration datetime not available', ha='center', va='center', transform=ax2.transAxes)
            ax2.set_title('Course Enrollment Trends (No Data)')
        
        # 3. Course Performance Comparison
        ax3 = fig.add_subplot(333)
        course_stats = students_df.groupby('course').agg({
            'gpa': 'mean',
            'engagement_score': 'mean',
            'student_id': 'count'
        })
        
        x = range(len(course_stats))
        width = 0.35
        ax3.bar([i - width/2 for i in x], course_stats['gpa'], width, 
               label='Avg GPA', color=CONFIG['colors'][0])
        ax3_twin = ax3.twinx()
        ax3_twin.bar([i + width/2 for i in x], course_stats['engagement_score'], width, 
                    label='Avg Engagement', color=CONFIG['colors'][1], alpha=0.7)
        
        ax3.set_xlabel('Course')
        ax3.set_ylabel('Average GPA')
        ax3_twin.set_ylabel('Average Engagement Score')
        ax3.set_title('Course Performance Metrics')
        ax3.set_xticks(x)
        ax3.set_xticklabels(course_stats.index)
        ax3.legend(loc='upper left')
        ax3_twin.legend(loc='upper right')
        
        # 4. Age Distribution by Course
        ax4 = fig.add_subplot(334)
        for course in students_df['course'].unique():
            course_ages = students_df[students_df['course'] == course]['age']
            ax4.hist(course_ages, alpha=0.7, label=course, bins=15)
        ax4.set_xlabel('Age')
        ax4.set_ylabel('Number of Students')
        ax4.set_title('Age Distribution by Course')
        ax4.legend()
        
        # 5. Gender Distribution by Course
        ax5 = fig.add_subplot(335)
        gender_course = pd.crosstab(students_df['course'], students_df['gender'])
        gender_course.plot(kind='bar', ax=ax5, color=CONFIG['colors'])
        ax5.set_xlabel('Course')
        ax5.set_ylabel('Number of Students')
        ax5.set_title('Gender Distribution by Course')
        ax5.legend(title='Gender')
        plt.xticks(rotation=45)
        
        # 6. Course Completion Rates
        ax6 = fig.add_subplot(336)
        completion_rates = students_df.groupby('course').apply(
            lambda x: (x['completion_status'] == 'Completed').mean() * 100
        )
        ax6.bar(completion_rates.index, completion_rates.values, color='green', alpha=0.7)
        ax6.set_xlabel('Course')
        ax6.set_ylabel('Completion Rate (%)')
        ax6.set_title('Course Completion Rates')
        
        # 7. Course Capacity Analysis
        ax7 = fig.add_subplot(337)
        enrollment_counts = students_df['course'].value_counts()
        avg_enrollment = enrollment_counts.mean()
        
        colors = ['red' if count < avg_enrollment * 0.7 else 'orange' if count < avg_enrollment else 'green' 
                 for count in enrollment_counts.values]
        
        ax7.bar(enrollment_counts.index, enrollment_counts.values, color=colors, alpha=0.7)
        ax7.axhline(y=avg_enrollment, color='blue', linestyle='--', label=f'Average: {avg_enrollment:.1f}')
        ax7.set_xlabel('Course')
        ax7.set_ylabel('Number of Students')
        ax7.set_title('Course Enrollment vs Average')
        ax7.legend()
        
        # 8. Course Satisfaction (Engagement) Heatmap
        ax8 = fig.add_subplot(338)
        engagement_by_course_age = students_df.groupby(['course', pd.cut(students_df['age'], bins=[0, 25, 35, 45, 100], 
                                                       labels=['18-25', '26-35', '36-45', '46+'])])['engagement_score'].mean().unstack()
        
        im = ax8.imshow(engagement_by_course_age.values, cmap='RdYlGn', aspect='auto')
        ax8.set_xticks(range(len(engagement_by_course_age.columns)))
        ax8.set_yticks(range(len(engagement_by_course_age.index)))
        ax8.set_xticklabels(engagement_by_course_age.columns)
        ax8.set_yticklabels(engagement_by_course_age.index)
        ax8.set_xlabel('Age Group')
        ax8.set_ylabel('Course')
        ax8.set_title('Average Engagement by Course and Age')
        plt.colorbar(im, ax=ax8)
        
        # 9. Course Enrollment Forecast
        ax9 = fig.add_subplot(339)
        if 'registration_datetime' in students_df.columns:
            monthly_total = students_df.groupby('reg_month').size()
            
            if len(monthly_total) > 3:
                # Simple linear forecast
                x_data = range(len(monthly_total))
                y_data = monthly_total.values
                
                z = np.polyfit(x_data, y_data, 1)
                p = np.poly1d(z)
                
                # Forecast next 6 months
                future_months = range(len(monthly_total), len(monthly_total) + 6)
                forecast = [p(month) for month in future_months]
                
                ax9.plot(x_data, y_data, 'o-', label='Historical', color=CONFIG['colors'][0])
                ax9.plot(future_months, forecast, 's--', label='Forecast', color='red')
                ax9.set_xlabel('Time Period')
                ax9.set_ylabel('Total Enrollments')
                ax9.set_title('Enrollment Forecast (Next 6 Months)')
                ax9.legend()
            else:
                ax9.text(0.5, 0.5, 'Insufficient data for forecast', ha='center', va='center', transform=ax9.transAxes)
                ax9.set_title('Enrollment Forecast (Insufficient Data)')
        else:
            ax9.text(0.5, 0.5, 'Registration datetime not available', ha='center', va='center', transform=ax9.transAxes)
            ax9.set_title('Enrollment Forecast (No Data)')
        plt.tight_layout(rect=[0, 0, 1, 0.95])
        
        self.save_or_display_plot(fig, "course_enrollment_analysis")
    
    def analyze_registration_timeline(self):
        """Analyze student registration patterns over time - GUI compatible"""
        students_df = self.get_all_students(self.custom_filters)
        
        if students_df.empty:
            print("No student data available for registration timeline analysis.")
            return
        
        print("\nGenerating Registration Timeline Analysis...")
        
        # Convert registration datetime
        students_df['registration_date'] = pd.to_datetime(students_df['registration_datetime'])
        students_df['reg_year'] = students_df['registration_date'].dt.year
        students_df['reg_month'] = students_df['registration_date'].dt.month
        students_df['reg_day_of_week'] = students_df['registration_date'].dt.day_name()
        students_df['reg_hour'] = students_df['registration_date'].dt.hour
        
        fig = plt.figure(figsize=(20, 15))
        fig.suptitle('Student Registration Timeline Analysis', fontsize=20)
        
        # 1. Registrations Over Time
        ax1 = fig.add_subplot(331)
        monthly_registrations = students_df.groupby(students_df['registration_date'].dt.to_period('M')).size()
        ax1.plot(range(len(monthly_registrations)), monthly_registrations.values, 
                marker='o', color=CONFIG['colors'][0], linewidth=2)
        ax1.set_xlabel('Time Period')
        ax1.set_ylabel('Number of Registrations')
        ax1.set_title('Registration Trends Over Time')
        
        # Continue with other timeline analysis plots...
        plt.tight_layout(rect=[0, 0, 1, 0.95])
        
        self.save_or_display_plot(fig, "registration_timeline_analysis")
    
    def show_system_info(self):
        """Show system information"""
        import platform
        import matplotlib
        
        info = f"""
        System Information:
        
        Platform: {platform.platform()}
        Python Version: {platform.python_version()}
        Matplotlib Version: {matplotlib.__version__}
        GUI Backend: {matplotlib.get_backend()}
        
        Database: {self.analytics.db_path}
        Plots Directory: {self.analytics.plots_dir}
        Reports Directory: {self.analytics.reports_dir}
        """
        messagebox.showinfo("System Information", info)
        
    def test_database(self):
        """Test database connection"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM students")
            count = cursor.fetchone()[0]

            messagebox.showinfo("Database Test", f"Database connection successful!\nFound {count} student records.")

        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            messagebox.showerror("Database Error", f"Database connection failed:\n{str(e)}")

        except Exception as e:
            if conn:
                conn.rollback()
            messagebox.showerror("Database Error", f"Database connection failed:\n{str(e)}")

        finally:
            if conn:
                conn.close()

    def refresh_data(self):
        """Refresh data cache"""
        self.custom_filters.clear()
        self.refresh_stats()
        messagebox.showinfo("Data Refreshed", "Data cache has been refreshed successfully!")
        
    def clear_filters(self):
        """Clear all applied filters"""
        self.analytics.custom_filters.clear()
        self.update_filter_status()
        messagebox.showinfo("Filters Cleared", "All filters have been cleared.")
        
    def update_filter_status(self):
        """Update filter status display"""
        if self.analytics.custom_filters:
            filter_count = len(self.analytics.custom_filters)
            self.filter_status.config(text=f"{filter_count} filter(s) applied")
        else:
            self.filter_status.config(text="No filters applied")
            
    def clear_output(self):
        """Clear the output text area"""
        self.output_text.delete('1.0', 'end')
        
    def save_output(self):
        """Save output to file"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filename:
            with open(filename, 'w') as f:
                f.write(self.output_text.get('1.0', 'end'))
            messagebox.showinfo("Saved", f"Output saved to {filename}")
            
    def copy_output(self):
        """Copy output to clipboard"""
        self.root.clipboard_clear()
        self.root.clipboard_append(self.output_text.get('1.0', 'end'))
        messagebox.showinfo("Copied", "Output copied to clipboard")
        
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
        """Start the GUI application"""
        # Initialize stats on startup
        self.refresh_stats()

        # Start the main loop
        self.root.mainloop()


class FilterDialog:
    """Advanced filters dialog"""
    
    def __init__(self, parent, analytics):
        self.analytics = analytics
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Advanced Filters")
        self.dialog.geometry("500x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_filter_interface()
        
    def create_filter_interface(self):
        """Create the filter interface"""
        # Age range
        age_frame = ttk.LabelFrame(self.dialog, text="Age Range", padding=10)
        age_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(age_frame, text="Min Age:").grid(row=0, column=0, sticky='w')
        self.min_age = ttk.Entry(age_frame, width=10)
        self.min_age.grid(row=0, column=1, padx=5)
        
        ttk.Label(age_frame, text="Max Age:").grid(row=0, column=2, sticky='w', padx=(20,0))
        self.max_age = ttk.Entry(age_frame, width=10)
        self.max_age.grid(row=0, column=3, padx=5)
        
        # GPA range
        gpa_frame = ttk.LabelFrame(self.dialog, text="GPA Range", padding=10)
        gpa_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(gpa_frame, text="Min GPA:").grid(row=0, column=0, sticky='w')
        self.min_gpa = ttk.Entry(gpa_frame, width=10)
        self.min_gpa.grid(row=0, column=1, padx=5)
        
        ttk.Label(gpa_frame, text="Max GPA:").grid(row=0, column=2, sticky='w', padx=(20,0))
        self.max_gpa = ttk.Entry(gpa_frame, width=10)
        self.max_gpa.grid(row=0, column=3, padx=5)
        
        # Course selection
        course_frame = ttk.LabelFrame(self.dialog, text="Course Selection", padding=10)
        course_frame.pack(fill='x', padx=10, pady=5)
        
        self.course_var = tk.StringVar()
        self.course_combo = ttk.Combobox(course_frame, textvariable=self.course_var)
        self.course_combo.pack(fill='x')
        
        # Load courses
        try:
            students_df = self.analytics.get_all_students()
            courses = ['All Courses'] + list(students_df['course'].unique())
            self.course_combo['values'] = courses
            self.course_combo.set('All Courses')
        except:
            self.course_combo['values'] = ['All Courses']
            self.course_combo.set('All Courses')
        
        # Gender selection
        gender_frame = ttk.LabelFrame(self.dialog, text="Gender", padding=10)
        gender_frame.pack(fill='x', padx=10, pady=5)
        
        self.gender_var = tk.StringVar()
        self.gender_combo = ttk.Combobox(gender_frame, textvariable=self.gender_var)
        self.gender_combo['values'] = ['All', 'Male', 'Female', 'Other']
        self.gender_combo.set('All')
        self.gender_combo.pack(fill='x')
        
        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill='x', padx=10, pady=20)
        
        ttk.Button(button_frame, text="Apply Filters", 
                  command=self.apply_filters).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Clear All", 
                  command=self.clear_filters).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", 
                  command=self.dialog.destroy).pack(side='right', padx=5)
        
    def apply_filters(self):
        """Apply the selected filters"""
        filters = {}
        
        # Age range
        if self.min_age.get() and self.max_age.get():
            try:
                min_age = int(self.min_age.get())
                max_age = int(self.max_age.get())
                filters['age_range'] = [min_age, max_age]
            except ValueError:
                messagebox.showerror("Invalid Input", "Please enter valid age values")
                return
        
        # GPA range
        if self.min_gpa.get() and self.max_gpa.get():
            try:
                min_gpa = float(self.min_gpa.get())
                max_gpa = float(self.max_gpa.get())
                filters['gpa_range'] = [min_gpa, max_gpa]
            except ValueError:
                messagebox.showerror("Invalid Input", "Please enter valid GPA values")
                return
        
        # Course selection
        if self.course_var.get() != 'All Courses':
            filters['course'] = self.course_var.get()
        
        # Gender selection
        if self.gender_var.get() != 'All':
            filters['gender'] = self.gender_var.get()
        
        # Apply filters to analytics
        self.analytics.custom_filters.update(filters)
        
        messagebox.showinfo("Filters Applied", f"Applied {len(filters)} filter(s)")
        self.dialog.destroy()
        
    def clear_filters(self):
        """Clear all filter inputs"""
        self.min_age.delete(0, 'end')
        self.max_age.delete(0, 'end')
        self.min_gpa.delete(0, 'end')
        self.max_gpa.delete(0, 'end')
        self.course_combo.set('All Courses')
        self.gender_combo.set('All')


class CustomReportDialog:
    """Custom report builder dialog"""
    
    def __init__(self, parent, analytics):
        self.analytics = analytics
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Custom Report Builder")
        self.dialog.geometry("600x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.selected_components = []
        self.create_report_interface()
        
    def create_report_interface(self):
        """Create the custom report interface"""
        # Title
        title_label = ttk.Label(self.dialog, text="Custom Report Builder", 
                               font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)
        
        # Report name
        name_frame = ttk.Frame(self.dialog)
        name_frame.pack(fill='x', padx=20, pady=5)
        
        ttk.Label(name_frame, text="Report Name:").pack(side='left')
        self.report_name = ttk.Entry(name_frame, width=30)
        self.report_name.pack(side='left', padx=10)
        self.report_name.insert(0, f"Custom_Report_{datetime.now().strftime('%Y%m%d')}")
        
        # Component selection
        components_frame = ttk.LabelFrame(self.dialog, text="Select Components", padding=10)
        components_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        # Create scrollable frame for components
        canvas = tk.Canvas(components_frame)
        scrollbar = ttk.Scrollbar(components_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Component checkboxes
        self.component_vars = {}
        components = [
            ('demographics', 'Student Demographics', 'Age, gender, course distribution'),
            ('grades', 'Grade Distribution', 'Academic performance analysis'),
            ('modules', 'Module Popularity', 'Most popular modules and trends'),
            ('trends', 'Performance Trends', 'Performance changes over time'),
            ('engagement', 'Engagement Analysis', 'Student engagement patterns'),
            ('risk', 'Risk Assessment', 'Academic risk identification'),
            ('cohorts', 'Cohort Analysis', 'Student cohort comparisons'),
            ('correlations', 'Correlation Analysis', 'Variable relationships')
        ]
        
        for i, (key, title, description) in enumerate(components):
            frame = ttk.Frame(scrollable_frame)
            frame.pack(fill='x', pady=2)
            
            var = tk.BooleanVar()
            self.component_vars[key] = var
            
            cb = ttk.Checkbutton(frame, text=title, variable=var)
            cb.pack(side='left')
            
            desc_label = ttk.Label(frame, text=f"- {description}", foreground='gray')
            desc_label.pack(side='left', padx=10)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Options
        options_frame = ttk.LabelFrame(self.dialog, text="Report Options", padding=10)
        options_frame.pack(fill='x', padx=20, pady=5)
        
        self.include_summary = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Include Executive Summary", 
                       variable=self.include_summary).pack(anchor='w')
        
        self.include_recommendations = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Include Recommendations", 
                       variable=self.include_recommendations).pack(anchor='w')
        
        # Format selection
        format_frame = ttk.Frame(options_frame)
        format_frame.pack(fill='x', pady=5)
        
        ttk.Label(format_frame, text="Output Format:").pack(side='left')
        self.format_var = tk.StringVar(value='PDF')
        format_combo = ttk.Combobox(format_frame, textvariable=self.format_var, 
                                   values=['PDF', 'HTML', 'Word'], state='readonly')
        format_combo.pack(side='left', padx=10)
        
        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill='x', padx=20, pady=20)
        
        ttk.Button(button_frame, text="Generate Report", 
                  command=self.generate_report).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Select All", 
                  command=self.select_all).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Clear All", 
                  command=self.clear_all).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", 
                  command=self.dialog.destroy).pack(side='right', padx=5)
        
    def select_all(self):
        """Select all components"""
        for var in self.component_vars.values():
            var.set(True)
            
    def clear_all(self):
        """Clear all component selections"""
        for var in self.component_vars.values():
            var.set(False)
            
    def generate_report(self):
        """Generate the custom report"""
        # Get selected components
        selected = [key for key, var in self.component_vars.items() if var.get()]
        
        if not selected:
            messagebox.showwarning("No Components Selected", 
                                 "Please select at least one component for the report.")
            return
        
        report_name = self.report_name.get()
        if not report_name:
            messagebox.showwarning("No Report Name", "Please enter a report name.")
            return
        
        # Close dialog and generate report
        self.dialog.destroy()
        
        # Start report generation in thread
        def generate():
            try:
                print(f"\nGenerating custom report: {report_name}")
                print(f"Selected components: {', '.join(selected)}")
                print(f"Include summary: {self.include_summary.get()}")
                print(f"Format: {self.format_var.get()}")
                
                # Generate selected analyses
                analysis_map = {
                    'demographics': self.analytics.analyze_student_demographics,
                    'grades': self.analytics.analyze_grade_distribution,
                    'modules': self.analytics.analyze_module_popularity,
                    'trends': self.analytics.analyze_performance_trends,
                    'engagement': self.analytics.analyze_engagement,
                    'risk': self.analytics.analyze_academic_risk,
                    'cohorts': self.analytics.analyze_cohorts,
                    'correlations': self.analytics.analyze_correlations
                }
                
                for component in selected:
                    if component in analysis_map:
                        print(f"\nGenerating {component}...")
                        analysis_map[component]()
                
                print(f"\nCustom report '{report_name}' generated successfully!")
                
                # Show completion message in main thread
                self.dialog.after(0, lambda: messagebox.showinfo(
                    "Report Generated", 
                    f"Custom report '{report_name}' has been generated successfully!"
                ))
                
            except Exception as e:
                import traceback
                error_msg = f"Error generating report: {str(e)}\n\n{traceback.format_exc()}"
                print(error_msg)
                messagebox.showerror("Report Error", error_msg)

        # Run in main thread instead of daemon thread
        generate()


class ConfigDialog:
    """Configuration settings dialog"""
    
    def __init__(self, parent, analytics):
        self.analytics = analytics
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Configuration Settings")
        self.dialog.geometry("500x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_config_interface()
        
    def create_config_interface(self):
        """Create the configuration interface"""
        notebook = ttk.Notebook(self.dialog)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # General settings tab
        general_tab = ttk.Frame(notebook)
        notebook.add(general_tab, text="General")
        
        # Plot settings
        plot_frame = ttk.LabelFrame(general_tab, text="Plot Settings", padding=10)
        plot_frame.pack(fill='x', pady=5)
        
        ttk.Label(plot_frame, text="Figure Width:").grid(row=0, column=0, sticky='w')
        self.fig_width = ttk.Entry(plot_frame, width=10)
        self.fig_width.grid(row=0, column=1, padx=5)
        self.fig_width.insert(0, str(CONFIG['figure_size'][0]))
        
        ttk.Label(plot_frame, text="Figure Height:").grid(row=0, column=2, sticky='w', padx=(20,0))
        self.fig_height = ttk.Entry(plot_frame, width=10)
        self.fig_height.grid(row=0, column=3, padx=5)
        self.fig_height.insert(0, str(CONFIG['figure_size'][1]))
        
        ttk.Label(plot_frame, text="DPI:").grid(row=1, column=0, sticky='w', pady=5)
        self.dpi = ttk.Entry(plot_frame, width=10)
        self.dpi.grid(row=1, column=1, padx=5, pady=5)
        self.dpi.insert(0, str(CONFIG['dpi']))
        
        # Export settings
        export_frame = ttk.LabelFrame(general_tab, text="Export Settings", padding=10)
        export_frame.pack(fill='x', pady=5)
        
        ttk.Label(export_frame, text="Default Export Formats:").pack(anchor='w')
        
        self.format_vars = {}
        formats = ['png', 'pdf', 'svg', 'excel']
        for fmt in formats:
            var = tk.BooleanVar(value=fmt in CONFIG['export_formats'])
            self.format_vars[fmt] = var
            ttk.Checkbutton(export_frame, text=fmt.upper(), variable=var).pack(anchor='w')
        
        # Email settings tab
        email_tab = ttk.Frame(notebook)
        notebook.add(email_tab, text="Email")
        
        email_frame = ttk.LabelFrame(email_tab, text="Email Configuration", padding=10)
        email_frame.pack(fill='both', expand=True, pady=5)
        
        ttk.Label(email_frame, text="Sender Email:").grid(row=0, column=0, sticky='w', pady=5)
        self.sender_email = ttk.Entry(email_frame, width=30)
        self.sender_email.grid(row=0, column=1, padx=5, pady=5)
        self.sender_email.insert(0, CONFIG['email_config']['sender_email'])
        
        ttk.Label(email_frame, text="SMTP Server:").grid(row=1, column=0, sticky='w', pady=5)
        self.smtp_server = ttk.Entry(email_frame, width=30)
        self.smtp_server.grid(row=1, column=1, padx=5, pady=5)
        self.smtp_server.insert(0, CONFIG['email_config']['smtp_server'])
        
        ttk.Label(email_frame, text="SMTP Port:").grid(row=2, column=0, sticky='w', pady=5)
        self.smtp_port = ttk.Entry(email_frame, width=30)
        self.smtp_port.grid(row=2, column=1, padx=5, pady=5)
        self.smtp_port.insert(0, str(CONFIG['email_config']['smtp_port']))
        
        ttk.Label(email_frame, text="Password:").grid(row=3, column=0, sticky='w', pady=5)
        self.password = ttk.Entry(email_frame, width=30, show='*')
        self.password.grid(row=3, column=1, padx=5, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(button_frame, text="Save Settings", 
                  command=self.save_settings).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Reset to Defaults", 
                  command=self.reset_defaults).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", 
                  command=self.dialog.destroy).pack(side='right', padx=5)
        
    def save_settings(self):
        """Save the configuration settings"""
        try:
            # Update plot settings
            CONFIG['figure_size'] = (int(self.fig_width.get()), int(self.fig_height.get()))
            CONFIG['dpi'] = int(self.dpi.get())
            
            # Update export formats
            CONFIG['export_formats'] = [fmt for fmt, var in self.format_vars.items() if var.get()]
            
            # Update email settings
            CONFIG['email_config']['sender_email'] = self.sender_email.get()
            CONFIG['email_config']['smtp_server'] = self.smtp_server.get()
            CONFIG['email_config']['smtp_port'] = int(self.smtp_port.get())
            if self.password.get():
                CONFIG['email_config']['sender_password'] = self.password.get()
            
            messagebox.showinfo("Settings Saved", "Configuration settings have been saved successfully!")
            self.dialog.destroy()
            
        except ValueError as e:
            messagebox.showerror("Invalid Input", "Please check your input values.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {str(e)}")
            
    def reset_defaults(self):
        """Reset settings to defaults"""
        # Reset plot settings
        self.fig_width.delete(0, 'end')
        self.fig_width.insert(0, '15')
        self.fig_height.delete(0, 'end')
        self.fig_height.insert(0, '10')
        self.dpi.delete(0, 'end')
        self.dpi.insert(0, '300')
        
        # Reset export formats
        default_formats = ['png', 'pdf', 'svg', 'excel']
        for fmt, var in self.format_vars.items():
            var.set(fmt in default_formats)
        
        # Reset email settings
        self.sender_email.delete(0, 'end')
        self.smtp_server.delete(0, 'end')
        self.smtp_server.insert(0, 'smtp.gmail.com')
        self.smtp_port.delete(0, 'end')
        self.smtp_port.insert(0, '587')
        self.password.delete(0, 'end')


# Extension to original StudentAnalytics class
def add_gui_methods():
    """Add GUI-compatible methods to the original StudentAnalytics class"""
    
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

    def export_data_choice(self, choice):
        """Handle export data choice for GUI"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        students_df = self.get_all_students(self.custom_filters)
        modules_df = self.get_all_modules(self.custom_filters)
        
        if choice == '1':
            # Excel export
            filename = f"{self.reports_dir}/student_data_export_{timestamp}.xlsx"
            
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                students_df.to_excel(writer, sheet_name='Students', index=False)
                
                if not modules_df.empty:
                    modules_df.to_excel(writer, sheet_name='Modules', index=False)
                
                # Summary statistics
                summary_data = {
                    'Metric': ['Total Students', 'Average GPA', 'Average Engagement', 'Completion Rate'],
                    'Value': [
                        len(students_df),
                        students_df['gpa'].mean(),
                        students_df['engagement_score'].mean(),
                        (students_df['completion_status'] == 'Completed').mean() * 100
                    ]
                }
                pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)
            
            print(f"Excel export completed: {filename}")
            
        elif choice == '2':
            # CSV export
            students_filename = f"{self.reports_dir}/students_{timestamp}.csv"
            students_df.to_csv(students_filename, index=False)
            print(f"Students CSV exported: {students_filename}")
            
            if not modules_df.empty:
                modules_filename = f"{self.reports_dir}/modules_{timestamp}.csv"
                modules_df.to_csv(modules_filename, index=False)
                print(f"Modules CSV exported: {modules_filename}")
                
        elif choice == '3':
            # JSON export
            filename = f"{self.reports_dir}/student_data_{timestamp}.json"
            export_data = {
                'students': students_df.to_dict('records'),
                'modules': modules_df.to_dict('records') if not modules_df.empty else [],
                'export_metadata': {
                    'timestamp': timestamp,
                    'total_students': len(students_df),
                    'total_modules': len(modules_df)
                }
            }
            
            with open(filename, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
            
            print(f"JSON export completed: {filename}")
            
        elif choice == '4':
            # Statistical summary
            self.generate_statistical_summary_report(students_df, modules_df, timestamp)
    
    # Add the method to the class
    StudentAnalytics.export_data_choice = export_data_choice


def launch_gui(auth_manager=None):
    """Launch the GUI version of Student Analytics with optional auth"""
    print("Launching Enhanced Student Analytics GUI...")
    
    # Add GUI methods to existing class
    add_gui_methods()
    
    # Create and run GUI with auth context
    app = GUIStudentAnalytics(auth_manager)
    app.run()

def main():
    """Main function with backward compatibility"""
    import sys
    
    # Check if GUI mode is requested
    if len(sys.argv) > 1 and sys.argv[1] in ['--gui', '-g', 'gui']:
        launch_gui()
    else:
        # Run original command-line interface
        analytics = StudentAnalytics()
        analytics.display_main_menu()

def get_gui_analytics_class():
    """Return the GUIStudentAnalytics class for integration"""
    return GUIStudentAnalytics

def integrate_with_main_system(main_gui_instance, auth_manager):
    """Integrate analytics with main GUI system"""
    try:
        # Create analytics instance
        analytics_gui = GUIStudentAnalytics()
        
        # Set auth context
        if hasattr(analytics_gui, 'auth'):
            analytics_gui.auth = auth_manager
        
        return analytics_gui
    except Exception as e:
        print(f"Failed to integrate analytics: {e}")
        return None

# Entry point with backward compatibility
if __name__ == "__main__":
    # Check if GUI libraries are available
    try:
        import tkinter
        gui_available = True
    except ImportError:
        gui_available = False
        print("GUI libraries not available. Running in command-line mode.")
    
    # Ask user for interface preference if GUI is available
    if gui_available:
        print("\nEnhanced Student Analytics Dashboard")
        print("=====================================")
        print("Choose interface:")
        print("1. GUI Mode (Recommended)")
        print("2. Command Line Mode (Classic)")
        
        choice = input("\nSelect interface (1 or 2, or press Enter for GUI): ").strip()
        
        if choice == '2':
            # Run command-line version
            analytics = StudentAnalytics()
            analytics.display_main_menu()
        else:
            # Run GUI version (default) - now with None for auth since standalone
            launch_gui(None)
    else:
        # Fall back to command-line mode
        analytics = StudentAnalytics()
        analytics.display_main_menu()
