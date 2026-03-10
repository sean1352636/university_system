from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch

from education_system.university_system.infrastructure.database.db import get_connection

from . import _common


def compliance_audit_system():
    """Compliance and audit trail system"""
    auth = _common.auth

    if not auth or not auth.current_user:
        print("You must be logged in to access compliance and audit system.")
        return

    if not auth.check_permission('manage_finances'):
        print("You don't have permission to access compliance and audit system.")
        return

    print("\nFinancial Compliance & Audit System")
    print("=" * 50)

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Create audit tables if they don't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_log (
            audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_name TEXT NOT NULL,
            operation TEXT NOT NULL,
            record_id TEXT,
            old_values TEXT,
            new_values TEXT,
            user_id TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS compliance_checks (
            check_id INTEGER PRIMARY KEY AUTOINCREMENT,
            check_type TEXT NOT NULL,
            check_date DATE,
            status TEXT,
            details TEXT,
            resolved BOOLEAN DEFAULT FALSE
        )
        ''')

        # Compliance checks
        compliance_results = []

        # Check 1: Data integrity
        cursor.execute('''
        SELECT COUNT(*) FROM student_fees sf
        LEFT JOIN students s ON sf.student_id = s.student_id
        WHERE s.student_id IS NULL
        ''')
        orphaned_fees = cursor.fetchone()[0]

        compliance_results.append({
            'check': 'Data Integrity - Orphaned Fee Records',
            'status': 'PASS' if orphaned_fees == 0 else 'FAIL',
            'details': f'{orphaned_fees} orphaned fee records found' if orphaned_fees > 0 else 'No orphaned records'
        })

        # Check 2: Payment reconciliation
        cursor.execute('''
        SELECT
            SUM(CASE WHEN sf.status = 'paid' THEN sf.amount ELSE 0 END) as fees_marked_paid,
            (SELECT SUM(amount) FROM payments) as total_payments
        FROM student_fees sf
        ''')

        reconciliation_data = cursor.fetchone()
        fees_marked_paid = reconciliation_data[0] or 0
        total_payments = reconciliation_data[1] or 0
        reconciliation_diff = abs(fees_marked_paid - total_payments)

        compliance_results.append({
            'check': 'Payment Reconciliation',
            'status': 'PASS' if reconciliation_diff < 100 else 'FAIL',
            'details': f'Difference: £{reconciliation_diff:.2f}' if reconciliation_diff >= 100 else 'Payments reconciled'
        })

        # Check 3: Fee structure compliance
        cursor.execute('''
        SELECT ft.fee_name, COUNT(DISTINCT sf.amount) as unique_amounts
        FROM student_fees sf
        JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
        GROUP BY ft.fee_name
        HAVING unique_amounts > 3
        ''')

        fee_variations = cursor.fetchall()

        compliance_results.append({
            'check': 'Fee Structure Consistency',
            'status': 'PASS' if len(fee_variations) == 0 else 'WARNING',
            'details': f'{len(fee_variations)} fee types with multiple amounts' if fee_variations else 'Fee structure consistent'
        })

        # Check 4: Late payment policy compliance
        cursor.execute('''
        SELECT COUNT(*) FROM student_fees sf
        WHERE sf.status != 'paid'
        AND sf.due_date < date('now', '-30 days')
        AND sf.student_id NOT IN (
            SELECT DISTINCT p.student_id FROM payments p
            WHERE p.payment_date > sf.due_date
        )
        ''')

        overdue_without_action = cursor.fetchone()[0]

        compliance_results.append({
            'check': 'Late Payment Policy Compliance',
            'status': 'PASS' if overdue_without_action < 10 else 'FAIL',
            'details': f'{overdue_without_action} overdue accounts without recent action'
        })

        # Display compliance results
        print("Compliance Check Results:")
        print("-" * 40)

        for result in compliance_results:
            status_symbol = "✓" if result['status'] == 'PASS' else "⚠" if result['status'] == 'WARNING' else "✗"
            print(f"{status_symbol} {result['check']}: {result['status']}")
            print(f"   {result['details']}")

        # Audit trail analysis - check if table exists first
        try:
            cursor.execute('''
            SELECT operation, COUNT(*) as count
            FROM audit_log
            WHERE timestamp >= date('now', '-30 days')
            GROUP BY operation
            ORDER BY count DESC
            ''')

            audit_activity = cursor.fetchall()

            if audit_activity:
                print("\nAudit Activity (Last 30 Days):")
                print("-" * 30)
                for operation, count in audit_activity:
                    print(f"{operation}: {count} operations")
        except Exception:
            print("\nAudit Activity: No audit log data available")

        # Generate compliance report
        export_compliance = input("\nGenerate compliance report? (y/n): ").strip().lower()

        if export_compliance == 'y':
            report_filename = f"Compliance_Report_{datetime.now().strftime('%Y%m%d')}.pdf"

            doc = SimpleDocTemplate(report_filename, pagesize=letter)
            styles = getSampleStyleSheet()
            elements = []

            # Title
            elements.append(Paragraph("Financial Compliance Report", styles['Title']))
            elements.append(Spacer(1, 0.25*inch))

            # Date
            elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
            elements.append(Spacer(1, 0.25*inch))

            # Compliance results table
            compliance_data = [['Check', 'Status', 'Details']]
            for result in compliance_results:
                compliance_data.append([result['check'], result['status'], result['details']])

            compliance_table = Table(compliance_data, colWidths=[3*inch, 1*inch, 2.5*inch])
            compliance_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))

            elements.append(compliance_table)
            elements.append(Spacer(1, 0.5*inch))

            # Summary
            pass_count = sum(1 for r in compliance_results if r['status'] == 'PASS')
            total_checks = len(compliance_results)

            elements.append(Paragraph("Compliance Summary", styles['Heading2']))
            elements.append(Paragraph(f"Passed: {pass_count}/{total_checks} checks", styles['Normal']))

            if pass_count == total_checks:
                elements.append(Paragraph("Status: COMPLIANT", styles['Normal']))
            else:
                elements.append(Paragraph("Status: ACTION REQUIRED", styles['Normal']))

            doc.build(elements)
            print(f"Compliance report exported to {report_filename}")

        conn.commit()
        conn.close()

    except Exception as e:
        print(f"Error in compliance audit system: {e}")
