"""Analytics dialogs extracted from DialogsMixin."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from ._shared import *  # noqa: F401,F403


class AnalyticsDialogsMixin:
    def show_data_visualization_studio(self):
        """Show advanced data visualization studio"""
        try:
            studio_window = tk.Toplevel(self.root)
            studio_window.title(_t('gui.shell.enhanced_reporting.mixins.dialog_components.analytics.windows.data_visualization_studio', default="Data Visualization Studio"))
            studio_window.geometry("900x700")
            studio_window.transient(self.root)

            # Create notebook for different visualization aspects
            studio_notebook = ttk.Notebook(studio_window)
            studio_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Chart Builder Tab
            chart_frame = ttk.Frame(studio_notebook)
            studio_notebook.add(chart_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.analytics.tabs.chart_builder', default="Chart Builder"))

            # Data selection
            data_frame = ttk.LabelFrame(chart_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.analytics.labels.data_selection', default="Data Selection"), padding="10")
            data_frame.pack(fill=tk.X, padx=10, pady=10)

            ttk.Label(data_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.analytics.labels.data_source', default="Data Source:")).pack(anchor=tk.W)
            data_source_var = tk.StringVar(value=_t('gui.shell.enhanced_reporting.mixins.dialog_components.analytics.values.students', default="students"))
            data_combo = ttk.Combobox(data_frame, textvariable=data_source_var,
                                     values=["students", "courses", "modules", "attendance"], state="readonly")
            data_combo.pack(fill=tk.X)

            # Chart type selection
            chart_frame_inner = ttk.LabelFrame(chart_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.analytics.labels.chart_type', default="Chart Type"), padding="10")
            chart_frame_inner.pack(fill=tk.X, padx=10, pady=10)

            chart_type_var = tk.StringVar(value=_t('gui.shell.enhanced_reporting.mixins.dialog_components.analytics.values.bar', default="bar"))
            chart_types = [("bar", "Bar Chart"), ("pie", "Pie Chart"), ("line", "Line Chart"),
                          ("scatter", "Scatter Plot"), ("heatmap", "Heatmap")]

            for chart_id, chart_name in chart_types:
                ttk.Radiobutton(chart_frame_inner, text=chart_name,
                               variable=chart_type_var, value=chart_id).pack(anchor=tk.W)

            # Styling options
            style_frame = ttk.LabelFrame(chart_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.analytics.labels.styling_options', default="Styling Options"), padding="10")
            style_frame.pack(fill=tk.X, padx=10, pady=10)

            color_scheme_var = tk.StringVar(value=_t('gui.shell.enhanced_reporting.mixins.dialog_components.analytics.values.default', default="default"))
            ttk.Label(style_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.analytics.labels.color_scheme', default="Color Scheme:")).pack(anchor=tk.W)
            ttk.Combobox(style_frame, textvariable=color_scheme_var,
                        values=["default", "viridis", "plasma", "cool", "warm"], state="readonly").pack(fill=tk.X)

            # Custom Dashboard Tab
            dashboard_frame = ttk.Frame(studio_notebook)
            studio_notebook.add(dashboard_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.analytics.tabs.dashboard', default="Dashboard"))

            dashboard_info = ttk.LabelFrame(dashboard_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.analytics.labels.dashboard_components', default="Dashboard Components"), padding="10")
            dashboard_info.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Component selection
            components = {}
            component_types = [
                ("overview_cards", "Overview Cards", True),
                ("trend_charts", "Trend Charts", True),
                ("distribution_charts", "Distribution Charts", False),
                ("comparison_tables", "Comparison Tables", False),
                ("filter_controls", "Interactive Filters", False)
            ]

            for comp_id, comp_name, default_val in component_types:
                var = tk.BooleanVar(value=default_val)
                components[comp_id] = var
                ttk.Checkbutton(dashboard_info, text=comp_name, variable=var).pack(anchor=tk.W)

            def generate_visualization():
                try:
                    chart_type = chart_type_var.get()
                    data_source = data_source_var.get()
                    color_scheme = color_scheme_var.get()

                    # Generate sample visualization based on selections
                    messagebox.showinfo(_t('gui.shell.enhanced_reporting.mixins.dialog_components.analytics.dialogs.visualization_generated', default="Visualization Generated"),
                                      f"Generated {chart_type} chart for {data_source} data with {color_scheme} colors!")

                except Exception as e:
                    messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.dialog_components.analytics.dialogs.generation_error', default="Generation Error"), f"Failed to generate visualization: {str(e)}")

            # Buttons
            button_frame = ttk.Frame(studio_window)
            button_frame.pack(fill=tk.X, padx=10, pady=10)

            ttk.Button(button_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.analytics.buttons.generate_visualization', default="Generate Visualization"), command=generate_visualization,
                      style='Success.TButton').pack(side=tk.RIGHT, padx=(5, 0))
            ttk.Button(button_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.analytics.buttons.close', default="Close"), command=studio_window.destroy).pack(side=tk.RIGHT)

        except Exception as e:
            messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.dialog_components.analytics.dialogs.visualization_studio_error', default="Visualization Studio Error"), f"Failed to open visualization studio: {str(e)}")

    def show_report_analytics_dashboard(self):
        """Show analytics about report generation and usage"""
        try:
            analytics_window = tk.Toplevel(self.root)
            analytics_window.title(_t('gui.shell.enhanced_reporting.mixins.dialog_components.analytics.windows.report_analytics_dashboard', default="Report Analytics Dashboard"))
            analytics_window.geometry("800x600")
            analytics_window.transient(self.root)

            # Metrics display
            metrics_frame = ttk.LabelFrame(analytics_window, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.analytics.labels.report_metrics', default="Report Metrics"), padding="10")
            metrics_frame.pack(fill=tk.X, padx=10, pady=10)

            # Calculate metrics
            templates = load_templates() if ENHANCED_AVAILABLE else []
            scheduled_reports = load_scheduled_reports() if ENHANCED_AVAILABLE else []

            # Report counts
            reports_dir = CONFIG.get('reports_dir', 'reports') if ENHANCED_AVAILABLE else 'reports'
            report_count = 0
            if os.path.exists(reports_dir):
                report_count = len([f for f in os.listdir(reports_dir)
                                  if f.endswith(('.pdf', '.xlsx', '.html'))])

            metrics_text = f"""Report System Analytics
{"=" * 30}

