import logging
import calendar as cal
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Tuple
from university_system.utils.logging.log_config import configure_logging
from .exceptions import PermissionError, ValidationError
from .config import ValidationUtils

logger = configure_logging(name=__name__)

try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.patches import Rectangle
    import seaborn as sns
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

try:
    import plotly.graph_objs as go
    import plotly.express as px
    from plotly.offline import plot
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False


class EnhancedCalendarVisualizationManager:
    """Advanced calendar visualization and views"""

    def __init__(self, db_manager, auth_manager):
        self.db_manager = db_manager
        self.auth_manager = auth_manager

    def create_timeline_visualization(self, academic_year_id: str,
                                    output_path: str = None) -> Tuple[bool, str]:
        """Create timeline visualization of academic year"""
        if not MATPLOTLIB_AVAILABLE:
            return False, "Matplotlib not available for visualizations"

        try:
            # Get events for academic year
            query = '''
            SELECT e.*, s.name as semester_name
            FROM academic_calendar_events e
            LEFT JOIN semesters s ON (e.date BETWEEN s.start_date AND s.end_date)
            WHERE s.academic_year_id = ?
            ORDER BY COALESCE(e.date, e.date_start)
            '''
            rows = self.db_manager.execute_query(query, (academic_year_id,))

            if not rows:
                return False, "No events found for academic year"

            # Create timeline plot
            fig, ax = plt.subplots(figsize=(15, 8))

            # Color mapping for event types
            colors = {
                'Academic': '#1E3A8A',
                'Administrative': '#7C2D12',
                'Social': '#15803D',
                'Sports': '#DC2626',
                'Holiday': '#7C3AED',
                'Deadline': '#EA580C'
            }

            events_by_type = defaultdict(list)

            for event in rows:
                event_date = event['date'] or event['date_start']
                if event_date:
                    date_obj = datetime.strptime(event_date, "%Y-%m-%d")
                    events_by_type[event['event_type']].append({
                        'date': date_obj,
                        'name': event['name'],
                        'semester': event['semester_name']
                    })

            # Plot events by type
            y_pos = 0
            type_positions = {}

            for event_type, events in events_by_type.items():
                dates = [e['date'] for e in events]
                y_positions = [y_pos] * len(dates)

                ax.scatter(dates, y_positions,
                          c=colors.get(event_type, '#6B7280'),
                          label=event_type, s=100, alpha=0.7)

                # Add event names as annotations
                for i, event in enumerate(events):
                    if i % 3 == 0:  # Only show every 3rd label to avoid crowding
                        ax.annotate(event['name'][:20],
                                  (event['date'], y_pos),
                                  xytext=(5, 5), textcoords='offset points',
                                  fontsize=8, alpha=0.8)

                type_positions[event_type] = y_pos
                y_pos += 1

            # Format plot
            ax.set_ylabel('Event Types')
            ax.set_xlabel('Date')
            ax.set_title(f'Academic Calendar Timeline - {academic_year_id}')
            ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
            ax.grid(True, alpha=0.3)

            # Format x-axis
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
            ax.xaxis.set_major_locator(mdates.MonthLocator())
            plt.xticks(rotation=45)

            # Set y-axis labels
            ax.set_yticks(list(type_positions.values()))
            ax.set_yticklabels(list(type_positions.keys()))

            plt.tight_layout()

            if output_path:
                plt.savefig(output_path, dpi=300, bbox_inches='tight')
                plt.close()
                return True, f"Timeline saved to {output_path}"
            else:
                plt.show()
                return True, "Timeline displayed"

        except Exception as e:
            logger.error(f"Failed to create timeline visualization: {e}")
            return False, f"Error creating timeline: {str(e)}"

    def create_conflict_visualization(self, date_range: Tuple[str, str],
                                    output_path: str = None) -> Tuple[bool, str]:
        """Create visualization showing event conflicts"""
        if not MATPLOTLIB_AVAILABLE:
            return False, "Matplotlib not available for visualizations"

        try:
            # Get overlapping events
            query = '''
            SELECT e1.id as event1_id, e1.name as event1_name,
                   e1.date_start as event1_start, e1.date_end as event1_end,
                   e2.id as event2_id, e2.name as event2_name,
                   e2.date_start as event2_start, e2.date_end as event2_end
            FROM academic_calendar_events e1
            JOIN academic_calendar_events e2 ON e1.id != e2.id
            WHERE e1.date_start BETWEEN ? AND ?
            AND e2.date_start BETWEEN ? AND ?
            AND e1.date_start < e2.date_end
            AND e2.date_start < e1.date_end
            '''

            rows = self.db_manager.execute_query(query,
                                               date_range + date_range)

            if not rows:
                return True, "No conflicts found in date range"

            # Create conflict visualization
            fig, ax = plt.subplots(figsize=(12, 8))

            conflicts = []
            for row in rows:
                conflicts.append({
                    'event1': row['event1_name'],
                    'event2': row['event2_name'],
                    'start1': datetime.strptime(row['event1_start'], "%Y-%m-%d"),
                    'end1': datetime.strptime(row['event1_end'], "%Y-%m-%d"),
                    'start2': datetime.strptime(row['event2_start'], "%Y-%m-%d"),
                    'end2': datetime.strptime(row['event2_end'], "%Y-%m-%d")
                })

            # Plot conflicts
            for i, conflict in enumerate(conflicts):
                y_pos = i

                # Event 1
                ax.barh(y_pos - 0.2, (conflict['end1'] - conflict['start1']).days,
                       left=conflict['start1'], height=0.3,
                       color='red', alpha=0.6, label='Event 1' if i == 0 else "")

                # Event 2
                ax.barh(y_pos + 0.2, (conflict['end2'] - conflict['start2']).days,
                       left=conflict['start2'], height=0.3,
                       color='blue', alpha=0.6, label='Event 2' if i == 0 else "")

                # Add labels
                ax.text(conflict['start1'], y_pos - 0.2, conflict['event1'][:20],
                       ha='left', va='center', fontsize=8)
                ax.text(conflict['start2'], y_pos + 0.2, conflict['event2'][:20],
                       ha='left', va='center', fontsize=8)

            ax.set_ylabel('Conflicts')
            ax.set_xlabel('Date')
            ax.set_title('Event Conflicts Visualization')
            ax.legend()
            ax.grid(True, alpha=0.3)

            plt.tight_layout()

            if output_path:
                plt.savefig(output_path, dpi=300, bbox_inches='tight')
                plt.close()
                return True, f"Conflict visualization saved to {output_path}"
            else:
                plt.show()
                return True, "Conflict visualization displayed"

        except Exception as e:
            logger.error(f"Failed to create conflict visualization: {e}")
            return False, f"Error creating visualization: {str(e)}"


