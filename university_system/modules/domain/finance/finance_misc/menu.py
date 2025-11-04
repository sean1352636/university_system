from __future__ import annotations

import logging

from university_system.modules.domain.finance.finance_misc.finance_context import auth
from university_system.modules.domain.finance.finance_misc.finance_db_operations import initialize_finance

def display_enhanced_finance_menu():
    """Display the enhanced finance management menu"""
    global auth

    # Initialize system if not already done
    if not auth:
        initialize_finance()

    while True:
        print("\n" + "=" * 60)
        print("ENHANCED FINANCE MANAGEMENT SYSTEM")
        print("=" * 60)

        # Core Finance Operations
        print("\n📊 CORE FINANCE OPERATIONS:")
        if auth.check_permission('manage_finances'):
            print("1.  Assign Fees to Student")
            print("2.  Record Payment")
            print("3.  Generate Invoice")
            print("4.  Process Refund")
            print("5.  Manage Student Credits")

        print("6.  View Student Financial Statement")

        # Payment Plans
        print("\n💳 PAYMENT PLANS:")
        if auth.check_permission('manage_finances'):
            print("7.  Manage Payment Plans")
            print("8.  Process Payment Plan Payment")

        # Late Fees and Penalties
        print("\n⚠️  LATE FEES & PENALTIES:")
        if auth.check_permission('manage_finances'):
            print("9.  Calculate Late Fees")
            print("10. Waive Late Fee")

        # Multi-Currency
        print("\n🌍 MULTI-CURRENCY:")
        if auth.check_permission('manage_finances'):
            print("11. Update Exchange Rates")
            print("12. Currency Conversion Tool")

        # Analytics and Reporting
        print("\n📈 ANALYTICS & REPORTING:")
        if auth.check_permission('manage_finances'):
            print("13. Generate Financial Dashboard")
            print("14. Predictive Analytics")
            print("15. Generate Financial Reports")
            print("16. Outstanding Fees Report")
            print("17. Payment Collection Report")

        # Scholarships and Financial Aid
        print("\n🎓 SCHOLARSHIPS & FINANCIAL AID:")
        if auth.check_permission('manage_finances'):
            print("18. Manage Scholarships")
            print("19. Manage Financial Aid")

        # Security and Compliance
        print("\n🔒 SECURITY & COMPLIANCE:")
        if auth.check_permission('manage_finances'):
            print("20. Run Fraud Detection")
            print("21. Generate Audit Report")
            print("22. Manage Workflows")

        # Automation
        print("\n🤖 AUTOMATION:")
        if auth.check_permission('manage_finances'):
            print("23. Setup Automated Notifications")
            print("24. Send Automated Notifications")

        # Budgeting
        print("\n💼 BUDGETING & FORECASTING:")
        if auth.check_permission('manage_finances'):
            print("25. Budget Management")
            print("26. Revenue Forecasting")

        # Collection Management
        print("\n📞 COLLECTION MANAGEMENT:")
        if auth.check_permission('manage_finances'):
            print("27. Collection Management")

        print("\n28. Initialize System (Reset)")
        print("29. Exit")
        print("=" * 60)

        choice = input("Enter your choice: ").strip()

        try:
            # Core Finance Operations
            if choice == '1' and auth.check_permission('manage_finances'):
                from university_system.modules.domain.finance.core.account_management import assign_fees_to_student
                assign_fees_to_student()
            elif choice == '2' and auth.check_permission('manage_finances'):
                from university_system.modules.domain.finance.core.account_management import record_payment
                record_payment()
            elif choice == '3' and auth.check_permission('manage_finances'):
                from university_system.modules.domain.finance.core.account_management import generate_invoice
                generate_invoice()
            elif choice == '4' and auth.check_permission('manage_finances'):
                from university_system.modules.domain.finance.core.account_management import process_refund
                process_refund()
            elif choice == '5' and auth.check_permission('manage_finances'):
                from university_system.modules.domain.finance.core.account_management import manage_student_credits
                manage_student_credits()
            elif choice == '6':
                from university_system.modules.domain.finance.core.account_management import view_student_financial_statement
                view_student_financial_statement()

            # Payment Plans
            elif choice == '7' and auth.check_permission('manage_finances'):
                from university_system.modules.domain.finance.billing.payment_plans import manage_payment_plans
                manage_payment_plans()
            elif choice == '8' and auth.check_permission('manage_finances'):
                from university_system.modules.domain.finance.billing.payment_plans import process_payment_plan_payment
                process_payment_plan_payment()

            # Late Fees
            elif choice == '9' and auth.check_permission('manage_finances'):
                from university_system.modules.domain.finance.billing.fee_structure import calculate_late_fees
                calculate_late_fees()
            elif choice == '10' and auth.check_permission('manage_finances'):
                from university_system.modules.domain.finance.billing.fee_structure import waive_late_fee
                waive_late_fee()

            # Multi-Currency
            elif choice == '11' and auth.check_permission('manage_finances'):
                from university_system.modules.domain.finance.billing.fee_structure import update_exchange_rates
                update_exchange_rates()
            elif choice == '12' and auth.check_permission('manage_finances'):
                from university_system.modules.domain.finance.billing.fee_structure import currency_conversion_tool
                currency_conversion_tool()

            # Analytics
            elif choice == '13' and auth.check_permission('manage_finances'):
                from university_system.modules.domain.finance.reporting.revenue_analytics import generate_financial_dashboard
                generate_financial_dashboard()
            elif choice == '14' and auth.check_permission('manage_finances'):
                from university_system.modules.domain.finance.reporting.revenue_analytics import generate_predictive_analytics
                generate_predictive_analytics()
            elif choice == '15' and auth.check_permission('manage_finances'):
                from university_system.modules.domain.finance.reporting.revenue_analytics import generate_financial_reports
                generate_financial_reports()
            elif choice == '16' and auth.check_permission('manage_finances'):
                from university_system.modules.domain.finance.reporting.revenue_analytics import generate_outstanding_fees_report
                generate_outstanding_fees_report()
            elif choice == '17' and auth.check_permission('manage_finances'):
                from university_system.modules.domain.finance.reporting.revenue_analytics import generate_payment_collection_report
                generate_payment_collection_report()

            # Scholarships
            elif choice == '18' and auth.check_permission('manage_finances'):
                from university_system.modules.domain.finance.scholarships.scholarship_programs import manage_scholarships
                manage_scholarships()
            elif choice == '19' and auth.check_permission('manage_finances'):
                from university_system.modules.domain.finance.scholarships.scholarship_programs import manage_financial_aid
                manage_financial_aid()

            # Security
            elif choice == '20' and auth.check_permission('manage_finances'):
                from university_system.modules.domain.finance.core.security_automation import detect_payment_fraud
                detect_payment_fraud()
            elif choice == '21' and auth.check_permission('view_audit_logs'):
                from university_system.modules.domain.finance.reporting.revenue_analytics import generate_audit_report
                start_date = input("Enter start date (YYYY-MM-DD): ").strip()
                end_date = input("Enter end date (YYYY-MM-DD): ").strip()
                generate_audit_report(start_date, end_date)
            elif choice == '22' and auth.check_permission('manage_workflows'):
                from university_system.modules.domain.finance.core.security_automation import create_approval_workflow
                create_approval_workflow()

            # Automation
            elif choice == '23' and auth.check_permission('manage_finances'):
                from university_system.modules.domain.finance.core.security_automation import setup_automated_notifications
                setup_automated_notifications()
            elif choice == '24' and auth.check_permission('manage_finances'):
                from university_system.modules.domain.finance.core.security_automation import send_automated_notifications
                notifications_sent = send_automated_notifications()
                print(f"Sent {notifications_sent} notifications")

            # Budgeting
            elif choice == '25' and auth.check_permission('manage_finances'):
                from university_system.modules.domain.finance.reporting.budget_analysis import manage_budgets
                manage_budgets()
            elif choice == '26' and auth.check_permission('manage_finances'):
                from university_system.modules.domain.finance.reporting.revenue_analytics import generate_revenue_forecast
                generate_revenue_forecast()

            # Collection
            elif choice == '27' and auth.check_permission('manage_finances'):
                from university_system.modules.domain.finance.reporting.revenue_analytics import manage_collections
                manage_collections()

            elif choice == '28':
                initialize_finance()
            elif choice == '29':
                print("Goodbye!")
                return
            else:
                print("Invalid choice or insufficient permissions. Please try again.")

        except Exception as e:
            print(f"An error occurred: {e}")
            logging.error(f"Finance menu error: {e}")