Templates: {len(templates)}
Scheduled Reports: {len(scheduled_reports)}
Generated Reports: {report_count}
Active Schedules: {sum(1 for r in scheduled_reports if r.get('schedule_config', {}).get('enabled', True))}

Most Used Sections:"""

            # Count section usage across templates
            section_counts = {}
            for template in templates:
                for section in template.get('sections', []):
                    section_counts[section] = section_counts.get(section, 0) + 1

            for section, count in sorted(section_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
                metrics_text += f"\n- {section.replace('_', ' ').title()}: {count} templates"

            metrics_display = ScrolledText(metrics_frame, height=15, wrap=tk.WORD)
            metrics_display.pack(fill=tk.BOTH, expand=True)
            metrics_display.insert(1.0, metrics_text)
            metrics_display.config(state=tk.DISABLED)

            # Usage trends (placeholder)
            trends_frame = ttk.LabelFrame(analytics_window, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.analytics.labels.usage_trends', default="Usage Trends"), padding="10")
            trends_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            ttk.Label(trends_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.analytics.labels.trend_analysis_would_be_displayed_here_with_actual_usage_data', default="Trend analysis would be displayed here with actual usage data")).pack()

            ttk.Button(analytics_window, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.analytics.buttons.close', default="Close"), command=analytics_window.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.dialog_components.analytics.dialogs.analytics_error', default="Analytics Error"), f"Failed to open analytics dashboard: {str(e)}")

    def show_api_endpoints_documentation(self):
        """Show comprehensive API documentation dialog"""
        try:
            api_doc_window = tk.Toplevel(self.root)
            api_doc_window.title(_t('gui.shell.enhanced_reporting.mixins.dialog_components.analytics.windows.api_documentation', default="API Documentation"))
            api_doc_window.geometry("900x700")
            api_doc_window.transient(self.root)

            # Create notebook for different API sections
            api_notebook = ttk.Notebook(api_doc_window)
            api_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Authentication Tab
            auth_frame = ttk.Frame(api_notebook)
            api_notebook.add(auth_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.analytics.tabs.authentication', default="Authentication"))

            auth_text = ScrolledText(auth_frame, wrap=tk.WORD)
            auth_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            auth_docs = """API Authentication
