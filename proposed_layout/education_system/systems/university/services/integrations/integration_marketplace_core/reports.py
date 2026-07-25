"""Reports & Dashboard Manager and CLI functions"""

from education_system.systems.university.services.integrations.integration_marketplace_core._imports import datetime, timedelta, Any, Dict, List, get_connection


class ReportsDashboardManager:
    """Manages reports and dashboard data for integrations"""

    @staticmethod
    def get_dashboard_overview() -> Dict[str, Any]:
        """Real-time dashboard with KPIs, charts, and status widgets"""
        dashboard = {
            'generated_at': datetime.now().isoformat(),
            'kpis': {},
            'status_summary': {},
            'recent_activity': []
        }

        with get_connection() as conn:
            cursor = conn.cursor()

            # KPIs
            cursor.execute('SELECT COUNT(*) FROM integration_catalog WHERE is_active = 1')
            dashboard['kpis']['total_available'] = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM installed_integrations WHERE status = "active"')
            dashboard['kpis']['total_installed'] = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM installed_integrations WHERE is_enabled = 1')
            dashboard['kpis']['total_enabled'] = cursor.fetchone()[0]

            cursor.execute('''
                SELECT COUNT(*) FROM integration_sync_logs
                WHERE sync_start_time >= date('now', '-1 day')
            ''')
            dashboard['kpis']['syncs_last_24h'] = cursor.fetchone()[0]

            cursor.execute('''
                SELECT COUNT(*) FROM integration_sync_logs
                WHERE sync_status = 'failed' AND sync_start_time >= date('now', '-1 day')
            ''')
            dashboard['kpis']['failed_syncs_24h'] = cursor.fetchone()[0]

            # Status summary
            cursor.execute('''
                SELECT sync_status, COUNT(*) FROM integration_sync_logs
                WHERE sync_start_time >= date('now', '-7 days')
                GROUP BY sync_status
            ''')
            dashboard['status_summary'] = {row[0]: row[1] for row in cursor.fetchall()}

            # Recent activity
            cursor.execute('''
                SELECT isl.log_id, ic.integration_name, isl.sync_status, isl.sync_start_time
                FROM integration_sync_logs isl
                JOIN installed_integrations ii ON isl.install_id = ii.install_id
                JOIN integration_catalog ic ON ii.integration_id = ic.integration_id
                ORDER BY isl.sync_start_time DESC
                LIMIT 10
            ''')
            dashboard['recent_activity'] = [dict(row) for row in cursor.fetchall()]

        return dashboard

    @staticmethod
    def generate_health_report() -> Dict[str, Any]:
        """Comprehensive health report for all integrations"""
        report = {
            'generated_at': datetime.now().isoformat(),
            'overall_health': 'healthy',
            'integrations': []
        }

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT ii.install_id, ic.integration_name, ii.status, ii.is_enabled,
                       ii.last_sync_date,
                       (SELECT COUNT(*) FROM integration_sync_logs isl
                        WHERE isl.install_id = ii.install_id AND isl.sync_status = 'failed'
                        AND isl.sync_start_time >= date('now', '-7 days')) as recent_failures
                FROM installed_integrations ii
                JOIN integration_catalog ic ON ii.integration_id = ic.integration_id
                WHERE ii.status != 'uninstalled'
            ''')

            unhealthy_count = 0
            for row in cursor.fetchall():
                health_status = 'healthy'
                issues = []

                if row['recent_failures'] > 0:
                    health_status = 'warning' if row['recent_failures'] < 3 else 'critical'
                    issues.append(f"{row['recent_failures']} failed syncs in last 7 days")

                if not row['is_enabled']:
                    health_status = 'disabled'
                    issues.append("Integration is disabled")

                if row['last_sync_date']:
                    last_sync = datetime.fromisoformat(row['last_sync_date'].replace('Z', '+00:00'))
                    if (datetime.now() - last_sync.replace(tzinfo=None)).days > 7:
                        if health_status == 'healthy':
                            health_status = 'warning'
                        issues.append("No sync in over 7 days")

                if health_status in ['warning', 'critical']:
                    unhealthy_count += 1

                report['integrations'].append({
                    'install_id': row['install_id'],
                    'integration_name': row['integration_name'],
                    'health_status': health_status,
                    'issues': issues
                })

            if unhealthy_count > len(report['integrations']) / 2:
                report['overall_health'] = 'critical'
            elif unhealthy_count > 0:
                report['overall_health'] = 'warning'

        return report

    @staticmethod
    def get_error_analysis(days: int = 30) -> Dict[str, Any]:
        """Analyze and categorize sync errors by type/frequency"""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        analysis = {
            'period': f"Last {days} days",
            'total_errors': 0,
            'error_by_type': {},
            'error_by_integration': {},
            'top_error_messages': []
        }

        with get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT COUNT(*) FROM integration_sync_logs
                WHERE sync_status = 'failed' AND sync_start_time >= ?
            ''', (cutoff,))
            analysis['total_errors'] = cursor.fetchone()[0]

            cursor.execute('''
                SELECT ic.integration_name, COUNT(*) as error_count
                FROM integration_sync_logs isl
                JOIN installed_integrations ii ON isl.install_id = ii.install_id
                JOIN integration_catalog ic ON ii.integration_id = ic.integration_id
                WHERE isl.sync_status = 'failed' AND isl.sync_start_time >= ?
                GROUP BY ic.integration_name
                ORDER BY error_count DESC
            ''', (cutoff,))
            analysis['error_by_integration'] = {row[0]: row[1] for row in cursor.fetchall()}

            cursor.execute('''
                SELECT error_details, COUNT(*) as count
                FROM integration_sync_logs
                WHERE sync_status = 'failed' AND error_details IS NOT NULL
                    AND sync_start_time >= ?
                GROUP BY error_details
                ORDER BY count DESC
                LIMIT 10
            ''', (cutoff,))
            analysis['top_error_messages'] = [
                {'message': row[0], 'count': row[1]}
                for row in cursor.fetchall()
            ]

        return analysis

    @staticmethod
    def get_usage_trends(days: int = 30) -> Dict[str, Any]:
        """Usage trend data for visualization"""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        trends = {
            'period': f"Last {days} days",
            'daily_syncs': [],
            'daily_records': []
        }

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT DATE(sync_start_time) as sync_date,
                       COUNT(*) as sync_count,
                       SUM(COALESCE(records_synced, 0)) as total_records
                FROM integration_sync_logs
                WHERE sync_start_time >= ?
                GROUP BY DATE(sync_start_time)
                ORDER BY sync_date
            ''', (cutoff,))

            for row in cursor.fetchall():
                trends['daily_syncs'].append({'date': row[0], 'count': row[1]})
                trends['daily_records'].append({'date': row[0], 'records': row[2]})

        return trends

    @staticmethod
    def get_api_call_statistics(days: int = 30) -> Dict[str, Any]:
        """Statistics on API calls per integration"""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        stats = {
            'period': f"Last {days} days",
            'by_integration': []
        }

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT ic.integration_name,
                       COUNT(isl.log_id) as total_syncs,
                       SUM(CASE WHEN isl.sync_status = 'success' THEN 1 ELSE 0 END) as successful,
                       SUM(CASE WHEN isl.sync_status = 'failed' THEN 1 ELSE 0 END) as failed,
                       AVG(COALESCE(isl.records_synced, 0)) as avg_records
                FROM integration_sync_logs isl
                JOIN installed_integrations ii ON isl.install_id = ii.install_id
                JOIN integration_catalog ic ON ii.integration_id = ic.integration_id
                WHERE isl.sync_start_time >= ?
                GROUP BY ic.integration_name
                ORDER BY total_syncs DESC
            ''', (cutoff,))

            for row in cursor.fetchall():
                stats['by_integration'].append({
                    'integration_name': row[0],
                    'total_syncs': row[1],
                    'successful': row[2],
                    'failed': row[3],
                    'success_rate': round(row[2] / row[1] * 100, 1) if row[1] > 0 else 0,
                    'avg_records_per_sync': round(row[4] or 0, 1)
                })

        return stats

    @staticmethod
    def compare_integration_performance(install_ids: List[int]) -> Dict[str, Any]:
        """Side-by-side performance comparison"""
        comparison = {'integrations': []}

        with get_connection() as conn:
            cursor = conn.cursor()
            for install_id in install_ids:
                cursor.execute('''
                    SELECT ic.integration_name,
                           COUNT(isl.log_id) as total_syncs,
                           SUM(CASE WHEN isl.sync_status = 'success' THEN 1 ELSE 0 END) as successful,
                           AVG(COALESCE(isl.records_synced, 0)) as avg_records,
                           AVG(
                               CASE WHEN isl.sync_end_time IS NOT NULL
                               THEN (julianday(isl.sync_end_time) - julianday(isl.sync_start_time)) * 86400
                               ELSE NULL END
                           ) as avg_duration_seconds
                    FROM installed_integrations ii
                    JOIN integration_catalog ic ON ii.integration_id = ic.integration_id
                    LEFT JOIN integration_sync_logs isl ON ii.install_id = isl.install_id
                    WHERE ii.install_id = ?
                    GROUP BY ii.install_id
                ''', (install_id,))

                row = cursor.fetchone()
                if row:
                    comparison['integrations'].append({
                        'install_id': install_id,
                        'integration_name': row[0],
                        'total_syncs': row[1] or 0,
                        'success_rate': round((row[2] or 0) / (row[1] or 1) * 100, 1),
                        'avg_records': round(row[3] or 0, 1),
                        'avg_duration_seconds': round(row[4] or 0, 2)
                    })

        return comparison

    @staticmethod
    def generate_compliance_report() -> Dict[str, Any]:
        """Report showing data handling compliance status"""
        report = {
            'generated_at': datetime.now().isoformat(),
            'compliance_status': 'compliant',
            'findings': [],
            'integrations': []
        }

        with get_connection() as conn:
            cursor = conn.cursor()

            # Check for integrations without encryption
            cursor.execute('''
                SELECT ic.integration_name, ii.install_id
                FROM installed_integrations ii
                JOIN integration_catalog ic ON ii.integration_id = ic.integration_id
                WHERE ii.status = 'active'
                AND NOT EXISTS (
                    SELECT 1 FROM integration_credentials icr
                    WHERE icr.install_id = ii.install_id
                )
            ''')
            no_creds = cursor.fetchall()
            if no_creds:
                report['findings'].append({
                    'severity': 'warning',
                    'finding': f"{len(no_creds)} active integrations have no credentials configured",
                    'affected': [row[0] for row in no_creds]
                })

            # Check for old credentials
            cursor.execute('''
                SELECT ic.integration_name, icr.created_at
                FROM integration_credentials icr
                JOIN installed_integrations ii ON icr.install_id = ii.install_id
                JOIN integration_catalog ic ON ii.integration_id = ic.integration_id
                WHERE icr.created_at < date('now', '-90 days')
            ''')
            old_creds = cursor.fetchall()
            if old_creds:
                report['findings'].append({
                    'severity': 'info',
                    'finding': f"{len(old_creds)} integrations have credentials older than 90 days",
                    'recommendation': "Consider rotating credentials"
                })

            if any(f['severity'] == 'critical' for f in report['findings']):
                report['compliance_status'] = 'non-compliant'
            elif any(f['severity'] == 'warning' for f in report['findings']):
                report['compliance_status'] = 'needs-attention'

        return report


