"""
Real-Time Dashboard Service

Provides dynamic dashboards with real-time data updates.
"""

import logging
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.infrastructure.analytics.models import DashboardWidget, AnalyticsMetric
from education_system.university_system.core.sql_safety import validate_identifier  # nosec B608
from education_system.university_system.infrastructure.analytics.retention_prediction import get_retention_predictor
from education_system.university_system.infrastructure.analytics.performance_analytics import get_performance_analyzer
from education_system.university_system.infrastructure.analytics.report_generator import get_report_generator
from education_system.university_system.infrastructure.analytics.data_warehouse import get_data_warehouse

logger = logging.getLogger(__name__)


class DashboardService:
    """
    Real-time dashboard service

    Features:
    - Custom dashboard creation
    - Widget management (charts, metrics, tables, gauges)
    - Real-time data refresh
    - Dashboard sharing and permissions
    - Layout persistence
    - Widget configuration
    """

    def __init__(self):
        """Initialize dashboard service"""
        self._initialize_tables()

        # Get analytics services
        self.retention = get_retention_predictor()
        self.performance = get_performance_analyzer()
        self.reports = get_report_generator()
        self.warehouse = get_data_warehouse()

    def _initialize_tables(self):
        """Create dashboard tables if they don't exist"""
        try:
            with transaction() as conn:
                # Dashboards table
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS dashboards (
                        dashboard_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        description TEXT,
                        owner_id TEXT NOT NULL,
                        shared BOOLEAN DEFAULT 0,
                        layout_config TEXT,
                        refresh_interval INTEGER DEFAULT 300,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # Dashboard widgets table
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS dashboard_widgets (
                        widget_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        dashboard_id INTEGER NOT NULL,
                        widget_type TEXT NOT NULL,
                        title TEXT NOT NULL,
                        data_source TEXT NOT NULL,
                        configuration TEXT,
                        position_x INTEGER DEFAULT 0,
                        position_y INTEGER DEFAULT 0,
                        width INTEGER DEFAULT 4,
                        height INTEGER DEFAULT 3,
                        refresh_interval INTEGER DEFAULT 300,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (dashboard_id) REFERENCES dashboards(dashboard_id) ON DELETE CASCADE
                    )
                ''')

                # Dashboard permissions table
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS dashboard_permissions (
                        permission_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        dashboard_id INTEGER NOT NULL,
                        user_id TEXT,
                        role TEXT,
                        can_view BOOLEAN DEFAULT 1,
                        can_edit BOOLEAN DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (dashboard_id) REFERENCES dashboards(dashboard_id) ON DELETE CASCADE
                    )
                ''')

                # Create indices
                conn.execute('CREATE INDEX IF NOT EXISTS idx_dashboards_owner ON dashboards(owner_id)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_widgets_dashboard ON dashboard_widgets(dashboard_id)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_permissions_dashboard ON dashboard_permissions(dashboard_id)')

        except Exception as e:
            logger.error(f"Error initializing dashboard tables: {e}")

    # Dashboard Management

    def create_dashboard(
        self,
        name: str,
        owner_id: str,
        description: Optional[str] = None,
        shared: bool = False,
        layout_config: Optional[Dict[str, Any]] = None,
        refresh_interval: int = 300
    ) -> Optional[int]:
        """
        Create a new dashboard

        Args:
            name: Dashboard name
            owner_id: User ID of dashboard owner
            description: Dashboard description
            shared: Whether dashboard is shared
            layout_config: Dashboard layout configuration
            refresh_interval: Auto-refresh interval in seconds

        Returns:
            Dashboard ID if successful
        """
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO dashboards
                    (name, description, owner_id, shared, layout_config, refresh_interval)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    name,
                    description,
                    owner_id,
                    1 if shared else 0,
                    json.dumps(layout_config) if layout_config else None,
                    refresh_interval
                ))

                dashboard_id = cursor.lastrowid
                logger.info(f"Created dashboard '{name}' (ID: {dashboard_id})")
                return dashboard_id

        except Exception as e:
            logger.error(f"Error creating dashboard: {e}")
            return None

    def get_dashboard(self, dashboard_id: int) -> Optional[Dict[str, Any]]:
        """Get dashboard details"""
        try:
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT
                        dashboard_id, name, description, owner_id,
                        shared, layout_config, refresh_interval,
                        created_at, updated_at
                    FROM dashboards
                    WHERE dashboard_id = ?
                ''', (dashboard_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                return {
                    'dashboard_id': row[0],
                    'name': row[1],
                    'description': row[2],
                    'owner_id': row[3],
                    'shared': bool(row[4]),
                    'layout_config': json.loads(row[5]) if row[5] else {},
                    'refresh_interval': row[6],
                    'created_at': row[7],
                    'updated_at': row[8]
                }

        except Exception as e:
            logger.error(f"Error getting dashboard: {e}")
            return None

    def list_dashboards(
        self,
        user_id: Optional[str] = None,
        include_shared: bool = True
    ) -> List[Dict[str, Any]]:
        """
        List dashboards accessible to user

        Args:
            user_id: Filter by owner (None = all)
            include_shared: Include shared dashboards

        Returns:
            List of dashboard summaries
        """
        try:
            with get_connection() as conn:
                if user_id:
                    if include_shared:
                        query = '''
                            SELECT
                                d.dashboard_id, d.name, d.description, d.owner_id,
                                d.shared, d.refresh_interval, d.created_at,
                                COUNT(w.widget_id) as widget_count
                            FROM dashboards d
                            LEFT JOIN dashboard_widgets w ON d.dashboard_id = w.dashboard_id
                            WHERE d.owner_id = ? OR d.shared = 1
                            GROUP BY d.dashboard_id
                            ORDER BY d.updated_at DESC
                        '''
                        params = (user_id,)
                    else:
                        query = '''
                            SELECT
                                d.dashboard_id, d.name, d.description, d.owner_id,
                                d.shared, d.refresh_interval, d.created_at,
                                COUNT(w.widget_id) as widget_count
                            FROM dashboards d
                            LEFT JOIN dashboard_widgets w ON d.dashboard_id = w.dashboard_id
                            WHERE d.owner_id = ?
                            GROUP BY d.dashboard_id
                            ORDER BY d.updated_at DESC
                        '''
                        params = (user_id,)
                else:
                    query = '''
                        SELECT
                            d.dashboard_id, d.name, d.description, d.owner_id,
                            d.shared, d.refresh_interval, d.created_at,
                            COUNT(w.widget_id) as widget_count
                        FROM dashboards d
                        LEFT JOIN dashboard_widgets w ON d.dashboard_id = w.dashboard_id
                        GROUP BY d.dashboard_id
                        ORDER BY d.updated_at DESC
                    '''
                    params = ()

                cursor = conn.execute(query, params)

                dashboards = []
                for row in cursor.fetchall():
                    dashboards.append({
                        'dashboard_id': row[0],
                        'name': row[1],
                        'description': row[2],
                        'owner_id': row[3],
                        'shared': bool(row[4]),
                        'refresh_interval': row[5],
                        'created_at': row[6],
                        'widget_count': row[7]
                    })

                return dashboards

        except Exception as e:
            logger.error(f"Error listing dashboards: {e}")
            return []

    _DASHBOARD_ALLOWED_COLUMNS = frozenset({
        'name', 'description', 'owner_id', 'shared', 'refresh_interval', 'layout_config',
    })

    def update_dashboard(
        self,
        dashboard_id: int,
        **updates
    ) -> bool:
        """Update dashboard properties"""
        try:
            if not updates:
                return True

            # Handle layout_config serialization
            if 'layout_config' in updates and updates['layout_config']:
                updates['layout_config'] = json.dumps(updates['layout_config'])

            # Validate column names against whitelist
            invalid_keys = set(updates.keys()) - self._DASHBOARD_ALLOWED_COLUMNS
            if invalid_keys:
                raise ValueError(f"Invalid column names: {invalid_keys}")

            # Validate each column name format for defense-in-depth
            for k in updates.keys():
                validate_identifier(k, "column name")

            # Build update query
            set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
            set_clause += ', updated_at = CURRENT_TIMESTAMP'
            values = list(updates.values()) + [dashboard_id]

            with transaction() as conn:
                conn.execute(f'''
                    UPDATE dashboards
                    SET {set_clause}
                    WHERE dashboard_id = ?
                ''', values)

            logger.info(f"Updated dashboard {dashboard_id}")
            return True

        except Exception as e:
            logger.error(f"Error updating dashboard: {e}")
            return False

    def delete_dashboard(self, dashboard_id: int) -> bool:
        """Delete dashboard and all widgets"""
        try:
            with transaction() as conn:
                conn.execute('DELETE FROM dashboards WHERE dashboard_id = ?', (dashboard_id,))

            logger.info(f"Deleted dashboard {dashboard_id}")
            return True

        except Exception as e:
            logger.error(f"Error deleting dashboard: {e}")
            return False

    # Widget Management

    def add_widget(
        self,
        dashboard_id: int,
        widget_type: str,
        title: str,
        data_source: str,
        configuration: Optional[Dict[str, Any]] = None,
        position_x: int = 0,
        position_y: int = 0,
        width: int = 4,
        height: int = 3,
        refresh_interval: int = 300
    ) -> Optional[int]:
        """
        Add widget to dashboard

        Args:
            dashboard_id: Target dashboard
            widget_type: Widget type (chart, metric, table, gauge)
            title: Widget title
            data_source: Data source identifier
            configuration: Widget-specific configuration
            position_x: X position in grid
            position_y: Y position in grid
            width: Widget width in grid units
            height: Widget height in grid units
            refresh_interval: Refresh interval in seconds

        Returns:
            Widget ID if successful
        """
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO dashboard_widgets
                    (dashboard_id, widget_type, title, data_source, configuration,
                     position_x, position_y, width, height, refresh_interval)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    dashboard_id,
                    widget_type,
                    title,
                    data_source,
                    json.dumps(configuration) if configuration else None,
                    position_x,
                    position_y,
                    width,
                    height,
                    refresh_interval
                ))

                # Update dashboard timestamp
                conn.execute('''
                    UPDATE dashboards
                    SET updated_at = CURRENT_TIMESTAMP
                    WHERE dashboard_id = ?
                ''', (dashboard_id,))

                widget_id = cursor.lastrowid
                logger.info(f"Added widget '{title}' to dashboard {dashboard_id}")
                return widget_id

        except Exception as e:
            logger.error(f"Error adding widget: {e}")
            return None

    def get_widget(self, widget_id: int) -> Optional[DashboardWidget]:
        """Get widget configuration"""
        try:
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT
                        widget_id, widget_type, title, data_source,
                        configuration, position_x, position_y,
                        width, height, refresh_interval
                    FROM dashboard_widgets
                    WHERE widget_id = ?
                ''', (widget_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                return DashboardWidget(
                    widget_id=str(row[0]),
                    widget_type=row[1],
                    title=row[2],
                    data_source=row[3],
                    configuration=json.loads(row[4]) if row[4] else {},
                    refresh_interval=row[9],
                    position={
                        'x': row[5],
                        'y': row[6],
                        'width': row[7],
                        'height': row[8]
                    }
                )

        except Exception as e:
            logger.error(f"Error getting widget: {e}")
            return None

    def get_dashboard_widgets(self, dashboard_id: int) -> List[DashboardWidget]:
        """Get all widgets for dashboard"""
        try:
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT
                        widget_id, widget_type, title, data_source,
                        configuration, position_x, position_y,
                        width, height, refresh_interval
                    FROM dashboard_widgets
                    WHERE dashboard_id = ?
                    ORDER BY position_y, position_x
                ''', (dashboard_id,))

                widgets = []
                for row in cursor.fetchall():
                    widgets.append(DashboardWidget(
                        widget_id=str(row[0]),
                        widget_type=row[1],
                        title=row[2],
                        data_source=row[3],
                        configuration=json.loads(row[4]) if row[4] else {},
                        refresh_interval=row[9],
                        position={
                            'x': row[5],
                            'y': row[6],
                            'width': row[7],
                            'height': row[8]
                        }
                    ))

                return widgets

        except Exception as e:
            logger.error(f"Error getting dashboard widgets: {e}")
            return []

    _WIDGET_ALLOWED_COLUMNS = frozenset({
        'widget_type', 'title', 'data_source', 'configuration',
        'position_x', 'position_y', 'width', 'height', 'refresh_interval',
    })

    def update_widget(self, widget_id: int, **updates) -> bool:
        """Update widget configuration"""
        try:
            if not updates:
                return True

            # Handle configuration serialization
            if 'configuration' in updates and updates['configuration']:
                updates['configuration'] = json.dumps(updates['configuration'])

            # Validate column names against whitelist
            invalid_keys = set(updates.keys()) - self._WIDGET_ALLOWED_COLUMNS
            if invalid_keys:
                raise ValueError(f"Invalid column names: {invalid_keys}")

            # Validate each column name format for defense-in-depth
            for k in updates.keys():
                validate_identifier(k, "column name")

            # Build update query
            set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
            values = list(updates.values()) + [widget_id]

            with transaction() as conn:
                conn.execute(f'''
                    UPDATE dashboard_widgets
                    SET {set_clause}
                    WHERE widget_id = ?
                ''', values)

            logger.info(f"Updated widget {widget_id}")
            return True

        except Exception as e:
            logger.error(f"Error updating widget: {e}")
            return False

    def delete_widget(self, widget_id: int) -> bool:
        """Delete widget from dashboard"""
        try:
            with transaction() as conn:
                conn.execute('DELETE FROM dashboard_widgets WHERE widget_id = ?', (widget_id,))

            logger.info(f"Deleted widget {widget_id}")
            return True

        except Exception as e:
            logger.error(f"Error deleting widget: {e}")
            return False

    # Data Fetching

    def get_widget_data(self, widget: DashboardWidget) -> Dict[str, Any]:
        """
        Fetch real-time data for widget

        Args:
            widget: Widget configuration

        Returns:
            Widget data in appropriate format
        """
        try:
            data_source = widget.data_source
            config = widget.configuration

            # Route to appropriate data source
            if data_source == 'retention_stats':
                return self._get_retention_stats()

            elif data_source == 'at_risk_students':
                limit = config.get('limit', 10)
                return self._get_at_risk_students(limit)

            elif data_source == 'gpa_trends':
                period = config.get('period_days', 365)
                return self._get_gpa_trends(period)

            elif data_source == 'course_performance':
                course_id = config.get('course_id')
                return self._get_course_performance(course_id)

            elif data_source == 'department_metrics':
                return self._get_department_metrics()

            elif data_source == 'enrollment_trends':
                period = config.get('period', 'monthly')
                return self._get_enrollment_trends(period)

            elif data_source == 'financial_summary':
                period = config.get('period', 'monthly')
                return self._get_financial_summary(period)

            elif data_source == 'student_success':
                return self._get_student_success_metrics()

            else:
                logger.warning(f"Unknown data source: {data_source}")
                return {'error': f'Unknown data source: {data_source}'}

        except Exception as e:
            logger.error(f"Error fetching widget data: {e}")
            return {'error': str(e)}

    def _get_retention_stats(self) -> Dict[str, Any]:
        """Get retention statistics"""
        stats = self.retention.get_retention_statistics()
        return {
            'type': 'metrics',
            'data': stats
        }

    def _get_at_risk_students(self, limit: int) -> Dict[str, Any]:
        """Get at-risk students"""
        predictions = self.retention.predict_at_risk_students(threshold=0.3, limit=limit)

        students = []
        for pred in predictions:
            students.append({
                'student_id': pred.student_id,
                'risk_level': pred.risk_level,
                'probability': round(pred.probability, 2),
                'factors': pred.contributing_factors,
                'actions': pred.recommended_actions
            })

        return {
            'type': 'table',
            'data': students
        }

    def _get_gpa_trends(self, period_days: int) -> Dict[str, Any]:
        """Get GPA trends"""
        trends = self.performance.analyze_gpa_trends(period_days)
        return {
            'type': 'chart',
            'data': trends
        }

    def _get_course_performance(self, course_id: Optional[str]) -> Dict[str, Any]:
        """Get course performance metrics"""
        metrics = self.performance.get_course_performance_metrics(course_id)
        return {
            'type': 'table',
            'data': metrics
        }

    def _get_department_metrics(self) -> Dict[str, Any]:
        """Get department performance metrics"""
        metrics = self.performance.get_department_metrics()
        return {
            'type': 'table',
            'data': metrics
        }

    def _get_enrollment_trends(self, period: str) -> Dict[str, Any]:
        """Get enrollment trends from data warehouse"""
        data = self.warehouse.get_bi_dataset('enrollment_trends', {'period': period})
        return {
            'type': 'chart',
            'data': data
        }

    def _get_financial_summary(self, period: str) -> Dict[str, Any]:
        """Get financial summary from reports"""
        dashboard = self.reports.generate_executive_dashboard(period)
        return {
            'type': 'metrics',
            'data': dashboard.get('financial_summary', {})
        }

    def _get_student_success_metrics(self) -> Dict[str, Any]:
        """Get student success metrics"""
        try:
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT
                        COUNT(DISTINCT s.student_id) as total_students,
                        AVG(sdp.current_gpa) as avg_gpa,
                        COUNT(DISTINCT CASE WHEN s.status = 'Active' THEN s.student_id END) as active_students,
                        COUNT(DISTINCT CASE WHEN s.status = 'Graduated' THEN s.student_id END) as graduated_students,
                        COUNT(DISTINCT e.course_id) as total_enrollments,
                        AVG(CASE WHEN a.present = 1 THEN 100.0 ELSE 0.0 END) as avg_attendance
                    FROM students s
                    LEFT JOIN student_degree_progress sdp ON s.student_id = sdp.student_id
                    LEFT JOIN enrollments e ON s.student_id = e.student_id
                    LEFT JOIN attendance a ON s.student_id = a.student_id
                        AND a.date >= date('now', '-30 days')
                ''')

                row = cursor.fetchone()

                return {
                    'type': 'metrics',
                    'data': {
                        'total_students': row[0] or 0,
                        'avg_gpa': round(row[1], 2) if row[1] else 0.0,
                        'active_students': row[2] or 0,
                        'graduated_students': row[3] or 0,
                        'total_enrollments': row[4] or 0,
                        'avg_attendance': round(row[5], 1) if row[5] else 0.0
                    }
                }

        except Exception as e:
            logger.error(f"Error getting student success metrics: {e}")
            return {'type': 'metrics', 'data': {}}

    def refresh_dashboard_data(self, dashboard_id: int) -> Dict[str, Any]:
        """
        Refresh all widget data for dashboard

        Args:
            dashboard_id: Dashboard ID

        Returns:
            Complete dashboard data with all widgets
        """
        dashboard = self.get_dashboard(dashboard_id)
        if not dashboard:
            return {'error': 'Dashboard not found'}

        widgets = self.get_dashboard_widgets(dashboard_id)

        widget_data = []
        for widget in widgets:
            data = self.get_widget_data(widget)
            widget_data.append({
                'widget_id': widget.widget_id,
                'widget_type': widget.widget_type,
                'title': widget.title,
                'position': widget.position,
                'data': data
            })

        return {
            'dashboard': dashboard,
            'widgets': widget_data,
            'refreshed_at': datetime.utcnow().isoformat()
        }


# Singleton instance
_dashboard_service: Optional[DashboardService] = None


def get_dashboard_service() -> DashboardService:
    """Get or create dashboard service singleton"""
    global _dashboard_service
    if _dashboard_service is None:
        _dashboard_service = DashboardService()
    return _dashboard_service