=================

POST /api/login
- Description: User authentication
- Body: {"username": "user", "password": "pass"}
- Response: {"token": "jwt_token", "expires": "timestamp"}

Authentication Headers:
- Authorization: Bearer <token>
- Content-Type: application/json
"""
            auth_text.insert(1.0, auth_docs)

            # Endpoints Tab
            endpoints_frame = ttk.Frame(api_notebook)
            api_notebook.add(endpoints_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.analytics.tabs.endpoints', default="Endpoints"))

            endpoints_text = ScrolledText(endpoints_frame, wrap=tk.WORD)
            endpoints_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            endpoints_docs = """API Endpoints Reference
======================

TEMPLATES:
GET  /api/templates - List all templates
POST /api/templates - Create new template
GET  /api/templates/{name} - Get specific template
PUT  /api/templates/{name} - Update template
DELETE /api/templates/{name} - Delete template

REPORTS:
POST /api/reports/generate - Generate report
  Body: {
    "template_name": "string",
    "start_date": "YYYY-MM-DD",
    "end_date": "YYYY-MM-DD",
    "format": "pdf|excel|interactive"
  }

DATA:
GET /api/data/{section} - Get section data
  Parameters: start_date, end_date, filters

ANALYTICS:
GET /api/analytics/quality - Data quality metrics
GET /api/analytics/predictions - Dropout risk predictions
GET /api/analytics/anomalies - Anomaly detection results
GET /api/analytics/correlations - Correlation analysis

SYSTEM:
GET /api/health - System health check
GET /api/config - System configuration
"""
            endpoints_text.insert(1.0, endpoints_docs)

            # Examples Tab
            examples_frame = ttk.Frame(api_notebook)
            api_notebook.add(examples_frame, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.analytics.tabs.examples', default="Examples"))

            examples_text = ScrolledText(examples_frame, wrap=tk.WORD)
            examples_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            examples_docs = """API Usage Examples
==================

Generate a PDF Report:
curl -X POST http://localhost:5000/api/reports/generate \\
  -H "Content-Type: application/json" \\
  -d '{
    "template_name": "student_overview",
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "format": "pdf"
  }'

Get Data Quality Metrics:
curl -X GET http://localhost:5000/api/analytics/quality \\
  -H "Authorization: Bearer <token>"

Create New Template:
curl -X POST http://localhost:5000/api/templates \\
  -H "Content-Type: application/json" \\
  -d '{
    "name": "Custom Report",
    "description": "My custom report",
    "sections": ["student_overview", "course_distribution"],
    "visualization_type": "standard"
  }'
"""
            examples_text.insert(1.0, examples_docs)

            ttk.Button(api_doc_window, text=_t('gui.shell.enhanced_reporting.mixins.dialog_components.analytics.buttons.close', default="Close"), command=api_doc_window.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_t('gui.shell.enhanced_reporting.mixins.dialog_components.analytics.dialogs.api_documentation_error', default="API Documentation Error"), f"Failed to open API documentation: {str(e)}")