# =============================================================================
# CLI FUNCTIONS
# =============================================================================

def show_dashboard_overview():
    """Real-time dashboard with KPIs, charts, and status widgets"""
    print("\n" + "="*60)
    print("           INTEGRATION DASHBOARD")
    print("="*60)

    dashboard = ReportsDashboardManager.get_dashboard_overview()

    kpis = dashboard.get('kpis', {})
    print("\n--- KEY PERFORMANCE INDICATORS ---")
    print(f"  Available Integrations:  {kpis.get('total_available', 0)}")
    print(f"  Installed Integrations:  {kpis.get('total_installed', 0)}")
    print(f"  Enabled Integrations:    {kpis.get('total_enabled', 0)}")
    print(f"  Syncs (Last 24h):        {kpis.get('syncs_last_24h', 0)}")
    print(f"  Failed Syncs (24h):      {kpis.get('failed_syncs_24h', 0)}")

    status = dashboard.get('status_summary', {})
    if status:
        print("\n--- SYNC STATUS (Last 7 Days) ---")
        for s, count in status.items():
            bar = '*' * min(count, 20)
            print(f"  {s:12} {bar} ({count})")

    recent = dashboard.get('recent_activity', [])
    if recent:
        print("\n--- RECENT ACTIVITY ---")
        for activity in recent[:5]:
            print(f"  [{activity.get('sync_status', 'N/A'):8}] {activity.get('integration_name', 'N/A')} - {activity.get('sync_start_time', 'N/A')[:16]}")

    print(f"\nGenerated: {dashboard.get('generated_at', 'N/A')}")


