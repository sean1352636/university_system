"""Analytics and reporting for logs."""

from datetime import datetime, timedelta

try:
    import pandas as pd  # type: ignore
except Exception:
    pd = None  # type: ignore

try:
    import matplotlib.pyplot as plt  # type: ignore
    MATPLOTLIB_AVAILABLE = True
except Exception:
    MATPLOTLIB_AVAILABLE = False
    class _MatplotlibDummy:
        def __getattr__(self, name):
            return self
        def __call__(self, *args, **kwargs):  # pragma: no cover
            return None
    plt = _MatplotlibDummy()

try:
    import seaborn as sns  # type: ignore
    SEABORN_AVAILABLE = True
except Exception:
    SEABORN_AVAILABLE = False
    class _SeabornDummy:
        def __getattr__(self, name):
            return self
        def __call__(self, *args, **kwargs):  # pragma: no cover
            return None
    sns = _SeabornDummy()

from .database import LogDatabase


class LogAnalytics:
    """Analytics and reporting for logs"""

    def __init__(self, db: LogDatabase):
        self.db = db

    def generate_activity_summary(self, days=7):
        """Generate activity summary for the last N days"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        filters = {
            'date_from': start_date.strftime('%Y-%m-%d'),
            'date_to': end_date.strftime('%Y-%m-%d')
        }

        logs = self.db.search_logs(filters, limit=10000)

        if not logs:
            return {"error": "No logs found for the specified period"}

        # Convert to DataFrame for easier analysis
        df = pd.DataFrame(logs)

        summary = {
            "period": f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
            "total_activities": len(logs),
            "unique_users": df['username'].nunique(),
            "most_active_users": df['username'].value_counts().head(5).to_dict(),
            "activity_by_action": df['action'].value_counts().to_dict(),
            "activity_by_module": df['module'].value_counts().to_dict(),
            "success_rate": (df['status'] == 'success').mean() * 100,
            "failed_activities": len(df[df['status'] == 'failure']),
            "peak_activity_hour": pd.to_datetime(df['timestamp']).dt.hour.value_counts().index[0]
        }

        return summary

    def generate_user_activity_report(self, user_id, days=30):
        """Generate detailed activity report for a specific user"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        filters = {
            'date_from': start_date.strftime('%Y-%m-%d'),
            'date_to': end_date.strftime('%Y-%m-%d'),
            'user_id': user_id
        }

        logs = self.db.search_logs(filters, limit=5000)

        if not logs:
            return {"error": f"No activities found for user {user_id}"}

        df = pd.DataFrame(logs)

        report = {
            "user_id": user_id,
            "username": df['username'].iloc[0],
            "period": f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
            "total_activities": len(logs),
            "activities_by_day": df.groupby(pd.to_datetime(df['timestamp']).dt.date).size().to_dict(),
            "modules_used": df['module'].value_counts().to_dict(),
            "actions_performed": df['action'].value_counts().to_dict(),
            "success_rate": (df['status'] == 'success').mean() * 100,
            "most_active_days": df.groupby(pd.to_datetime(df['timestamp']).dt.date).size().nlargest(5).to_dict(),
            "activity_hours": pd.to_datetime(df['timestamp']).dt.hour.value_counts().to_dict()
        }

        return report

    def create_activity_chart(self, chart_type="daily", days=7, save_path=None):
        """Create activity visualization charts"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        filters = {
            'date_from': start_date.strftime('%Y-%m-%d'),
            'date_to': end_date.strftime('%Y-%m-%d')
        }

        logs = self.db.search_logs(filters, limit=10000)

        if not logs:
            print("No data available for chart generation")
            return None

        df = pd.DataFrame(logs)
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        plt.style.use('seaborn-v0_8' if 'seaborn-v0_8' in plt.style.available else 'default')
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle(f'Activity Analysis - Last {days} Days', fontsize=16)

        # Daily activity trend
        daily_activity = df.groupby(df['timestamp'].dt.date).size()
        axes[0, 0].plot(daily_activity.index, daily_activity.values, marker='o')
        axes[0, 0].set_title('Daily Activity Trend')
        axes[0, 0].set_xlabel('Date')
        axes[0, 0].set_ylabel('Number of Activities')
        axes[0, 0].tick_params(axis='x', rotation=45)

        # Activity by action type
        action_counts = df['action'].value_counts()
        axes[0, 1].pie(action_counts.values, labels=action_counts.index, autopct='%1.1f%%')
        axes[0, 1].set_title('Activity Distribution by Action Type')

        # Hourly activity pattern
        hourly_activity = df['timestamp'].dt.hour.value_counts().sort_index()
        axes[1, 0].bar(hourly_activity.index, hourly_activity.values)
        axes[1, 0].set_title('Activity Pattern by Hour')
        axes[1, 0].set_xlabel('Hour of Day')
        axes[1, 0].set_ylabel('Number of Activities')

        # Top modules
        module_counts = df['module'].value_counts().head(10)
        axes[1, 1].barh(module_counts.index, module_counts.values)
        axes[1, 1].set_title('Top 10 Most Used Modules')
        axes[1, 1].set_xlabel('Number of Activities')

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"Chart saved to {save_path}")
        else:
            plt.show()

        plt.close()
        return save_path
