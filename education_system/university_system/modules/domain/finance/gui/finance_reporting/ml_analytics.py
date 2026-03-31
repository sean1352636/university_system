import tkinter as tk
from tkinter.scrolledtext import ScrolledText
from tkinter import ttk, messagebox, filedialog, scrolledtext
from tkinter.font import Font
import threading
from datetime import datetime, timedelta
import json
import webbrowser
from pathlib import Path
import matplotlib
from education_system.university_system.modules.shared.constants import paths
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np

# Import auth instance management from user_authentication
try:
    from education_system.university_system.infrastructure.auth import get_current_user, set_auth_instance
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None

auth = None

def set_auth(auth_instance):
    global auth
    auth = auth_instance
    # Also set it in the global auth instance if available
    if HAS_AUTH:
        set_auth_instance(auth_instance)
# Import the shared authentication system
try:
    from education_system.university_system.infrastructure.auth import UserAuth
    from education_system.university_system.infrastructure.shared_context import get_auth
except ImportError as e:
    print(f"⚠️ Could not import UserAuth: {e}")
    UserAuth = None
    get_auth = lambda: None

from education_system.university_system.modules.shared.utils.i18n import get_text as _, init_i18n
init_i18n()

# Import analytics classes
from education_system.university_system.modules.domain.finance.gui.finance_reporting.analytics_classes import (
    CashFlowForecaster,
    AnomalyDetector,
    PaymentPredictionML,
)


# This module defines mixin functions for FinancialManagementGUI
# Note: Methods are registered by main.py to avoid circular imports

def run_risk_analysis(self):
    """Run payment risk analysis"""
    self.update_status("Running risk analysis...")

    def risk_in_background():
        try:

            # Payment risk prediction
            payment_predictor = PaymentPredictionML()
            risk_students = payment_predictor.predict_payment_risk()

            # Anomaly detection
            anomaly_detector = AnomalyDetector()
            anomalies = anomaly_detector.detect_payment_anomalies()

            self.root.after(0, lambda: [
                self.log_activity(f"Risk analysis completed - {len(risk_students)} students analyzed, {len(anomalies)} anomalies found"),
                self.update_status("Ready"),
                self.show_comprehensive_risk_results(risk_students, anomalies)
            ])
        except Exception as e:
            self.root.after(0, lambda _e=e: [
                self.log_activity(f"Risk analysis error: {_e}"),
                self.update_status("Error"),
                messagebox.showerror("Error", f"Risk analysis failed: {_e}")
            ])

    thread = threading.Thread(target=risk_in_background)
    thread.daemon = True
    thread.start()