def generate_health_report():
    """Comprehensive health report for all integrations"""
    print("\n" + "="*60)
    print("           INTEGRATION HEALTH REPORT")
    print("="*60)

    report = ReportsDashboardManager.generate_health_report()

    overall = report.get('overall_health', 'unknown')
    status_icon = {'healthy': '[OK]', 'warning': '[!]', 'critical': '[X]'}.get(overall, '[?]')
    print(f"\nOverall Status: {status_icon} {overall.upper()}")

    integrations = report.get('integrations', [])
    if integrations:
        print(f"\n--- INTEGRATION STATUS ({len(integrations)} total) ---")

        for status in ['critical', 'warning', 'disabled', 'healthy']:
            filtered = [i for i in integrations if i.get('health_status') == status]
            if filtered:
                icon = {'healthy': '[OK]', 'warning': '[!]', 'critical': '[X]', 'disabled': '[-]'}.get(status, '[?]')
                print(f"\n{icon} {status.upper()} ({len(filtered)}):")
                for integ in filtered:
                    print(f"    - {integ.get('integration_name')}")
                    for issue in integ.get('issues', []):
                        print(f"        {issue}")

    print(f"\nGenerated: {report.get('generated_at', 'N/A')}")


def show_error_analysis():
    """Analyze and categorize sync errors by type/frequency"""
    print("\n" + "="*60)
    print("           ERROR ANALYSIS")
    print("="*60)

    days = input("Analysis period in days (default 30): ").strip()
    days = int(days) if days.isdigit() else 30

    analysis = ReportsDashboardManager.get_error_analysis(days)

    print(f"\n--- SUMMARY ({analysis.get('period')}) ---")
    print(f"  Total Errors: {analysis.get('total_errors', 0)}")

    by_integration = analysis.get('error_by_integration', {})
    if by_integration:
        print("\n--- ERRORS BY INTEGRATION ---")
        for name, count in sorted(by_integration.items(), key=lambda x: -x[1])[:10]:
            bar = '*' * min(count, 20)
            print(f"  {name[:25]:25} {bar} ({count})")

    top_errors = analysis.get('top_error_messages', [])
    if top_errors:
        print("\n--- TOP ERROR MESSAGES ---")
        for i, err in enumerate(top_errors[:5], 1):
            msg = err.get('message', 'N/A')[:60]
            print(f"  {i}. [{err.get('count')}x] {msg}...")