class DataVisualizationManager:
    """Creates various data visualizations for calendar analytics"""

    def __init__(self, db_manager, auth_manager):
        self.db_manager = db_manager
        self.auth_manager = auth_manager

    def create_calendar_heatmap(self, year: int, output_path: str = None) -> Tuple[bool, str]:
        """Create a calendar heatmap showing event density"""
        if not self.auth_manager.check_permission('export_data'):
            raise PermissionError("Insufficient permissions to create visualizations")

        if not PLOTLY_AVAILABLE:
            return False, "Plotly not available for visualizations"

        try:
            # Validate year
            current_year = datetime.now().year
            if not (current_year - 5 <= year <= current_year + 5):
                raise ValidationError("Year must be within 5 years of current year")

            start_date = f"{year}-01-01"
            end_date = f"{year}-12-31"

            query = """
                SELECT DATE(COALESCE(e.date, e.date_start)) as event_date, COUNT(*) as event_count
                FROM academic_calendar_events e
                WHERE (e.date BETWEEN ? AND ?)
                OR (e.date_start BETWEEN ? AND ?)
                GROUP BY DATE(COALESCE(e.date, e.date_start))
                ORDER BY event_date
            """

            rows = self.db_manager.execute_query(query, (start_date, end_date, start_date, end_date))
            data = {row['event_date']: row['event_count'] for row in rows}

            # Create date range for the year
            start = datetime(year, 1, 1)
            dates = []
            event_counts = []

            days_in_year = 366 if cal.isleap(year) else 365
            for i in range(days_in_year):
                current_date = start + timedelta(days=i)
                date_str = current_date.strftime("%Y-%m-%d")
                dates.append(current_date)
                event_counts.append(data.get(date_str, 0))

            # Create heatmap using plotly
            fig = go.Figure(data=go.Heatmap(
                x=[d.strftime("%U") for d in dates],  # Week number
                y=[d.strftime("%A") for d in dates],  # Day of week
                z=event_counts,
                colorscale='Viridis',
                hoverongaps=False,
                hovertemplate='Week %{x}<br>%{y}<br>Events: %{z}<extra></extra>'
            ))

            fig.update_layout(
                title=f'Academic Calendar Activity Heatmap - {year}',
                xaxis_title='Week of Year',
                yaxis_title='Day of Week',
                height=600
            )

            if output_path:
                safe_path = ValidationUtils.sanitize_filename(output_path)
                fig.write_html(safe_path)
                return True, f"Heatmap saved to {safe_path}"
            else:
                html_str = plot(fig, output_type='div', include_plotlyjs=True)
                return True, html_str

        except Exception as e:
            logger.error(f"Failed to create heatmap: {e}")
            return False, f"Error creating heatmap: {str(e)}"

    def create_event_distribution_chart(self, timeframe: str = 'month', output_path: str = None) -> Tuple[bool, str]:
        """Create event distribution charts by type"""
        if not self.auth_manager.check_permission('export_data'):
            raise PermissionError("Insufficient permissions to create visualizations")

        if not PLOTLY_AVAILABLE:
            return False, "Plotly not available for visualizations"

        try:
            timeframe = ValidationUtils.sanitize_string(timeframe, 20).lower()

            query = """
                SELECT e.event_type, COUNT(*) as count
                FROM academic_calendar_events e
            """

            params = []

            # Add time filter
            if timeframe == 'month':
                current_month_start = datetime.now().replace(day=1).strftime("%Y-%m-%d")
                query += " WHERE COALESCE(e.date, e.date_start) >= ?"
                params.append(current_month_start)
            elif timeframe == 'semester':
                semester_start = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
                query += " WHERE COALESCE(e.date, e.date_start) >= ?"
                params.append(semester_start)
            elif timeframe == 'year':
                year_start = datetime.now().replace(month=1, day=1).strftime("%Y-%m-%d")
                query += " WHERE COALESCE(e.date, e.date_start) >= ?"
                params.append(year_start)

            query += " GROUP BY e.event_type ORDER BY count DESC"

            rows = self.db_manager.execute_query(query, tuple(params))
            data = [dict(row) for row in rows]

            if not data:
                return False, "No data found for the specified timeframe"

            # Create pie chart
            event_types = [row['event_type'] for row in data]
            counts = [row['count'] for row in data]

            fig = px.pie(
                values=counts,
                names=event_types,
                title=f'Event Distribution by Type - {timeframe.title()}'
            )

            fig.update_traces(textposition='inside', textinfo='percent+label')

            if output_path:
                safe_path = ValidationUtils.sanitize_filename(output_path)
                fig.write_html(safe_path)
                return True, f"Distribution chart saved to {safe_path}"
            else:
                html_str = plot(fig, output_type='div', include_plotlyjs=True)
                return True, html_str

        except Exception as e:
            logger.error(f"Failed to create distribution chart: {e}")
            return False, f"Error creating distribution chart: {str(e)}"
