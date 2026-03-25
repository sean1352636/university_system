"""Cross-system analytics CLI module.

Provides a text-based menu for viewing cross-system analytics:
summary, transfer rates, retention stats, year trends, and CSV export.
"""

import os
from education_system.shared.analytics.analytics_service import (
    AnalyticsService,
    SYSTEM_LABELS,
)


def run(db_path=None, auth=None):
    """Run the cross-system analytics CLI menu loop."""
    service = AnalyticsService()

    while True:
        print("\n" + "=" * 60)
        print("  Cross-System Analytics Dashboard")
        print("=" * 60)
        print("  1) View summary")
        print("  2) Transfer rates")
        print("  3) Retention stats")
        print("  4) Year trends")
        print("  5) Export to CSV")
        print("  0) Back")
        print("-" * 60)

        choice = input("Select option: ").strip()

        if choice == "1":
            _show_summary(service)
        elif choice == "2":
            _show_transfer_rates(service)
        elif choice == "3":
            _show_retention(service)
        elif choice == "4":
            _show_trends(service)
        elif choice == "5":
            _export_csv(service)
        elif choice == "0":
            break
        else:
            print("Invalid option. Please try again.")


def _show_summary(service):
    """Display the overall summary."""
    try:
        summary = service.get_summary()
    except Exception as exc:
        print(f"Error loading summary: {exc}")
        return

    print("\n--- Cross-System Summary ---")
    print(f"  Total Students:    {summary['total_students']}")
    print(f"  Active Students:   {summary['total_active']}")
    print(f"  Total Transfers:   {summary['total_transferred']}")
    print(f"  Total Graduated:   {summary['total_graduated']}")
    print()
    print(f"  {'System':<25} {'Total':>8} {'Active':>8} {'Transferred':>12} {'Graduated':>10}")
    print("  " + "-" * 65)
    for s in summary["systems"]:
        print(f"  {s['label']:<25} {s['total']:>8} {s['active']:>8} "
              f"{s['transferred']:>12} {s['graduated']:>10}")


def _show_transfer_rates(service):
    """Display transfer rate data."""
    try:
        transfers = service.get_transfer_rates()
    except Exception as exc:
        print(f"Error loading transfer rates: {exc}")
        return

    print("\n--- Transfer Rates ---")
    if not transfers:
        print("  No transfer data found.")
        return

    print(f"  {'Source':<22} {'Destination':<22} {'Count':>8} {'Rate':>8}")
    print("  " + "-" * 62)
    for t in transfers:
        src = SYSTEM_LABELS.get(t["source_system"], t["source_system"])
        dst = SYSTEM_LABELS.get(t["destination_system"], t["destination_system"])
        print(f"  {src:<22} {dst:<22} {t['count']:>8} {t['rate_pct']:>7.1f}%")


def _show_retention(service):
    """Display retention statistics."""
    try:
        retention = service.get_retention_stats()
    except Exception as exc:
        print(f"Error loading retention stats: {exc}")
        return

    print("\n--- Retention Statistics ---")
    print(f"  {'System':<22} {'Total':>7} {'Active':>7} {'Retained':>9} "
          f"{'Dropped':>8} {'Dropout':>8}")
    print("  " + "-" * 65)
    for r in retention:
        print(f"  {r['label']:<22} {r['total']:>7} {r['active']:>7} "
              f"{r['retained_pct']:>8.1f}% {r['dropped_out']:>8} "
              f"{r['dropout_pct']:>7.1f}%")


def _show_trends(service):
    """Display year-over-year trends."""
    try:
        trends = service.get_year_trends()
    except Exception as exc:
        print(f"Error loading trends: {exc}")
        return

    print("\n--- Year-over-Year Trends ---")
    if not trends:
        print("  No trend data available.")
        return

    print(f"  {'System':<25} {'Year':>6} {'Students':>10}")
    print("  " + "-" * 45)
    for t in trends:
        print(f"  {t['label']:<25} {t['year']:>6} {t['student_count']:>10}")


def _export_csv(service):
    """Export analytics data to a CSV file."""
    default_name = "cross_system_analytics.csv"
    path = input(f"Enter file path [{default_name}]: ").strip()
    if not path:
        path = default_name

    try:
        csv_data = service.export_summary_csv()
        with open(path, "w", newline="", encoding="utf-8") as f:
            f.write(csv_data)
        print(f"Analytics exported to: {os.path.abspath(path)}")
    except Exception as exc:
        print(f"Error exporting CSV: {exc}")


if __name__ == "__main__":
    run()