def generate_usage_trend_chart():
    """Usage trend data visualization"""
    print("\n" + "="*60)
    print("           USAGE TRENDS")
    print("="*60)

    days = input("Trend period in days (default 30): ").strip()
    days = int(days) if days.isdigit() else 30

    trends = ReportsDashboardManager.get_usage_trends(days)

    daily_syncs = trends.get('daily_syncs', [])
    if daily_syncs:
        print(f"\n--- DAILY SYNC COUNT ({trends.get('period')}) ---")
        max_count = max(d.get('count', 0) for d in daily_syncs) or 1
        for day in daily_syncs[-14:]:  # Last 14 days
            count = day.get('count', 0)
            bar_len = int((count / max_count) * 30)
            bar = '*' * bar_len
            print(f"  {day.get('date', 'N/A')}: {bar} ({count})")

    daily_records = trends.get('daily_records', [])
    if daily_records:
        print("\n--- DAILY RECORDS SYNCED ---")
        max_records = max(d.get('records', 0) for d in daily_records) or 1
        for day in daily_records[-14:]:
            records = day.get('records', 0)
            bar_len = int((records / max_records) * 30) if max_records > 0 else 0
            bar = '*' * bar_len
            print(f"  {day.get('date', 'N/A')}: {bar} ({records})")