def show_comprehensive_risk_results(self, risk_students, anomalies):
    """Show comprehensive risk analysis results"""
    risk_window = tk.Toplevel(self.root)
    risk_window.title(_("finance_reporting.windows.risk_analysis"))
    risk_window.geometry("1200x800")

    main_frame = ttk.Frame(risk_window, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Comprehensive Risk Analysis Results", 
             style='Title.TLabel').pack(pady=(0, 20))

    # Create notebook for different risk analyses
    notebook = ttk.Notebook(main_frame)
    notebook.pack(fill=tk.BOTH, expand=True)

    # Payment Risk Tab
    risk_frame = ttk.Frame(notebook, padding="10")
    notebook.add(risk_frame, text="Payment Risk Prediction")

    # Risk summary
    risk_summary_frame = ttk.LabelFrame(risk_frame, text="Risk Summary", padding="10")
    risk_summary_frame.pack(fill=tk.X, pady=(0, 10))

    high_risk = len([s for s in risk_students if s['risk_level'] == 'High'])
    medium_risk = len([s for s in risk_students if s['risk_level'] == 'Medium'])
    low_risk = len([s for s in risk_students if s['risk_level'] == 'Low'])

    summary_text = f"Total Students: {len(risk_students)} | High Risk: {high_risk} | Medium Risk: {medium_risk} | Low Risk: {low_risk}"
    ttk.Label(risk_summary_frame, text=summary_text).pack()

    # Risk details
    risk_tree = ttk.Treeview(risk_frame, columns=('Risk Level', 'Risk Score', 'Total Fees', 'Payments'), height=15)
    risk_tree.heading('#0', text='Student Name')
    risk_tree.heading('Risk Level', text='Risk Level')
    risk_tree.heading('Risk Score', text='Risk Score')
    risk_tree.heading('Total Fees', text='Total Fees')
    risk_tree.heading('Payments', text='Payments Made')
    risk_tree.pack(fill=tk.BOTH, expand=True)

    for student in risk_students:
        risk_tree.insert('', 'end', text=student['student_name'],
                        values=(student['risk_level'], 
                              f"{student['risk_score']:.1%}",
                              f"£{student['total_fees']:,.2f}",
                              student['payments_made']))

    # Anomaly Detection Tab
    anomaly_frame = ttk.Frame(notebook, padding="10")
    notebook.add(anomaly_frame, text="Payment Anomalies")

    # Anomaly summary
    anomaly_summary_frame = ttk.LabelFrame(anomaly_frame, text="Anomaly Summary", padding="10")
    anomaly_summary_frame.pack(fill=tk.X, pady=(0, 10))

    ttk.Label(anomaly_summary_frame, text=f"Anomalies Detected: {len(anomalies)}").pack(anchor=tk.W)

    if len(anomalies) > 0:
        ttk.Label(anomaly_summary_frame, text="⚠ Unusual payment patterns detected - review recommended", 
                 foreground="orange").pack(anchor=tk.W)
    else:
        ttk.Label(anomaly_summary_frame, text="✓ No unusual payment patterns detected", 
                 foreground="green").pack(anchor=tk.W)

    # Anomaly details
    if anomalies:
        anomaly_tree = ttk.Treeview(anomaly_frame, columns=('Amount', 'Reason'), height=15)
        anomaly_tree.heading('#0', text='Student ID')
        anomaly_tree.heading('Amount', text='Amount')
        anomaly_tree.heading('Reason', text='Anomaly Reason')
        anomaly_tree.column('#0', width=150)
        anomaly_tree.column('Amount', width=150)
        anomaly_tree.column('Reason', width=300)
        anomaly_tree.pack(fill=tk.BOTH, expand=True)

        for anomaly in anomalies:
            # Handle both tuple format (student_id, amount) and dict format
            if isinstance(anomaly, dict):
                student_id = anomaly.get('student_name', anomaly.get('student_id', 'Unknown'))
                amount = anomaly.get('amount', 0)
                reason = anomaly.get('anomaly_reason', 'Unusual payment pattern')
            else:
                # Tuple format: (student_id, amount)
                student_id = anomaly[0] if len(anomaly) > 0 else 'Unknown'
                amount = anomaly[1] if len(anomaly) > 1 else 0
                reason = 'Payment exceeds threshold'

            anomaly_tree.insert('', 'end', text=str(student_id),
                              values=(f"£{amount:,.2f}", reason))

    ttk.Button(main_frame, text="Close", command=risk_window.destroy).pack(pady=10)

    # Export button
    def export_results():
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Save Risk Analysis Results"
        )
        if filename:
            try:
                import csv
                with open(filename, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Student Name', 'Risk Level', 'Risk Score', 'Total Fees', 'Payments Made'])
                    for student in risk_students:
                        writer.writerow([
                            student['student_name'],
                            student['risk_level'],
                            student['risk_score'],
                            student['total_fees'],
                            student['payments_made']
                        ])
                messagebox.showinfo("Export Complete", f"Results exported to {filename}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export: {e}")

    ttk.Button(main_frame, text="📊 Export Results", command=export_results).pack(pady=5)

def run_ml_model_training(self):
    """Run ML model training with GUI display"""
    self.update_status("Training machine learning models...")

    def train_in_background():
        try:
            payment_predictor = PaymentPredictionML()

            # Train the model
            success = payment_predictor.train_model()

            self.root.after(0, lambda: [
                self.log_activity(f"ML model training {'completed' if success else 'failed'}"),
                self.update_status("Ready"),
                self.show_ml_training_results(success)
            ])

        except Exception as e:
            self.root.after(0, lambda _e=e: [
                self.log_activity(f"ML training error: {_e}"),
                self.update_status("Error"),
                messagebox.showerror("Error", f"ML model training failed: {_e}")
            ])

    thread = threading.Thread(target=train_in_background)
    thread.daemon = True
    thread.start()

def show_ml_training_results(self, success):
    """Show ML training results in new window"""
    training_window = tk.Toplevel(self.root)
    training_window.title(_("finance_reporting.windows.ml_training"))
    training_window.geometry("500x400")

    main_frame = ttk.Frame(training_window, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="ML Model Training Results", 
             style='Title.TLabel').pack(pady=(0, 20))

    if success:
        ttk.Label(main_frame, text="✓ Payment prediction model trained successfully", 
                 foreground="green").pack(pady=5)
        ttk.Label(main_frame, text="✓ Model saved to payment_prediction_model.pkl").pack(pady=5)
        ttk.Label(main_frame, text="✓ Risk prediction system is now operational").pack(pady=5)
    else:
        ttk.Label(main_frame, text="✗ Model training failed", 
                 foreground="red").pack(pady=5)
        ttk.Label(main_frame, text="Possible causes:").pack(pady=5)
        ttk.Label(main_frame, text="• Insufficient training data").pack(pady=2)
        ttk.Label(main_frame, text="• Missing required libraries").pack(pady=2)
        ttk.Label(main_frame, text="• Data quality issues").pack(pady=2)

    ttk.Button(main_frame, text="Close", command=training_window.destroy).pack(pady=20)

def run_anomaly_detection(self):
    """Run anomaly detection with GUI display"""
    self.update_status("Running anomaly detection...")

    def detect_in_background():
        try:
            anomaly_detector = AnomalyDetector()
            anomalies = anomaly_detector.detect_payment_anomalies()

            self.root.after(0, lambda: [
                self.log_activity(f"Anomaly detection completed - {len(anomalies)} anomalies found"),
                self.update_status("Ready"),
                self.show_anomaly_results(anomalies)
            ])

        except Exception as e:
            self.root.after(0, lambda _e=e: [
                self.log_activity(f"Anomaly detection error: {_e}"),
                self.update_status("Error"),
                messagebox.showerror("Error", f"Anomaly detection failed: {_e}")
            ])

    thread = threading.Thread(target=detect_in_background)
    thread.daemon = True
    thread.start()

def show_anomaly_results(self, anomalies):
    """Show anomaly detection results in new window"""
    anomaly_window = tk.Toplevel(self.root)
    anomaly_window.title(_("finance_reporting.windows.anomaly_detection"))
    anomaly_window.geometry("1000x600")

    main_frame = ttk.Frame(anomaly_window, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Payment Anomaly Detection Results", 
             style='Title.TLabel').pack(pady=(0, 20))

    # Summary
    summary_frame = ttk.LabelFrame(main_frame, text="Detection Summary", padding="10")
    summary_frame.pack(fill=tk.X, pady=(0, 10))

    ttk.Label(summary_frame, text=f"Total Anomalies Detected: {len(anomalies)}").pack(anchor=tk.W)

    if len(anomalies) == 0:
        ttk.Label(summary_frame, text="✓ No unusual payment patterns detected", 
                 foreground="green").pack(anchor=tk.W)
    else:
        ttk.Label(summary_frame, text="⚠ Anomalous payments require review", 
                 foreground="orange").pack(anchor=tk.W)

    # Results table
    if anomalies:
        results_frame = ttk.LabelFrame(main_frame, text="Detected Anomalies", padding="10")
        results_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        results_tree = ttk.Treeview(results_frame, columns=('Amount', 'Date', 'Method', 'Reason'), height=15)
        results_tree.heading('#0', text='Student Name')
        results_tree.heading('Amount', text='Amount')
        results_tree.heading('Date', text='Payment Date')
        results_tree.heading('Method', text='Payment Method')
        results_tree.heading('Reason', text='Anomaly Reason')
        results_tree.pack(fill=tk.BOTH, expand=True)

        for anomaly in anomalies:
            results_tree.insert('', 'end', text=anomaly['student_name'],
                              values=(f"£{anomaly['amount']:,.2f}",
                                    anomaly['payment_date'],
                                    anomaly['payment_method'],
                                    anomaly['anomaly_reason']))

    ttk.Button(main_frame, text="Close", command=anomaly_window.destroy).pack(pady=10)

def run_cash_flow_forecasting(self):
    """Run cash flow forecasting with GUI display"""
    self.update_status("Generating cash flow forecast...")

    def forecast_in_background():
        try:
            cash_flow_forecaster = CashFlowForecaster()
            forecast = cash_flow_forecaster.generate_cash_flow_forecast(12)

            self.root.after(0, lambda: [
                self.log_activity("Cash flow forecast completed"),
                self.update_status("Ready"),
                self.show_cash_flow_results(forecast)
            ])

        except Exception as e:
            self.root.after(0, lambda _e=e: [
                self.log_activity(f"Cash flow forecast error: {_e}"),
                self.update_status("Error"),
                messagebox.showerror("Error", f"Cash flow forecasting failed: {_e}")
            ])

    thread = threading.Thread(target=forecast_in_background)
    thread.daemon = True
    thread.start()

def show_cash_flow_results(self, forecast):
    """Show cash flow forecast results in new window"""
    forecast_window = tk.Toplevel(self.root)
    forecast_window.title(_("finance_reporting.windows.cash_flow_forecast"))
    forecast_window.geometry("1000x700")

    main_frame = ttk.Frame(forecast_window, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Cash Flow Forecast Results", 
             style='Title.TLabel').pack(pady=(0, 20))

    if forecast:
        # Summary statistics
        summary_frame = ttk.LabelFrame(main_frame, text="Forecast Summary", padding="10")
        summary_frame.pack(fill=tk.X, pady=(0, 10))

        total_forecast = sum(item['forecast_amount'] for item in forecast['forecast_data'])
        ttk.Label(summary_frame, text=f"Total 12-Month Forecast: £{total_forecast:,.2f}").pack(anchor=tk.W)
        ttk.Label(summary_frame, text=f"Monthly Baseline: £{forecast['baseline_monthly']:,.2f}").pack(anchor=tk.W)
        ttk.Label(summary_frame, text=f"Trend: £{forecast['trend']:,.2f} per month").pack(anchor=tk.W)

        # Monthly forecast table
        forecast_frame = ttk.LabelFrame(main_frame, text="Monthly Forecast", padding="10")
        forecast_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        forecast_tree = ttk.Treeview(forecast_frame, columns=('Amount', 'Confidence', 'Cumulative'), height=12)
        forecast_tree.heading('#0', text='Month')
        forecast_tree.heading('Amount', text='Forecast Amount')
        forecast_tree.heading('Confidence', text='Confidence')
        forecast_tree.heading('Cumulative', text='Cumulative')
        forecast_tree.pack(fill=tk.BOTH, expand=True)

        for item in forecast['forecast_data']:
            forecast_tree.insert('', 'end', text=item['month'],
                                values=(f"£{item['forecast_amount']:,.2f}",
                                      f"{item['confidence']:.1%}",
                                      f"£{item['cumulative_cash']:,.2f}"))
    else:
        ttk.Label(main_frame, text="No forecast data available", 
                 foreground="red").pack(pady=20)

    ttk.Button(main_frame, text="Close", command=forecast_window.destroy).pack(pady=10)

def run_peer_benchmarking(self):
    """Run peer institution benchmarking analysis"""
    self.update_status("Running peer benchmarking analysis...")

    def benchmark_in_background():
        try:
            # Get our current performance
            from education_system.university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT 
                SUM(sf.amount) as total_expected,
                SUM(CASE WHEN sf.status = 'paid' THEN sf.amount ELSE 0 END) as total_collected,
                COUNT(DISTINCT sf.student_id) as student_count
            FROM student_fees sf
            ''')

            our_data = cursor.fetchone()
            our_rate = (our_data[1] / our_data[0] * 100) if our_data[0] > 0 else 0
            our_avg_fee = our_data[0] / our_data[2] if our_data[2] > 0 else 0

            conn.close()

            # Simulate peer data (in production, this would come from external sources)
            peer_institutions = {
                'University A': {'collection_rate': 92.5, 'avg_fee': 8500, 'students': 1200},
                'University B': {'collection_rate': 89.3, 'avg_fee': 9200, 'students': 950},
                'University C': {'collection_rate': 95.1, 'avg_fee': 7800, 'students': 1500},
                'University D': {'collection_rate': 87.8, 'avg_fee': 8900, 'students': 1100}
            }

            # Calculate percentile ranking
            all_rates = [data['collection_rate'] for data in peer_institutions.values()] + [our_rate]
            our_percentile = (sorted(all_rates).index(our_rate) + 1) / len(all_rates) * 100

            benchmark_data = {
                'our_performance': {
                    'collection_rate': our_rate,
                    'avg_fee': our_avg_fee,
                    'student_count': our_data[2],
                    'percentile': our_percentile
                },
                'peer_data': peer_institutions
            }

            self.root.after(0, lambda: [
                self.log_activity("Peer benchmarking analysis completed"),
                self.update_status("Ready"),
                self.show_benchmarking_results(benchmark_data)
            ])

        except Exception as e:
            self.root.after(0, lambda _e=e: [
                self.log_activity(f"Peer benchmarking error: {_e}"),
                self.update_status("Error"),
                messagebox.showerror("Error", f"Peer benchmarking failed: {_e}")
            ])

    thread = threading.Thread(target=benchmark_in_background)
    thread.daemon = True
    thread.start()

def show_benchmarking_results_UNUSED_DUPLICATE(self, benchmark_data):
    """UNUSED DUPLICATE - Show peer benchmarking results in new window"""
    # NOTE: This is a duplicate function that expects different data structure
    # The active implementation is at line ~5861
    benchmark_window = tk.Toplevel(self.root)
    benchmark_window.title(_("finance_reporting.windows.peer_institution_benchmarking"))
    benchmark_window.geometry("900x700")

    main_frame = ttk.Frame(benchmark_window, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Peer Institution Benchmarking",
             style='Title.TLabel').pack(pady=(0, 20))

    # Our performance summary
    our_frame = ttk.LabelFrame(main_frame, text="Our Institution Performance", padding="10")
    our_frame.pack(fill=tk.X, pady=(0, 10))

    # Use .get() to avoid KeyError
    our_perf = benchmark_data.get('our_performance', {})
    ttk.Label(our_frame, text=f"Collection Rate: {our_perf.get('collection_rate', 0):.1f}%").pack(anchor=tk.W)
    ttk.Label(our_frame, text=f"Average Fee: £{our_perf.get('avg_fee', 0):,.0f}").pack(anchor=tk.W)
    ttk.Label(our_frame, text=f"Student Count: {our_perf.get('student_count', 0):,}").pack(anchor=tk.W)
    ttk.Label(our_frame, text=f"Percentile Ranking: {our_perf.get('percentile', 50):.0f}th percentile").pack(anchor=tk.W)

    # Peer comparison
    peer_frame = ttk.LabelFrame(main_frame, text="Peer Comparison", padding="10")
    peer_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    peer_tree = ttk.Treeview(peer_frame, columns=('Collection Rate', 'Avg Fee', 'Students', 'Comparison'), height=10)
    peer_tree.heading('#0', text='Institution')
    peer_tree.heading('Collection Rate', text='Collection Rate')
    peer_tree.heading('Avg Fee', text='Average Fee')
    peer_tree.heading('Students', text='Students')
    peer_tree.heading('Comparison', text='vs Our Rate')
    peer_tree.pack(fill=tk.BOTH, expand=True)

    for institution, data in benchmark_data['peer_data'].items():
        comparison = "↑" if our_perf['collection_rate'] > data['collection_rate'] else "↓" if our_perf['collection_rate'] < data['collection_rate'] else "="
        peer_tree.insert('', 'end', text=institution,
                        values=(f"{data['collection_rate']:.1f}%",
                              f"£{data['avg_fee']:,}",
                              f"{data['students']:,}",
                              comparison))

    ttk.Button(main_frame, text="Close", command=benchmark_window.destroy).pack(pady=10)

# Method registration is handled by main.py
