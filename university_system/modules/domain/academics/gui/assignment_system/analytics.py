"""Analytics and reporting"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import shutil
import threading
from datetime import datetime, timedelta
from pathlib import Path
import json
import csv
from PIL import Image, ImageTk
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import seaborn as sns
from university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH
from university_system.infrastructure.auth.user_authentication import UserAuth
from university_system.modules.shared.constants import paths
from collections import deque



class AnalyticsManager:
    """Analytics and reporting"""

    def __init__(self, gui):
        """Initialize manager with reference to main GUI"""
        self.gui = gui
        self.root = gui.root
        self.auth = gui.auth
        self.assignment_system = gui.assignment_system
        self.style = gui.style

    def _check_permission(self, permission):
        """Check if user has permission"""
        try:
            return self.auth.check_permission(permission)
        except:
            return self.auth.user_role in ['Admin', 'Faculty']

    def show_analytics(self):
        """Show analytics dashboard with charts"""
        self.gui.layout.clear_content_area()
        
        title = ttk.Label(self.gui.layout.content_area, text="Analytics Dashboard", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))
        
        # Create notebook for different analytics views
        notebook = ttk.Notebook(self.gui.layout.content_area)
        notebook.pack(fill='both', expand=True)
        
        # Overview tab
        overview_frame = ttk.Frame(notebook)
        notebook.add(overview_frame, text="Overview")
        
        # Grades tab
        grades_frame = ttk.Frame(notebook)
        notebook.add(grades_frame, text="Grade Distribution")
        
        # Submissions tab
        submissions_frame = ttk.Frame(notebook)
        notebook.add(submissions_frame, text="Submission Trends")
        
        # Create analytics content
        self.create_overview_analytics(overview_frame)
        self.create_grade_analytics(grades_frame)
        self.create_submission_analytics(submissions_frame)
    

    def create_overview_analytics(self, parent):
        """Create overview analytics"""
        # Statistics summary
        stats_frame = ttk.LabelFrame(parent, text="System Statistics", padding=10)
        stats_frame.pack(fill='x', padx=10, pady=10)
        
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            # Get various statistics
            stats_queries = [
                ("Total Assignments", "SELECT COUNT(*) FROM assignments WHERE is_active = 1"),
                ("Total Submissions", "SELECT COUNT(*) FROM assignment_submissions"),
                ("Graded Submissions", "SELECT COUNT(*) FROM assignment_submissions WHERE grade IS NOT NULL"),
                ("Late Submissions", "SELECT COUNT(*) FROM assignment_submissions WHERE late_submission = 1"),
                ("Active Students", "SELECT COUNT(DISTINCT student_id) FROM assignment_submissions"),
                ("Average Grade", "SELECT AVG(grade) FROM assignment_submissions WHERE grade IS NOT NULL")
            ]
            
            # Create grid layout for stats
            for i, (label, query) in enumerate(stats_queries):
                cursor.execute(query)
                result = cursor.fetchone()[0]
                
                if label == "Average Grade" and result:
                    value = f"{result:.1f}%"
                else:
                    value = str(result or 0)
                
                row = i // 3
                col = (i % 3) * 2
                
                ttk.Label(stats_frame, text=f"{label}:", font=('Arial', 10, 'bold')).grid(
                    row=row, column=col, sticky='w', padx=5, pady=5)
                ttk.Label(stats_frame, text=value).grid(
                    row=row, column=col+1, sticky='w', padx=5, pady=5)
            
            conn.close()
            
        except Exception as e:
            ttk.Label(stats_frame, text=f"Error loading statistics: {e}").pack()
        
        # Recent activity
        activity_frame = ttk.LabelFrame(parent, text="Recent Activity", padding=10)
        activity_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Activity tree
        activity_tree = ttk.Treeview(activity_frame, columns=('Type', 'Description', 'Date'), show='headings')
        activity_tree.heading('Type', text='Type')
        activity_tree.heading('Description', text='Description')
        activity_tree.heading('Date', text='Date')
        
        activity_tree.pack(fill='both', expand=True)
        
        # Load recent activity
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT 'Submission' as type, 
                   'New submission for ' || a.title as description,
                   s.submission_date as date
            FROM assignment_submissions s
            JOIN assignments a ON s.assignment_id = a.id
            ORDER BY s.submission_date DESC
            LIMIT 20
            ''')
            
            activities = cursor.fetchall()
            for activity in activities:
                activity_tree.insert('', 'end', values=activity)
            
            conn.close()
            
        except Exception as e:
            print(f"Error loading activity: {e}")
    

    def create_grade_analytics(self, parent):
        """Create grade distribution analytics with charts"""
        try:
            # Create matplotlib figure
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))
            fig.patch.set_facecolor('#f0f0f0')
            
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            # Grade distribution
            cursor.execute('''
            SELECT 
                CASE 
                    WHEN grade >= 90 THEN 'A (90-100%)'
                    WHEN grade >= 80 THEN 'B (80-89%)'
                    WHEN grade >= 70 THEN 'C (70-79%)'
                    WHEN grade >= 60 THEN 'D (60-69%)'
                    ELSE 'F (Below 60%)'
                END as grade_band,
                COUNT(*) as count
            FROM assignment_submissions
            WHERE grade IS NOT NULL
            GROUP BY grade_band
            ORDER BY grade_band
            ''')
            
            grade_data = cursor.fetchall()
            
            if grade_data:
                labels, counts = zip(*grade_data)
                colors = ['#2ecc71', '#3498db', '#f39c12', '#e74c3c', '#95a5a6']
                
                # Pie chart
                ax1.pie(counts, labels=labels, autopct='%1.1f%%', colors=colors[:len(labels)])
                ax1.set_title('Grade Distribution')
                
                # Bar chart
                ax2.bar(labels, counts, color=colors[:len(labels)])
                ax2.set_title('Grade Counts')
                ax2.set_ylabel('Number of Students')
                plt.setp(ax2.get_xticklabels(), rotation=45, ha='right')
            
            # Module-wise average grades
            cursor.execute('''
            SELECT a.module_code, AVG(s.grade) as avg_grade
            FROM assignment_submissions s
            JOIN assignments a ON s.assignment_id = a.id
            WHERE s.grade IS NOT NULL
            GROUP BY a.module_code
            ORDER BY avg_grade DESC
            ''')
            
            module_data = cursor.fetchall()
            
            conn.close()
            
            # Embed plot in tkinter
            canvas = FigureCanvasTkAgg(fig, parent)
            canvas.draw()
            canvas.get_tk_widget().pack(fill='both', expand=True, padx=10, pady=10)
            
            # Module performance table
            if module_data:
                module_frame = ttk.LabelFrame(parent, text="Module Performance", padding=10)
                module_frame.pack(fill='x', padx=10, pady=10)
                
                module_tree = ttk.Treeview(module_frame, columns=('Module', 'Average Grade'), show='headings')
                module_tree.heading('Module', text='Module')
                module_tree.heading('Average Grade', text='Average Grade')
                
                for module, avg_grade in module_data:
                    module_tree.insert('', 'end', values=(module, f"{avg_grade:.1f}%"))
                
                module_tree.pack(fill='x')
            
        except Exception as e:
            error_label = ttk.Label(parent, text=f"Error creating grade analytics: {e}")
            error_label.pack(padx=10, pady=10)
    

    def create_submission_analytics(self, parent):
        """Create submission trend analytics"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            # Submissions over time
            cursor.execute('''
            SELECT DATE(submission_date) as date, COUNT(*) as count
            FROM assignment_submissions
            WHERE submission_date >= date('now', '-30 days')
            GROUP BY DATE(submission_date)
            ORDER BY date
            ''')
            
            submission_data = cursor.fetchall()

            if submission_data and len(submission_data) > 0:
                # Create line chart
                fig, ax = plt.subplots(figsize=(12, 6))
                fig.patch.set_facecolor('#f0f0f0')

                dates, counts = zip(*submission_data)
                dates = [datetime.strptime(date, '%Y-%m-%d') for date in dates]

                ax.plot(dates, counts, marker='o', linewidth=2, markersize=6, color='#3498db')
                ax.set_title('Submission Trends (Last 30 Days)', fontsize=14, fontweight='bold')
                ax.set_xlabel('Date', fontsize=11)
                ax.set_ylabel('Number of Submissions', fontsize=11)
                ax.grid(True, alpha=0.3)

                # Format x-axis
                plt.setp(ax.get_xticklabels(), rotation=45, ha='right')
                plt.tight_layout()

                # Embed plot
                canvas = FigureCanvasTkAgg(fig, parent)
                canvas.draw()
                canvas.get_tk_widget().pack(fill='both', expand=True, padx=10, pady=10)
            else:
                # Show message when no data available
                no_data_frame = ttk.Frame(parent)
                no_data_frame.pack(fill='both', expand=True, padx=10, pady=50)

                ttk.Label(no_data_frame, text="No Submission Data Available",
                         font=('Arial', 14, 'bold')).pack(pady=10)
                ttk.Label(no_data_frame, text="No submissions have been made in the last 30 days.",
                         font=('Arial', 11)).pack(pady=5)
                ttk.Label(no_data_frame, text="Submit some assignments to see trends appear here.",
                         font=('Arial', 10), foreground='gray').pack(pady=5)

            # Late submission statistics
            cursor.execute('''
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN late_submission = 1 THEN 1 END) as late_count
            FROM assignment_submissions
            ''')
            
            total, late_count = cursor.fetchone()
            
            stats_frame = ttk.LabelFrame(parent, text="Submission Statistics", padding=10)
            stats_frame.pack(fill='x', padx=10, pady=10)
            
            if total > 0:
                late_percentage = (late_count / total) * 100
                ttk.Label(stats_frame, text=f"Total Submissions: {total}").pack(anchor='w')
                ttk.Label(stats_frame, text=f"Late Submissions: {late_count} ({late_percentage:.1f}%)").pack(anchor='w')
                ttk.Label(stats_frame, text=f"On-time Submissions: {total - late_count} ({100 - late_percentage:.1f}%)").pack(anchor='w')
            
            conn.close()
            
        except Exception as e:
            error_label = ttk.Label(parent, text=f"Error creating submission analytics: {e}")
            error_label.pack(padx=10, pady=10)
    

    def generate_advanced_analytics(self):
        """Generate advanced analytics with custom parameters"""
        if not self._check_permission('view_all_submissions'):
            return
        
        self.gui.layout.clear_content_area()
        
        title = ttk.Label(self.gui.layout.content_area, text="Advanced Analytics", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))
        
        # Parameters frame
        params_frame = ttk.LabelFrame(self.gui.layout.content_area, text="Analysis Parameters", padding=10)
        params_frame.pack(fill='x', pady=(0, 10))
        
        # Date range
        date_frame = ttk.Frame(params_frame)
        date_frame.pack(fill='x', pady=5)
        
        ttk.Label(date_frame, text="Date Range:").pack(side='left')
        self.start_date_var = tk.StringVar(value="2024-01-01")
        self.end_date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        
        ttk.Entry(date_frame, textvariable=self.start_date_var, width=12).pack(side='left', padx=5)
        ttk.Label(date_frame, text="to").pack(side='left')
        ttk.Entry(date_frame, textvariable=self.end_date_var, width=12).pack(side='left', padx=5)
        
        # Module filter
        module_frame = ttk.Frame(params_frame)
        module_frame.pack(fill='x', pady=5)
        
        ttk.Label(module_frame, text="Module:").pack(side='left')
        self.module_filter_var = tk.StringVar()
        module_combo = ttk.Combobox(module_frame, textvariable=self.module_filter_var)
        module_combo.pack(side='left', padx=5)
        
        # Load modules
        self.load_modules_for_filter(module_combo)
        
        # Analysis type
        analysis_frame = ttk.Frame(params_frame)
        analysis_frame.pack(fill='x', pady=5)
        
        ttk.Label(analysis_frame, text="Analysis Type:").pack(side='left')
        self.analysis_type_var = tk.StringVar(value="performance")
        
        analysis_types = [
            ("Performance Trends", "performance"),
            ("Submission Patterns", "submissions"),
            ("Grade Distribution", "grades"),
            ("Late Submission Analysis", "late_analysis"),
            ("Student Engagement", "engagement")
        ]
        
        for text, value in analysis_types:
            ttk.Radiobutton(analysis_frame, text=text, variable=self.analysis_type_var, 
                           value=value).pack(side='left', padx=10)
        
        # Generate button
        ttk.Button(params_frame, text="Generate Analysis", 
                  command=self.generate_custom_analysis).pack(pady=10)
        
        # Results frame
        self.analysis_results_frame = ttk.Frame(self.gui.layout.content_area)
        self.analysis_results_frame.pack(fill='both', expand=True)
    

    def load_modules_for_filter(self, combo):
        """Load modules for filtering"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            cursor.execute('SELECT module_code, module_name FROM modules ORDER BY module_code')
            modules = cursor.fetchall()
            
            module_list = ["All Modules"] + [f"{code} - {name}" for code, name in modules]
            combo['values'] = module_list
            combo.set("All Modules")
            
            conn.close()
            
        except Exception as e:
            print(f"Error loading modules: {e}")
    

    def generate_custom_analysis(self):
        """Generate custom analysis based on parameters"""
        # Clear previous results
        for widget in self.analysis_results_frame.winfo_children():
            widget.destroy()
        
        analysis_type = self.analysis_type_var.get()
        
        try:
            # Create results display
            results_label = ttk.Label(self.analysis_results_frame, 
                                    text=f"Analysis Results: {analysis_type.title()}", 
                                    style='Header.TLabel')
            results_label.pack(anchor='w', pady=(0, 10))
            
            # Generate specific analysis
            if analysis_type == "performance":
                self.generate_performance_analysis()
            elif analysis_type == "submissions":
                self.generate_submission_patterns()
            elif analysis_type == "grades":
                self.generate_grade_distribution()
            elif analysis_type == "late_analysis":
                self.generate_late_submission_analysis()
            elif analysis_type == "engagement":
                self.generate_engagement_analysis()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate analysis: {e}")
    

    def generate_performance_analysis(self):
        """Generate performance trend analysis"""
        # Create matplotlib figure for performance trends
        try:
            fig, ax = plt.subplots(figsize=(10, 6))
            fig.patch.set_facecolor('#f0f0f0')
            
            # Sample data (replace with actual database query)
            months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun']
            avg_grades = [75, 78, 82, 79, 85, 88]
            
            ax.plot(months, avg_grades, marker='o', linewidth=2, markersize=8)
            ax.set_title('Average Grade Trends Over Time')
            ax.set_xlabel('Month')
            ax.set_ylabel('Average Grade (%)')
            ax.grid(True, alpha=0.3)
            
            # Embed plot
            canvas = FigureCanvasTkAgg(fig, self.analysis_results_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill='both', expand=True)
            
        except Exception as e:
            ttk.Label(self.analysis_results_frame, text=f"Error generating chart: {e}").pack()
    

    def generate_submission_patterns(self):
        """Generate submission pattern analysis"""
        patterns_frame = ttk.LabelFrame(self.analysis_results_frame, text="Submission Patterns", padding=10)
        patterns_frame.pack(fill='both', expand=True)
        
        # Sample pattern data
        patterns = [
            ("Peak submission time", "6-8 PM"),
            ("Most active day", "Sunday"),
            ("Average time before deadline", "2.3 days"),
            ("Late submission rate", "15.2%")
        ]
        
        for pattern, value in patterns:
            pattern_frame = ttk.Frame(patterns_frame)
            pattern_frame.pack(fill='x', pady=2)
            
            ttk.Label(pattern_frame, text=f"{pattern}:", font=('Arial', 10, 'bold')).pack(side='left')
            ttk.Label(pattern_frame, text=value).pack(side='right')
    

    def generate_grade_distribution(self):
        """Generate grade distribution analysis"""
        # Create pie chart for grade distribution
        try:
            fig, ax = plt.subplots(figsize=(8, 6))
            fig.patch.set_facecolor('#f0f0f0')
            
            # Sample grade distribution
            grades = ['A (90-100%)', 'B (80-89%)', 'C (70-79%)', 'D (60-69%)', 'F (<60%)']
            counts = [25, 35, 20, 15, 5]
            colors = ['#2ecc71', '#3498db', '#f39c12', '#e67e22', '#e74c3c']
            
            ax.pie(counts, labels=grades, autopct='%1.1f%%', colors=colors, startangle=90)
            ax.set_title('Grade Distribution')
            
            # Embed plot
            canvas = FigureCanvasTkAgg(fig, self.analysis_results_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill='both', expand=True)
            
        except Exception as e:
            ttk.Label(self.analysis_results_frame, text=f"Error generating chart: {e}").pack()
    

    def generate_late_submission_analysis(self):
        """Generate late submission analysis"""
        late_frame = ttk.LabelFrame(self.analysis_results_frame, text="Late Submission Analysis", padding=10)
        late_frame.pack(fill='both', expand=True)
        
        # Sample late submission data
        stats = [
            ("Total submissions", "247"),
            ("Late submissions", "38 (15.4%)"),
            ("Average delay", "2.1 days"),
            ("Most common delay", "1 day"),
            ("Weekend submissions", "65% of late submissions")
        ]
        
        for stat, value in stats:
            stat_frame = ttk.Frame(late_frame)
            stat_frame.pack(fill='x', pady=3)
            
            ttk.Label(stat_frame, text=f"{stat}:", font=('Arial', 10, 'bold')).pack(side='left')
            ttk.Label(stat_frame, text=value).pack(side='right')
    

    def generate_engagement_analysis(self):
        """Generate student engagement analysis"""
        engagement_frame = ttk.LabelFrame(self.analysis_results_frame, text="Student Engagement", padding=10)
        engagement_frame.pack(fill='both', expand=True)
        
        # Sample engagement metrics
        metrics = [
            ("Active students", "89%"),
            ("Regular submitters", "76%"),
            ("Early submitters", "34%"),
            ("Help requests", "12 per week"),
            ("Peer review participation", "82%")
        ]
        
        for metric, value in metrics:
            metric_frame = ttk.Frame(engagement_frame)
            metric_frame.pack(fill='x', pady=3)
            
            ttk.Label(metric_frame, text=f"{metric}:", font=('Arial', 10, 'bold')).pack(side='left')
            ttk.Label(metric_frame, text=value).pack(side='right')
    

    def generate_custom_reports(self):
        """Generate custom reports"""
        if not self._check_permission('view_all_submissions'):
            return
        
        self.gui.layout.clear_content_area()
        
        title = ttk.Label(self.gui.layout.content_area, text="Custom Reports", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))
        
        # Report options
        options_frame = ttk.LabelFrame(self.gui.layout.content_area, text="Report Options", padding=20)
        options_frame.pack(fill='x', pady=(0, 20))
        
        # Report type
        self.report_type_var = tk.StringVar(value="student_performance")
        report_types = [
            ("Student Performance Report", "student_performance"),
            ("Assignment Statistics Report", "assignment_stats"),
            ("Module Summary Report", "module_summary"),
            ("Submission Timeline Report", "submission_timeline"),
            ("Grade Analysis Report", "grade_analysis")
        ]
        
        ttk.Label(options_frame, text="Report Type:", font=('Arial', 12, 'bold')).pack(anchor='w', pady=(0, 10))
        
        for text, value in report_types:
            ttk.Radiobutton(options_frame, text=text, variable=self.report_type_var, 
                           value=value).pack(anchor='w', pady=2)
        
        # Output format
        format_frame = ttk.Frame(options_frame)
        format_frame.pack(fill='x', pady=(20, 0))
        
        ttk.Label(format_frame, text="Output Format:", font=('Arial', 12, 'bold')).pack(side='left')
        self.output_format_var = tk.StringVar(value="excel")
        
        ttk.Radiobutton(format_frame, text="Excel (.xlsx)", variable=self.output_format_var, 
                       value="excel").pack(side='left', padx=(20, 10))
        ttk.Radiobutton(format_frame, text="CSV (.csv)", variable=self.output_format_var, 
                       value="csv").pack(side='left', padx=(0, 10))
        ttk.Radiobutton(format_frame, text="PDF (.pdf)", variable=self.output_format_var, 
                       value="pdf").pack(side='left')
        
        # Action buttons
        button_frame = ttk.Frame(options_frame)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text="📊 View Report",
                  command=self.view_custom_report).pack(side='left', padx=5)
        ttk.Button(button_frame, text="💾 Save Report",
                  command=self.create_custom_report).pack(side='left', padx=5)
        ttk.Button(button_frame, text="📧 Email to Admin",
                  command=self.email_custom_report).pack(side='left', padx=5)
    

    def create_custom_report(self):
        """Create and save custom report"""
        report_type = self.report_type_var.get()
        output_format = self.output_format_var.get()
        
        try:
            # Get save location
            file_extensions = {
                "excel": ".xlsx",
                "csv": ".csv", 
                "pdf": ".pdf"
            }
            
            file_types = {
                "excel": [("Excel files", "*.xlsx")],
                "csv": [("CSV files", "*.csv")],
                "pdf": [("PDF files", "*.pdf")]
            }
            
            save_path = filedialog.asksaveasfilename(
                defaultextension=file_extensions[output_format],
                filetypes=file_types[output_format] + [("All files", "*.*")]
            )
            
            if not save_path:
                return
            
            # Generate report data based on type
            if report_type == "student_performance":
                self.create_student_performance_report(save_path, output_format)
            elif report_type == "assignment_stats":
                self.create_assignment_stats_report(save_path, output_format)
            elif report_type == "module_summary":
                self.create_module_summary_report(save_path, output_format)
            elif report_type == "submission_timeline":
                self.create_submission_timeline_report(save_path, output_format)
            elif report_type == "grade_analysis":
                self.create_grade_analysis_report(save_path, output_format)
            
            messagebox.showinfo("Success", f"Report saved to: {save_path}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate report: {e}")


    def view_custom_report(self):
        """View custom report on screen before saving"""
        report_type = self.report_type_var.get()

        try:
            # Generate report data
            report_data, report_title = self._get_report_data(report_type)

            if not report_data:
                messagebox.showinfo("No Data", "No data available for this report")
                return

            # Create view window
            view_window = tk.Toplevel(self.root)
            view_window.title(f"{report_title} - Preview")
            view_window.geometry("1000x700")

            # Title
            ttk.Label(view_window, text=report_title, font=('Arial', 16, 'bold')).pack(pady=10)

            # Create treeview for data
            tree_frame = ttk.Frame(view_window)
            tree_frame.pack(fill='both', expand=True, padx=10, pady=10)

            # Scrollbars
            yscrollbar = ttk.Scrollbar(tree_frame)
            yscrollbar.pack(side='right', fill='y')
            xscrollbar = ttk.Scrollbar(tree_frame, orient='horizontal')
            xscrollbar.pack(side='bottom', fill='x')

            # Treeview
            columns = report_data['columns']
            tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                               yscrollcommand=yscrollbar.set, xscrollcommand=xscrollbar.set)

            yscrollbar.config(command=tree.yview)
            xscrollbar.config(command=tree.xview)

            # Configure columns
            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=120)

            # Insert data
            for row in report_data['rows']:
                tree.insert('', 'end', values=row)

            tree.pack(fill='both', expand=True)

            # Buttons
            button_frame = ttk.Frame(view_window)
            button_frame.pack(fill='x', padx=10, pady=10)

            ttk.Button(button_frame, text="Close", command=view_window.destroy).pack(side='right')

        except Exception as e:
            messagebox.showerror("Error", f"Failed to view report: {e}")


    def email_custom_report(self):
        """Email custom report to admin"""
        report_type = self.report_type_var.get()

        try:
            # Generate report data
            report_data, report_title = self._get_report_data(report_type)

            if not report_data:
                messagebox.showinfo("No Data", "No data available for this report")
                return

            # Get admin email
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute("SELECT email FROM users WHERE role = 'admin' LIMIT 1")
            admin_result = cursor.fetchone()
            conn.close()

            if not admin_result:
                messagebox.showerror("Error", "No admin email found in system")
                return

            admin_email = admin_result[0]

            # Format report as text
            email_body = f"=== {report_title} ===\n"
            email_body += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

            # Add column headers
            email_body += " | ".join(report_data['columns']) + "\n"
            email_body += "-" * (len(" | ".join(report_data['columns']))) + "\n"

            # Add data rows (limit to first 100 for email)
            for i, row in enumerate(report_data['rows'][:100]):
                email_body += " | ".join(str(val) for val in row) + "\n"

            if len(report_data['rows']) > 100:
                email_body += f"\n... and {len(report_data['rows']) - 100} more rows\n"

            email_body += f"\n\nTotal Records: {len(report_data['rows'])}\n"

            # Send email
            from university_system.infrastructure.email.email_service import send_email
            send_email(
                to_email=admin_email,
                subject=f"[Assignment System] {report_title}",
                body=email_body
            )

            messagebox.showinfo("Success", f"Report emailed to admin ({admin_email})")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to email report: {e}")


    def _get_report_data(self, report_type):
        """Get report data for viewing or emailing"""
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()

        if report_type == "student_performance":
            cursor.execute('''
            SELECT s.student_id, s.first_name, s.last_name,
                   COUNT(sub.id) as total_submissions,
                   ROUND(AVG(sub.grade), 2) as avg_grade,
                   COUNT(CASE WHEN sub.late_submission = 1 THEN 1 END) as late_submissions
            FROM students s
            LEFT JOIN assignment_submissions sub ON s.student_id = sub.student_id
            WHERE sub.grade IS NOT NULL
            GROUP BY s.student_id, s.first_name, s.last_name
            ORDER BY s.last_name, s.first_name
            ''')
            columns = ['Student ID', 'First Name', 'Last Name', 'Total Submissions', 'Avg Grade', 'Late Submissions']
            title = "Student Performance Report"

        elif report_type == "assignment_stats":
            cursor.execute('''
            SELECT a.title, a.module_code, a.max_marks,
                   COUNT(s.id) as total_submissions,
                   ROUND(AVG(s.grade), 2) as avg_grade,
                   MIN(s.grade) as min_grade,
                   MAX(s.grade) as max_grade
            FROM assignments a
            LEFT JOIN assignment_submissions s ON a.id = s.assignment_id
            WHERE a.is_active = 1
            GROUP BY a.id, a.title, a.module_code, a.max_marks
            ORDER BY a.title
            ''')
            columns = ['Assignment', 'Module', 'Max Marks', 'Submissions', 'Avg Grade', 'Min Grade', 'Max Grade']
            title = "Assignment Statistics Report"

        elif report_type == "module_summary":
            cursor.execute('''
            SELECT m.module_code, m.module_name,
                   COUNT(DISTINCT a.id) as total_assignments,
                   COUNT(DISTINCT s.student_id) as active_students,
                   ROUND(AVG(sub.grade), 2) as avg_grade
            FROM modules m
            LEFT JOIN assignments a ON m.module_code = a.module_code
            LEFT JOIN student_modules s ON m.module_code = s.module_code
            LEFT JOIN assignment_submissions sub ON a.id = sub.assignment_id
            GROUP BY m.module_code, m.module_name
            ORDER BY m.module_code
            ''')
            columns = ['Module Code', 'Module Name', 'Assignments', 'Students', 'Avg Grade']
            title = "Module Summary Report"

        elif report_type == "submission_timeline":
            cursor.execute('''
            SELECT DATE(submission_date) as date,
                   COUNT(*) as submissions,
                   COUNT(CASE WHEN late_submission = 1 THEN 1 END) as late,
                   COUNT(CASE WHEN grade IS NOT NULL THEN 1 END) as graded
            FROM assignment_submissions
            WHERE submission_date >= date('now', '-30 days')
            GROUP BY DATE(submission_date)
            ORDER BY date DESC
            ''')
            columns = ['Date', 'Total Submissions', 'Late', 'Graded']
            title = "Submission Timeline Report (Last 30 Days)"

        elif report_type == "grade_analysis":
            cursor.execute('''
            SELECT
                CASE
                    WHEN grade >= 90 THEN 'A (90-100%)'
                    WHEN grade >= 80 THEN 'B (80-89%)'
                    WHEN grade >= 70 THEN 'C (70-79%)'
                    WHEN grade >= 60 THEN 'D (60-69%)'
                    ELSE 'F (Below 60%)'
                END as grade_band,
                COUNT(*) as count,
                ROUND(AVG(grade), 2) as avg_grade
            FROM assignment_submissions
            WHERE grade IS NOT NULL
            GROUP BY grade_band
            ORDER BY grade_band
            ''')
            columns = ['Grade Band', 'Count', 'Avg Grade']
            title = "Grade Analysis Report"

        else:
            conn.close()
            return None, None

        rows = cursor.fetchall()
        conn.close()

        return {'columns': columns, 'rows': rows}, title


    def create_student_performance_report(self, save_path, output_format):
        """Create student performance report with directory creation"""
        try:
            # Ensure directory exists
            save_dir = os.path.dirname(save_path)
            if save_dir:
                os.makedirs(save_dir, exist_ok=True)
    
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            # Get student performance data
            cursor.execute('''
            SELECT s.student_id, s.first_name, s.last_name,
                   COUNT(sub.id) as total_submissions,
                   AVG(sub.grade) as avg_grade,
                   COUNT(CASE WHEN sub.late_submission = 1 THEN 1 END) as late_submissions
            FROM students s
            LEFT JOIN assignment_submissions sub ON s.student_id = sub.student_id
            WHERE sub.grade IS NOT NULL
            GROUP BY s.student_id, s.first_name, s.last_name
            ORDER BY s.last_name, s.first_name
            ''')
    
            data = cursor.fetchall()
            conn.close()
    
            if output_format == "csv":
                import csv
                with open(save_path, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['Student ID', 'First Name', 'Last Name', 'Total Submissions', 'Average Grade', 'Late Submissions'])
                    writer.writerows(data)
    
            elif output_format == "excel":
                import pandas as pd
                df = pd.DataFrame(data, columns=['Student ID', 'First Name', 'Last Name', 'Total Submissions', 'Average Grade', 'Late Submissions'])
                df.to_excel(save_path, index=False)
    
            elif output_format == "pdf":
                self._create_pdf_report(save_path, "Student Performance Report",
                                      ['Student ID', 'First Name', 'Last Name', 'Total Submissions', 'Average Grade', 'Late Submissions'],
                                      data)
    
        except Exception as e:
            raise Exception(f"Error creating student performance report: {e}")
    

    def create_assignment_stats_report(self, save_path, output_format):
        """Create assignment statistics report with directory creation"""
        try:
            # Ensure directory exists
            save_dir = os.path.dirname(save_path)
            if save_dir:
                os.makedirs(save_dir, exist_ok=True)
    
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            cursor.execute('''
            SELECT a.title, a.module_code, a.due_date,
                   COUNT(sub.id) as total_submissions,
                   AVG(sub.grade) as avg_grade,
                   COUNT(CASE WHEN sub.late_submission = 1 THEN 1 END) as late_submissions
            FROM assignments a
            LEFT JOIN assignment_submissions sub ON a.id = sub.assignment_id
            WHERE a.is_active = 1
            GROUP BY a.id, a.title, a.module_code, a.due_date
            ORDER BY a.due_date DESC
            ''')
    
            data = cursor.fetchall()
            conn.close()
    
            if output_format == "csv":
                import csv
                with open(save_path, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['Assignment', 'Module', 'Due Date', 'Submissions', 'Avg Grade', 'Late Submissions'])
                    writer.writerows(data)
    
            elif output_format == "excel":
                import pandas as pd
                df = pd.DataFrame(data, columns=['Assignment', 'Module', 'Due Date', 'Submissions', 'Avg Grade', 'Late Submissions'])
                df.to_excel(save_path, index=False)
    
            elif output_format == "pdf":
                self._create_pdf_report(save_path, "Assignment Statistics Report",
                                      ['Assignment', 'Module', 'Due Date', 'Submissions', 'Avg Grade', 'Late Submissions'],
                                      data)
    
        except Exception as e:
            raise Exception(f"Error creating assignment stats report: {e}")
    

    def create_module_summary_report(self, save_path, output_format):
        """Create module summary report with directory creation"""
        try:
            # Ensure directory exists
            save_dir = os.path.dirname(save_path)
            if save_dir:
                os.makedirs(save_dir, exist_ok=True)
    
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            cursor.execute('''
            SELECT m.module_code, m.module_name,
                   COUNT(DISTINCT a.id) as total_assignments,
                   COUNT(DISTINCT sub.student_id) as active_students,
                   AVG(sub.grade) as avg_grade
            FROM modules m
            LEFT JOIN assignments a ON m.module_code = a.module_code
            LEFT JOIN assignment_submissions sub ON a.id = sub.assignment_id
            GROUP BY m.module_code, m.module_name
            ORDER BY m.module_code
            ''')
    
            data = cursor.fetchall()
            conn.close()
    
            if output_format == "csv":
                import csv
                with open(save_path, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['Module Code', 'Module Name', 'Total Assignments', 'Active Students', 'Average Grade'])
                    writer.writerows(data)
    
            elif output_format == "excel":
                import pandas as pd
                df = pd.DataFrame(data, columns=['Module Code', 'Module Name', 'Total Assignments', 'Active Students', 'Average Grade'])
                df.to_excel(save_path, index=False)
    
            elif output_format == "pdf":
                self._create_pdf_report(save_path, "Module Summary Report",
                                      ['Module Code', 'Module Name', 'Total Assignments', 'Active Students', 'Average Grade'],
                                      data)
    
        except Exception as e:
            raise Exception(f"Error creating module summary report: {e}")
    

    def create_submission_timeline_report(self, save_path, output_format):
        """Create submission timeline report with directory creation"""
        try:
            # Ensure directory exists
            save_dir = os.path.dirname(save_path)
            if save_dir:
                os.makedirs(save_dir, exist_ok=True)
    
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            cursor.execute('''
            SELECT DATE(sub.submission_date) as submission_date,
                   COUNT(*) as submissions_count,
                   COUNT(CASE WHEN sub.late_submission = 1 THEN 1 END) as late_count
            FROM assignment_submissions sub
            WHERE sub.submission_date >= date('now', '-30 days')
            GROUP BY DATE(sub.submission_date)
            ORDER BY submission_date DESC
            ''')
    
            data = cursor.fetchall()
            conn.close()
    
            if output_format == "csv":
                import csv
                with open(save_path, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['Date', 'Total Submissions', 'Late Submissions'])
                    writer.writerows(data)
    
            elif output_format == "excel":
                import pandas as pd
                df = pd.DataFrame(data, columns=['Date', 'Total Submissions', 'Late Submissions'])
                df.to_excel(save_path, index=False)
    
            elif output_format == "pdf":
                self._create_pdf_report(save_path, "Submission Timeline Report",
                                      ['Date', 'Total Submissions', 'Late Submissions'],
                                      data)
    
        except Exception as e:
            raise Exception(f"Error creating submission timeline report: {e}")
    

    def create_grade_analysis_report(self, save_path, output_format):
        """Create grade analysis report with directory creation"""
        try:
            # Ensure directory exists
            save_dir = os.path.dirname(save_path)
            if save_dir:
                os.makedirs(save_dir, exist_ok=True)
    
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            cursor.execute('''
            SELECT
                CASE
                    WHEN grade >= 90 THEN 'A (90-100%)'
                    WHEN grade >= 80 THEN 'B (80-89%)'
                    WHEN grade >= 70 THEN 'C (70-79%)'
                    WHEN grade >= 60 THEN 'D (60-69%)'
                    ELSE 'F (Below 60%)'
                END as grade_band,
                COUNT(*) as student_count,
                ROUND(AVG(grade), 2) as avg_grade
            FROM assignment_submissions
            WHERE grade IS NOT NULL
            GROUP BY grade_band
            ORDER BY avg_grade DESC
            ''')
    
            data = cursor.fetchall()
            conn.close()
    
            if output_format == "csv":
                import csv
                with open(save_path, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['Grade Band', 'Student Count', 'Average Grade'])
                    writer.writerows(data)
    
            elif output_format == "excel":
                import pandas as pd
                df = pd.DataFrame(data, columns=['Grade Band', 'Student Count', 'Average Grade'])
                df.to_excel(save_path, index=False)
    
            elif output_format == "pdf":
                self._create_pdf_report(save_path, "Grade Analysis Report",
                                      ['Grade Band', 'Student Count', 'Average Grade'],
                                      data)
    
        except Exception as e:
            raise Exception(f"Error creating grade analysis report: {e}")
    

    def _create_pdf_report(self, save_path, title, headers, data):
        """Helper function to create PDF reports with proper error handling"""
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import letter, A4
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from datetime import datetime
    
            # Ensure directory exists
            save_dir = os.path.dirname(save_path)
            if save_dir:
                os.makedirs(save_dir, exist_ok=True)
    
            # Create PDF document
            doc = SimpleDocTemplate(save_path, pagesize=letter)
            elements = []
    
            # Add title
            styles = getSampleStyleSheet()
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                textColor=colors.HexColor('#2c3e50'),
                spaceAfter=30,
                alignment=1  # Center alignment
            )
            elements.append(Paragraph(title, title_style))
            elements.append(Spacer(1, 0.2 * inch))
    
            # Add generation date
            date_style = ParagraphStyle(
                'DateStyle',
                parent=styles['Normal'],
                fontSize=10,
                textColor=colors.grey,
                alignment=1
            )
            date_text = f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            elements.append(Paragraph(date_text, date_style))
            elements.append(Spacer(1, 0.3 * inch))
    
            # Create table data
            table_data = [headers]
            for row in data:
                # Convert values to strings and handle None values
                formatted_row = [str(val) if val is not None else 'N/A' for val in row]
                table_data.append(formatted_row)
    
            # Create table
            table = Table(table_data)
    
            # Style the table
            table.setStyle(TableStyle([
                # Header styling
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
    
                # Data rows styling
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#ecf0f1')]),
            ]))
    
            elements.append(table)
    
            # Build PDF
            doc.build(elements)
    
        except ImportError as e:
            # reportlab not installed, create a simple text-based PDF alternative
            with open(save_path, 'w') as f:
                f.write(f"{title}\n")
                f.write("=" * len(title) + "\n\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write(" | ".join(headers) + "\n")
                f.write("-" * (len(" | ".join(headers))) + "\n")
                for row in data:
                    f.write(" | ".join([str(val) if val is not None else 'N/A' for val in row]) + "\n")
            print(f"Note: reportlab not installed. Created text file instead of PDF at {save_path}")
    
        except Exception as e:
            raise Exception(f"Error creating PDF report: {e}")
    
    # GRADING WITH RUBRICS METHOD

    def show_advanced_analytics(self):
        """Show advanced analytics with more detailed reporting"""
        self.gui.layout.clear_content_area()
        
        title = ttk.Label(self.gui.layout.content_area, text="Advanced Analytics", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))
        
        # Create notebook for different analytics
        notebook = ttk.Notebook(self.gui.layout.content_area)
        notebook.pack(fill='both', expand=True)
        
        # Performance Analytics tab
        performance_frame = ttk.Frame(notebook)
        notebook.add(performance_frame, text="Performance Analytics")
        
        # Submission Analytics tab  
        submission_frame = ttk.Frame(notebook)
        notebook.add(submission_frame, text="Submission Analytics")
        
        # Comparative Analytics tab
        comparative_frame = ttk.Frame(notebook)
        notebook.add(comparative_frame, text="Comparative Analysis")
        
        # Add controls for analytics
        controls_frame = ttk.Frame(performance_frame)
        controls_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(controls_frame, text="Date Range:").pack(side='left')
        ttk.Button(controls_frame, text="Last 30 Days", 
                  command=lambda: self.load_analytics_data("30days")).pack(side='left', padx=5)
        ttk.Button(controls_frame, text="Last Semester", 
                  command=lambda: self.load_analytics_data("semester")).pack(side='left', padx=5)
        ttk.Button(controls_frame, text="Export Report", 
                  command=self.export_detailed_report).pack(side='right')
    

    def load_analytics_data(self, period):
        """Load analytics data for specified period"""
        messagebox.showinfo("Analytics", f"Loading analytics for {period}...")
    

    def export_detailed_report(self):
        """Export detailed analytics report"""
        save_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if save_path:
            messagebox.showinfo("Export", f"Report would be exported to: {save_path}")
    

    def generate_analytics_dashboard(self, *args, **kwargs):
        """Show the analytics dashboard."""
        self._launch_gui_feature(self.show_analytics, "analytics dashboard")


    def _export_analytics_report(self, report_type, data, filename_prefix="analytics"):
        """Export analytics report to file (CSV or Excel)"""
        try:
            # Ask user for save location and format
            save_path = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                initialfile=f"{filename_prefix}_{datetime.now().strftime('%Y%m%d')}",
                filetypes=[
                    ("Excel files", "*.xlsx"),
                    ("CSV files", "*.csv"),
                    ("PDF files", "*.pdf"),
                    ("All files", "*.*")
                ]
            )

            if not save_path:
                return

            # Determine format from extension
            file_ext = os.path.splitext(save_path)[1].lower()

            if file_ext == '.csv':
                # Export as CSV
                import csv
                with open(save_path, 'w', newline='') as f:
                    if isinstance(data, list) and len(data) > 0:
                        if isinstance(data[0], dict):
                            writer = csv.DictWriter(f, fieldnames=data[0].keys())
                            writer.writeheader()
                            writer.writerows(data)
                        else:
                            writer = csv.writer(f)
                            writer.writerows(data)

            elif file_ext == '.xlsx':
                # Export as Excel
                df = pd.DataFrame(data)
                df.to_excel(save_path, index=False, sheet_name=report_type)

            elif file_ext == '.pdf':
                # Export as PDF
                if isinstance(data, list) and len(data) > 0:
                    headers = list(data[0].keys()) if isinstance(data[0], dict) else None
                    self._create_pdf_report(save_path, f"{report_type} Report", headers, data)

            messagebox.showinfo("Success", f"Analytics report exported successfully to:\n{save_path}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export analytics report: {e}")


    def _launch_gui_feature(self, callback, feature_name):
        """Helper to launch GUI features with error handling"""
        try:
            callback()
        except Exception as e:
            messagebox.showerror("Error", f"Error launching {feature_name}: {str(e)}")


