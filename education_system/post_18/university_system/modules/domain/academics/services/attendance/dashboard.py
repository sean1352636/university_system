"""Real-time attendance dashboard using Plotly Dash."""

import datetime
from datetime import timedelta
from education_system.post_18.university_system.infrastructure.database.db import get_connection
from education_system.post_18.university_system.modules.domain.academics.services.attendance.settings import get_setting
from education_system.post_18.university_system.modules.domain.academics.services.attendance.records import get_modules


class AttendanceDashboard:
    def __init__(self):
        import dash
        self.app = dash.Dash(__name__)
        self.setup_layout()
        self.setup_callbacks()

    def setup_layout(self):
        """Setup dashboard layout"""
        from dash import dcc, html
        self.app.layout = html.Div([
            html.H1("Attendance Tracking Dashboard", style={'textAlign': 'center'}),

            # Controls
            html.Div([
                html.Div([
                    html.Label("Select Module:"),
                    dcc.Dropdown(
                        id='module-dropdown',
                        options=[],
                        value=None
                    )
                ], className="six columns"),

                html.Div([
                    html.Label("Select Date Range:"),
                    dcc.DatePickerRange(
                        id='date-picker-range',
                        start_date=datetime.date.today() - timedelta(days=30),
                        end_date=datetime.date.today()
                    )
                ], className="six columns"),
            ], className="row"),

            # Key Metrics
            html.Div([
                html.Div([
                    html.H3("Overall Attendance Rate"),
                    html.H2(id="overall-rate", children="--")
                ], className="three columns", style={'textAlign': 'center'}),

                html.Div([
                    html.H3("Students at Risk"),
                    html.H2(id="at-risk-count", children="--")
                ], className="three columns", style={'textAlign': 'center'}),

                html.Div([
                    html.H3("Today's Sessions"),
                    html.H2(id="todays-sessions", children="--")
                ], className="three columns", style={'textAlign': 'center'}),

                html.Div([
                    html.H3("Active Alerts"),
                    html.H2(id="active-alerts", children="--")
                ], className="three columns", style={'textAlign': 'center'}),
            ], className="row"),

            # Charts
            html.Div([
                html.Div([
                    dcc.Graph(id="attendance-trend-chart")
                ], className="six columns"),

                html.Div([
                    dcc.Graph(id="status-distribution-chart")
                ], className="six columns"),
            ], className="row"),

            html.Div([
                html.Div([
                    dcc.Graph(id="student-performance-chart")
                ], className="twelve columns"),
            ], className="row"),

            # Auto-refresh
            dcc.Interval(
                id='interval-component',
                interval=int(get_setting('dashboard_refresh_seconds') or 30) * 1000,
                n_intervals=0
            )
        ])

    def setup_callbacks(self):
        """Setup dashboard callbacks"""
        from dash.dependencies import Input, Output

        @self.app.callback(
            [Output('module-dropdown', 'options'),
             Output('overall-rate', 'children'),
             Output('at-risk-count', 'children'),
             Output('todays-sessions', 'children'),
             Output('active-alerts', 'children'),
             Output('attendance-trend-chart', 'figure'),
             Output('status-distribution-chart', 'figure'),
             Output('student-performance-chart', 'figure')],
            [Input('interval-component', 'n_intervals'),
             Input('module-dropdown', 'value'),
             Input('date-picker-range', 'start_date'),
             Input('date-picker-range', 'end_date')]
        )
        def update_dashboard(n_intervals, selected_module, start_date, end_date):
            # Get modules
            modules = get_modules()
            module_options = [{'label': f"{code} - {name}", 'value': code} for code, name in modules]

            # Get dashboard data
            dashboard_data = self.get_dashboard_data(selected_module, start_date, end_date)

            return (
                module_options,
                f"{dashboard_data['overall_rate']:.1f}%",
                str(dashboard_data['at_risk_count']),
                str(dashboard_data['todays_sessions']),
                str(dashboard_data['active_alerts']),
                dashboard_data['trend_chart'],
                dashboard_data['status_chart'],
                dashboard_data['performance_chart']
            )

    def get_dashboard_data(self, module_code=None, start_date=None, end_date=None):
        """Get data for dashboard"""
        import pandas as pd
        try:
            import plotly.express as px
        except ModuleNotFoundError as exc:
            raise ModuleNotFoundError(
                "Interactive Plotly dashboards require the optional 'viz' extra: "
                "pip install education-system[viz]"
            ) from exc
        try:
            conn = get_connection()

            # Base query conditions
            conditions = []
            params = []

            if module_code:
                conditions.append("ar.module_code = ?")
                params.append(module_code)

            if start_date:
                conditions.append("ar.date >= ?")
                params.append(start_date)

            if end_date:
                conditions.append("ar.date <= ?")
                params.append(end_date)

            where_clause = " AND " + " AND ".join(conditions) if conditions else ""

            # Overall attendance rate
            query = f'''
            SELECT
                AVG(CASE WHEN ar.status IN ('Present', 'Late') THEN 1.0 ELSE 0.0 END) * 100 as rate
            FROM attendance_records ar
            WHERE 1=1 {where_clause}
            '''

            overall_rate = pd.read_sql_query(query, conn, params=params)['rate'].iloc[0] or 0

            # Students at risk
            risk_query = f'''
            SELECT COUNT(DISTINCT ar.student_id) as count
            FROM attendance_records ar
            WHERE 1=1 {where_clause}
            GROUP BY ar.student_id
            HAVING AVG(CASE WHEN ar.status IN ('Present', 'Late') THEN 1.0 ELSE 0.0 END) < 0.8
            '''

            at_risk_df = pd.read_sql_query(risk_query, conn, params=params)
            at_risk_count = len(at_risk_df) if not at_risk_df.empty else 0

            # Today's sessions
            today = datetime.date.today().isoformat()
            sessions_query = '''
            SELECT COUNT(*) as count FROM attendance_sessions
            WHERE date = ? AND status = 'active'
            '''

            todays_sessions = pd.read_sql_query(sessions_query, conn, params=[today])['count'].iloc[0] or 0

            # Active alerts
            alerts_query = '''
            SELECT COUNT(*) as count FROM attendance_alerts
            WHERE status = 'pending'
            '''

            active_alerts = pd.read_sql_query(alerts_query, conn)['count'].iloc[0] or 0

            # Trend chart data
            trend_query = f'''
            SELECT
                ar.date,
                AVG(CASE WHEN ar.status IN ('Present', 'Late') THEN 1.0 ELSE 0.0 END) * 100 as rate
            FROM attendance_records ar
            WHERE 1=1 {where_clause}
            GROUP BY ar.date
            ORDER BY ar.date
            '''

            trend_df = pd.read_sql_query(trend_query, conn, params=params)

            if not trend_df.empty:
                trend_chart = px.line(trend_df, x='date', y='rate',
                                    title='Attendance Trend Over Time',
                                    labels={'rate': 'Attendance Rate (%)', 'date': 'Date'})
            else:
                trend_chart = px.line(title='No data available')

            # Status distribution
            status_query = f'''
            SELECT ar.status, COUNT(*) as count
            FROM attendance_records ar
            WHERE 1=1 {where_clause}
            GROUP BY ar.status
            '''

            status_df = pd.read_sql_query(status_query, conn, params=params)

            if not status_df.empty:
                status_chart = px.pie(status_df, values='count', names='status',
                                    title='Attendance Status Distribution')
            else:
                status_chart = px.pie(title='No data available')

            # Student performance chart
            performance_query = f'''
            SELECT
                ar.student_id,
                s.first_name || ' ' || s.last_name as name,
                AVG(CASE WHEN ar.status IN ('Present', 'Late') THEN 1.0 ELSE 0.0 END) * 100 as rate
            FROM attendance_records ar
            JOIN students s ON ar.student_id = s.student_id
            WHERE 1=1 {where_clause}
            GROUP BY ar.student_id, s.first_name, s.last_name
            ORDER BY rate ASC
            LIMIT 20
            '''

            performance_df = pd.read_sql_query(performance_query, conn, params=params)

            if not performance_df.empty:
                performance_chart = px.bar(performance_df, x='rate', y='name',
                                         orientation='h',
                                         title='Student Attendance Rates (Lowest 20)',
                                         labels={'rate': 'Attendance Rate (%)', 'name': 'Student'})
            else:
                performance_chart = px.bar(title='No data available')

            conn.close()

            return {
                'overall_rate': overall_rate,
                'at_risk_count': at_risk_count,
                'todays_sessions': todays_sessions,
                'active_alerts': active_alerts,
                'trend_chart': trend_chart,
                'status_chart': status_chart,
                'performance_chart': performance_chart
            }

        except Exception as e:
            print(f"Error getting dashboard data: {e}")
            return {
                'overall_rate': 0,
                'at_risk_count': 0,
                'todays_sessions': 0,
                'active_alerts': 0,
                'trend_chart': px.line(title='Error loading data'),
                'status_chart': px.pie(title='Error loading data'),
                'performance_chart': px.bar(title='Error loading data')
            }

    def run_dashboard(self, host='127.0.0.1', port=8050, debug=False):
        """Run the dashboard server"""
        print(f"Starting dashboard server at http://{host}:{port}")
        self.app.run_server(host=host, port=port, debug=debug)