def show_api_call_statistics():
    """Statistics on API calls per integration"""
    print("\n" + "="*60)
    print("           API CALL STATISTICS")
    print("="*60)

    days = input("Statistics period in days (default 30): ").strip()
    days = int(days) if days.isdigit() else 30

    stats = ReportsDashboardManager.get_api_call_statistics(days)

    print(f"\n--- BY INTEGRATION ({stats.get('period')}) ---")
    print(f"{'Integration':<25} {'Total':>8} {'Success':>8} {'Failed':>8} {'Rate':>8} {'Avg Rec':>10}")
    print("-" * 75)

    for integ in stats.get('by_integration', []):
        print(f"{integ.get('integration_name', 'N/A')[:24]:<25} "
              f"{integ.get('total_syncs', 0):>8} "
              f"{integ.get('successful', 0):>8} "
              f"{integ.get('failed', 0):>8} "
              f"{integ.get('success_rate', 0):>7.1f}% "
              f"{integ.get('avg_records_per_sync', 0):>10.1f}")


def compare_integration_performance():
    """Side-by-side performance comparison"""
    print("\n" + "="*60)
    print("           PERFORMANCE COMPARISON")
    print("="*60)

    ids_input = input("Enter install IDs to compare (comma-separated): ").strip()
    if not ids_input:
        print("No IDs provided.")
        return

    try:
        install_ids = [int(x.strip()) for x in ids_input.split(',')]
    except ValueError:
        print("Invalid ID format.")
        return

    comparison = ReportsDashboardManager.compare_integration_performance(install_ids)

    integrations = comparison.get('integrations', [])
    if not integrations:
        print("\nNo data found for the specified integrations.")
        return

    print(f"\n{'Integration':<25} {'Syncs':>8} {'Success%':>10} {'Avg Rec':>10} {'Avg Time':>12}")
    print("-" * 70)

    for integ in integrations:
        print(f"{integ.get('integration_name', 'N/A')[:24]:<25} "
              f"{integ.get('total_syncs', 0):>8} "
              f"{integ.get('success_rate', 0):>9.1f}% "
              f"{integ.get('avg_records', 0):>10.1f} "
              f"{integ.get('avg_duration_seconds', 0):>10.2f}s")


def generate_compliance_report():
    """Report showing data handling compliance status"""
    print("\n" + "="*60)
    print("           COMPLIANCE REPORT")
    print("="*60)

    report = ReportsDashboardManager.generate_compliance_report()

    status = report.get('compliance_status', 'unknown')
    status_icon = {'compliant': '[OK]', 'needs-attention': '[!]', 'non-compliant': '[X]'}.get(status, '[?]')
    print(f"\nCompliance Status: {status_icon} {status.upper()}")

    findings = report.get('findings', [])
    if findings:
        print("\n--- FINDINGS ---")
        for finding in findings:
            severity = finding.get('severity', 'info').upper()
            icon = {'CRITICAL': '[X]', 'WARNING': '[!]', 'INFO': '[i]'}.get(severity, '[?]')
            print(f"\n{icon} {severity}: {finding.get('finding')}")
            if finding.get('affected'):
                print(f"   Affected: {', '.join(finding.get('affected')[:5])}")
            if finding.get('recommendation'):
                print(f"   Recommendation: {finding.get('recommendation')}")
    else:
        print("\nNo compliance issues found.")

    print(f"\nGenerated: {report.get('generated_at', 'N/A')}")
