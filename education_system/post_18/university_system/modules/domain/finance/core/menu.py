from __future__ import annotations

import logging

from education_system.post_18.university_system.modules.domain.finance.core.finance_context import get_auth
from education_system.post_18.university_system.modules.domain.finance.core.finance_db_operations import initialize_finance
from education_system.post_18.university_system.core.i18n import get_text

def display_enhanced_finance_menu():
    """Display the enhanced finance management menu"""
    # Get current auth instance
    auth = get_auth()

    # Initialize system if not already done (check if auth is properly configured)
    if not auth or not hasattr(auth, 'check_permission'):
        initialize_finance()
        auth = get_auth()

    while True:
        print("\n" + "=" * 60)
        print(get_text("finance.menu.title"))
        print("=" * 60)

        # Core Finance Operations
        print("\n" + get_text("finance.menu.section_core"))
        if auth.check_permission('manage_finances'):
            print(get_text("finance.menu.option_1"))
            print(get_text("finance.menu.option_2"))
            print(get_text("finance.menu.option_3"))
            print(get_text("finance.menu.option_4"))
            print(get_text("finance.menu.option_5"))

        print(get_text("finance.menu.option_6"))

        # Payment Plans
        print("\n" + get_text("finance.menu.section_payment_plans"))
        if auth.check_permission('manage_finances'):
            print(get_text("finance.menu.option_7"))
            print(get_text("finance.menu.option_8"))

        # Late Fees and Penalties
        print("\n" + get_text("finance.menu.section_late_fees"))
        if auth.check_permission('manage_finances'):
            print(get_text("finance.menu.option_9"))
            print(get_text("finance.menu.option_10"))

        # Multi-Currency
        print("\n" + get_text("finance.menu.section_multi_currency"))
        if auth.check_permission('manage_finances'):
            print(get_text("finance.menu.option_11"))
            print(get_text("finance.menu.option_12"))

        # Analytics and Reporting
        print("\n" + get_text("finance.menu.section_analytics"))
        if auth.check_permission('manage_finances'):
            print(get_text("finance.menu.option_13"))
            print(get_text("finance.menu.option_14"))
            print(get_text("finance.menu.option_15"))
            print(get_text("finance.menu.option_16"))
            print(get_text("finance.menu.option_17"))

        # Scholarships and Financial Aid
        print("\n" + get_text("finance.menu.section_scholarships"))
        if auth.check_permission('manage_finances'):
            print(get_text("finance.menu.option_18"))
            print(get_text("finance.menu.option_19"))

        # Security and Compliance
        print("\n" + get_text("finance.menu.section_security"))
        if auth.check_permission('manage_finances'):
            print(get_text("finance.menu.option_20"))
            print(get_text("finance.menu.option_21"))
            print(get_text("finance.menu.option_22"))

        # Automation
        print("\n" + get_text("finance.menu.section_automation"))
        if auth.check_permission('manage_finances'):
            print(get_text("finance.menu.option_23"))
            print(get_text("finance.menu.option_24"))

        # Budgeting
        print("\n" + get_text("finance.menu.section_budgeting"))
        if auth.check_permission('manage_finances'):
            print(get_text("finance.menu.option_25"))
            print(get_text("finance.menu.option_26"))

        # Collection Management
        print("\n" + get_text("finance.menu.section_collection"))
        if auth.check_permission('manage_finances'):
            print(get_text("finance.menu.option_27"))

        print("\n" + get_text("finance.menu.option_28"))
        print(get_text("finance.menu.option_29"))
        print("=" * 60)

        choice = input(get_text("finance.menu.enter_choice")).strip()

        try:
            # Core Finance Operations
            if choice == '1' and auth.check_permission('manage_finances'):
                from education_system.post_18.university_system.modules.domain.finance.core.account_management import assign_fees_to_student
                assign_fees_to_student()
            elif choice == '2' and auth.check_permission('manage_finances'):
                from education_system.post_18.university_system.modules.domain.finance.core.account_management import record_payment
                record_payment()
            elif choice == '3' and auth.check_permission('manage_finances'):
                from education_system.post_18.university_system.modules.domain.finance.core.account_management import generate_invoice
                generate_invoice()
            elif choice == '4' and auth.check_permission('manage_finances'):
                from education_system.post_18.university_system.modules.domain.finance.core.account_management import process_refund
                process_refund()
            elif choice == '5' and auth.check_permission('manage_finances'):
                from education_system.post_18.university_system.modules.domain.finance.core.account_management import manage_student_credits
                manage_student_credits()
            elif choice == '6':
                from education_system.post_18.university_system.modules.domain.finance.core.account_management import view_student_financial_statement
                view_student_financial_statement()

            # Payment Plans
            elif choice == '7' and auth.check_permission('manage_finances'):
                from education_system.post_18.university_system.modules.domain.finance.billing.payment_plans import manage_payment_plans
                manage_payment_plans()
            elif choice == '8' and auth.check_permission('manage_finances'):
                from education_system.post_18.university_system.modules.domain.finance.billing.payment_plans import process_payment_plan_payment
                process_payment_plan_payment()

            # Late Fees
            elif choice == '9' and auth.check_permission('manage_finances'):
                from education_system.post_18.university_system.modules.domain.finance.billing.fee_structure import calculate_late_fees
                calculate_late_fees()
            elif choice == '10' and auth.check_permission('manage_finances'):
                from education_system.post_18.university_system.modules.domain.finance.billing.fee_structure import waive_late_fee
                waive_late_fee()

            # Multi-Currency
            elif choice == '11' and auth.check_permission('manage_finances'):
                from education_system.post_18.university_system.modules.domain.finance.billing.fee_structure import update_exchange_rates
                update_exchange_rates()
            elif choice == '12' and auth.check_permission('manage_finances'):
                from education_system.post_18.university_system.modules.domain.finance.billing.fee_structure import currency_conversion_tool
                currency_conversion_tool()

            # Analytics
            elif choice == '13' and auth.check_permission('manage_finances'):
                from education_system.post_18.university_system.modules.domain.finance.reporting.revenue_analytics import generate_financial_dashboard
                generate_financial_dashboard()
            elif choice == '14' and auth.check_permission('manage_finances'):
                from education_system.post_18.university_system.modules.domain.finance.reporting.revenue_analytics import generate_predictive_analytics
                generate_predictive_analytics()
            elif choice == '15' and auth.check_permission('manage_finances'):
                from education_system.post_18.university_system.modules.domain.finance.reporting.revenue_analytics import generate_financial_reports
                generate_financial_reports()
            elif choice == '16' and auth.check_permission('manage_finances'):
                from education_system.post_18.university_system.modules.domain.finance.reporting.revenue_analytics import generate_outstanding_fees_report
                generate_outstanding_fees_report()
            elif choice == '17' and auth.check_permission('manage_finances'):
                from education_system.post_18.university_system.modules.domain.finance.reporting.revenue_analytics import generate_payment_collection_report
                generate_payment_collection_report()

            # Scholarships
            elif choice == '18' and auth.check_permission('manage_finances'):
                from education_system.post_18.university_system.modules.domain.finance.scholarships.scholarship_programs import manage_scholarships
                manage_scholarships()
            elif choice == '19' and auth.check_permission('manage_finances'):
                from education_system.post_18.university_system.modules.domain.finance.scholarships.scholarship_programs import manage_financial_aid
                manage_financial_aid()

            # Security
            elif choice == '20' and auth.check_permission('manage_finances'):
                from education_system.post_18.university_system.modules.domain.finance.core.security_automation import detect_payment_fraud
                detect_payment_fraud()
            elif choice == '21' and auth.check_permission('view_audit_logs'):
                from education_system.post_18.university_system.modules.domain.finance.reporting.revenue_analytics import generate_audit_report
                start_date = input(get_text("finance.menu.enter_start_date")).strip()
                end_date = input(get_text("finance.menu.enter_end_date")).strip()
                generate_audit_report(start_date, end_date)
            elif choice == '22' and auth.check_permission('manage_workflows'):
                from education_system.post_18.university_system.modules.domain.finance.core.security_automation import create_approval_workflow
                create_approval_workflow()

            # Automation
            elif choice == '23' and auth.check_permission('manage_finances'):
                from education_system.post_18.university_system.modules.domain.finance.core.security_automation import setup_automated_notifications
                setup_automated_notifications()
            elif choice == '24' and auth.check_permission('manage_finances'):
                from education_system.post_18.university_system.modules.domain.finance.core.security_automation import send_automated_notifications
                notifications_sent = send_automated_notifications()
                print(get_text("finance.menu.notifications_sent", count=notifications_sent))

            # Budgeting
            elif choice == '25' and auth.check_permission('manage_finances'):
                from education_system.post_18.university_system.modules.domain.finance.reporting.budget_analysis import manage_budgets
                manage_budgets()
            elif choice == '26' and auth.check_permission('manage_finances'):
                from education_system.post_18.university_system.modules.domain.finance.reporting.revenue_analytics import generate_revenue_forecast
                generate_revenue_forecast()

            # Collection
            elif choice == '27' and auth.check_permission('manage_finances'):
                from education_system.post_18.university_system.modules.domain.finance.reporting.revenue_analytics import manage_collections
                manage_collections()

            elif choice == '28':
                initialize_finance()
            elif choice == '29':
                print(get_text("finance.menu.goodbye"))
                return
            else:
                print(get_text("finance.menu.invalid_choice"))

        except Exception as e:
            print(get_text("finance.menu.error_occurred", error=e))
            logging.error(f"Finance menu error: {e}")
