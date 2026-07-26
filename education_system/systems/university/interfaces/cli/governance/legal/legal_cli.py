"""
Legal Services CLI Interface

Command-line interface for legal services management including
cases, consultations, documents, payments, and reporting.
"""

from datetime import datetime

from education_system.systems.university.domain.governance.legal.services.legal_services_core import (
    init_legal_services_db,
    CaseManager,
    ConsultationManager,
    DocumentManager,
    PaymentManager,
    calculate_service_fee,
    generate_invoice_text,
    CASE_TYPES,
    CASE_STATUSES,
    SERVICE_FEES,
    CONSULTATION_STATUSES,
)


def display_menu():
    """Display the legal services menu and handle user input."""
    init_legal_services_db()

    while True:
        print("\n" + "=" * 70)
        print(" " * 20 + "LEGAL SERVICES MANAGEMENT")
        print("=" * 70)

        print("\n[Cases]")
        print("1.  Create Case")
        print("2.  View Case")
        print("3.  Search/List Cases")
        print("4.  Update Case")
        print("5.  Close Case")
        print("6.  Case Statistics")

        print("\n[Consultations]")
        print("7.  Schedule Consultation")
        print("8.  View Consultation")
        print("9.  List Consultations")
        print("10. Update Consultation")
        print("11. Cancel Consultation")
        print("12. Upcoming Consultations")

        print("\n[Documents]")
        print("13. Create Document")
        print("14. View Document")
        print("15. List Case Documents")
        print("16. View Document History")

        print("\n[Payments]")
        print("17. Record Payment")
        print("18. View Payment")
        print("19. List Payments")
        print("20. Process Refund")
        print("21. Revenue Statistics")

        print("\n[Tools]")
        print("22. Calculate Service Fee")
        print("23. Generate Invoice")

        print("\n0.  Back to Main Menu")
        print("=" * 70)

        choice = input("\nEnter your choice: ").strip()

        try:
            if choice == "0":
                break
            elif choice == "1":
                _create_case()
            elif choice == "2":
                _view_case()
            elif choice == "3":
                _list_cases()
            elif choice == "4":
                _update_case()
            elif choice == "5":
                _close_case()
            elif choice == "6":
                _case_statistics()
            elif choice == "7":
                _schedule_consultation()
            elif choice == "8":
                _view_consultation()
            elif choice == "9":
                _list_consultations()
            elif choice == "10":
                _update_consultation()
            elif choice == "11":
                _cancel_consultation()
            elif choice == "12":
                _upcoming_consultations()
            elif choice == "13":
                _create_document()
            elif choice == "14":
                _view_document()
            elif choice == "15":
                _list_case_documents()
            elif choice == "16":
                _view_document_history()
            elif choice == "17":
                _record_payment()
            elif choice == "18":
                _view_payment()
            elif choice == "19":
                _list_payments()
            elif choice == "20":
                _process_refund()
            elif choice == "21":
                _revenue_statistics()
            elif choice == "22":
                _calculate_fee()
            elif choice == "23":
                _generate_invoice()
            else:
                print("Invalid choice. Please try again.")
        except Exception as e:
            print(f"\nError: {e}")


def _create_case():
    """Create a new legal case."""
    print("\n--- Create Case ---")
    client_id = input("Client ID: ").strip()
    client_name = input("Client name: ").strip()
    client_email = input("Client email: ").strip()

    print(f"Case types: {', '.join(CASE_TYPES)}")
    case_type = input("Case type: ").strip()
    if case_type not in CASE_TYPES:
        print("Invalid case type.")
        return

    case_title = input("Case title: ").strip()
    case_description = input("Case description (optional): ").strip() or ""
    priority = input("Priority (low/normal/high/urgent, default normal): ").strip() or "normal"
    assigned_lawyer = input("Assigned lawyer (optional): ").strip() or None

    case_id = CaseManager.create_case(
        client_id, client_name, client_email,
        case_type, case_title, case_description,
        priority, assigned_lawyer,
    )
    if case_id:
        print(f"Case created successfully. Case ID: {case_id}")
    else:
        print("Failed to create case.")


def _view_case():
    """View case details."""
    print("\n--- View Case ---")
    print("Search by: 1) Case ID  2) Case Number")
    search_by = input("Choice: ").strip()

    case = None
    if search_by == "1":
        case_id = int(input("Case ID: ").strip())
        case = CaseManager.get_case(case_id)
    elif search_by == "2":
        case_number = input("Case number: ").strip()
        case = CaseManager.get_case_by_number(case_number)
    else:
        print("Invalid choice.")
        return

    if not case:
        print("Case not found.")
        return

    print(f"\n  Case ID:       {case['case_id']}")
    print(f"  Case Number:   {case['case_number']}")
    print(f"  Client:        {case['client_name']} ({case['client_id']})")
    print(f"  Email:         {case.get('client_email', 'N/A')}")
    print(f"  Type:          {case['case_type']}")
    print(f"  Title:         {case['case_title']}")
    print(f"  Description:   {case.get('case_description', 'N/A')}")
    print(f"  Status:        {case['status']}")
    print(f"  Priority:      {case.get('priority', 'N/A')}")
    print(f"  Lawyer:        {case.get('assigned_lawyer', 'Unassigned')}")
    print(f"  Total Fees:    GBP {case.get('total_fees', 0):.2f}")
    print(f"  Amount Paid:   GBP {case.get('amount_paid', 0):.2f}")
    print(f"  Created:       {case.get('created_at', 'N/A')}")
    if case.get('closed_at'):
        print(f"  Closed:        {case['closed_at']}")


def _list_cases():
    """List/search cases."""
    print("\n--- List/Search Cases ---")
    print(f"Statuses: {', '.join(CASE_STATUSES)}")
    status = input("Filter by status (Enter for all): ").strip() or None
    print(f"Types: {', '.join(CASE_TYPES)}")
    case_type = input("Filter by type (Enter for all): ").strip() or None
    search = input("Search term (Enter to skip): ").strip() or None

    filters = {}
    if status:
        filters['status'] = status
    if case_type:
        filters['case_type'] = case_type
    if search:
        filters['search'] = search

    cases = CaseManager.get_all_cases(filters if filters else None)
    if not cases:
        print("No cases found.")
        return

    print(f"\n{'ID':<6}{'Case #':<22}{'Client':<18}{'Type':<18}{'Status':<14}{'Priority':<10}")
    print("-" * 88)
    for c in cases:
        print(
            f"{c['case_id']:<6}{c['case_number']:<22}{c['client_name']:<18}"
            f"{c['case_type']:<18}{c['status']:<14}{c.get('priority', 'N/A'):<10}"
        )


def _update_case():
    """Update a case."""
    print("\n--- Update Case ---")
    case_id = int(input("Case ID: ").strip())

    case = CaseManager.get_case(case_id)
    if not case:
        print("Case not found.")
        return

    print(f"Current: {case['case_title']} | Status: {case['status']} | Priority: {case.get('priority')}")
    print("Press Enter to keep current value.")

    updates = {}
    status = input(f"Status [{case['status']}] ({', '.join(CASE_STATUSES)}): ").strip()
    if status:
        updates['status'] = status
    priority = input(f"Priority [{case.get('priority', 'normal')}]: ").strip()
    if priority:
        updates['priority'] = priority
    lawyer = input(f"Assigned lawyer [{case.get('assigned_lawyer', 'None')}]: ").strip()
    if lawyer:
        updates['assigned_lawyer'] = lawyer
    total_fees = input(f"Total fees [{case.get('total_fees', 0)}]: ").strip()
    if total_fees:
        updates['total_fees'] = float(total_fees)

    if updates:
        if CaseManager.update_case(case_id, **updates):
            print("Case updated successfully.")
        else:
            print("Failed to update case.")
    else:
        print("No changes made.")


def _close_case():
    """Close a case."""
    print("\n--- Close Case ---")
    case_id = int(input("Case ID: ").strip())
    confirm = input("Are you sure you want to close this case? (y/n): ").strip().lower()
    if confirm != "y":
        print("Cancelled.")
        return

    if CaseManager.close_case(case_id):
        print("Case closed successfully.")
    else:
        print("Failed to close case.")


def _case_statistics():
    """Display case statistics."""
    print("\n--- Case Statistics ---")
    stats = CaseManager.get_case_statistics()
    if not stats:
        print("No data available.")
        return

    print(f"  Total Cases:       {stats.get('total_cases', 0)}")
    print(f"  Cases This Month:  {stats.get('cases_this_month', 0)}")
    print(f"  Total Fees:        GBP {stats.get('total_fees', 0):.2f}")
    print(f"  Total Paid:        GBP {stats.get('total_paid', 0):.2f}")

    print("\n  By Status:")
    for status, count in stats.get('by_status', {}).items():
        print(f"    {status}: {count}")

    print("\n  By Type:")
    for ctype, count in stats.get('by_type', {}).items():
        print(f"    {ctype}: {count}")


def _schedule_consultation():
    """Schedule a consultation."""
    print("\n--- Schedule Consultation ---")
    client_id = input("Client ID: ").strip()
    client_name = input("Client name: ").strip()
    client_email = input("Client email: ").strip()

    print("Consultation types: consultation, immigration, ip_patent, criminal,")
    print("  family_law, pro_bono, tenant_dispute, employment, consumer_rights")
    consultation_type = input("Consultation type: ").strip()

    scheduled_date = input("Date (YYYY-MM-DD): ").strip()
    scheduled_time = input("Time (HH:MM): ").strip()

    duration_str = input("Duration in minutes (default 30): ").strip()
    duration = int(duration_str) if duration_str else 30

    lawyer_name = input("Lawyer name (optional): ").strip() or None
    case_id_str = input("Associated case ID (optional): ").strip()
    case_id = int(case_id_str) if case_id_str else None
    notes = input("Notes (optional): ").strip() or ""

    consultation_id = ConsultationManager.schedule_consultation(
        client_id, client_name, client_email,
        consultation_type, scheduled_date, scheduled_time,
        duration, lawyer_name, case_id, notes,
    )
    if consultation_id:
        print(f"Consultation scheduled. ID: {consultation_id}")
    else:
        print("Failed to schedule consultation.")


def _view_consultation():
    """View consultation details."""
    print("\n--- View Consultation ---")
    consultation_id = int(input("Consultation ID: ").strip())

    consultation = ConsultationManager.get_consultation(consultation_id)
    if not consultation:
        print("Consultation not found.")
        return

    print(f"\n  Consultation ID:  {consultation['consultation_id']}")
    print(f"  Client:           {consultation['client_name']} ({consultation['client_id']})")
    print(f"  Type:             {consultation['consultation_type']}")
    print(f"  Date/Time:        {consultation['scheduled_date']} {consultation['scheduled_time']}")
    print(f"  Duration:         {consultation['duration_minutes']} minutes")
    print(f"  Lawyer:           {consultation.get('lawyer_name', 'Unassigned')}")
    print(f"  Fee:              GBP {consultation.get('fee', 0):.2f}")
    print(f"  Payment Status:   {consultation.get('payment_status', 'N/A')}")
    print(f"  Status:           {consultation['status']}")
    if consultation.get('case_id'):
        print(f"  Case ID:          {consultation['case_id']}")
    if consultation.get('notes'):
        print(f"  Notes:            {consultation['notes']}")


def _list_consultations():
    """List consultations."""
    print("\n--- List Consultations ---")
    print(f"Statuses: {', '.join(CONSULTATION_STATUSES)}")
    status = input("Filter by status (Enter for all): ").strip() or None
    client_id = input("Filter by client ID (Enter for all): ").strip() or None

    filters = {}
    if status:
        filters['status'] = status
    if client_id:
        filters['client_id'] = client_id

    consultations = ConsultationManager.get_all_consultations(filters if filters else None)
    if not consultations:
        print("No consultations found.")
        return

    print(f"\n{'ID':<6}{'Client':<18}{'Type':<18}{'Date':<12}{'Time':<8}{'Status':<12}{'Fee':<10}")
    print("-" * 84)
    for c in consultations:
        print(
            f"{c['consultation_id']:<6}{c['client_name']:<18}{c['consultation_type']:<18}"
            f"{c['scheduled_date']:<12}{c['scheduled_time']:<8}{c['status']:<12}"
            f"GBP {c.get('fee', 0):.2f}"
        )


def _update_consultation():
    """Update a consultation."""
    print("\n--- Update Consultation ---")
    consultation_id = int(input("Consultation ID: ").strip())

    consultation = ConsultationManager.get_consultation(consultation_id)
    if not consultation:
        print("Consultation not found.")
        return

    print("Press Enter to keep current value.")
    updates = {}
    status = input(f"Status [{consultation['status']}] ({', '.join(CONSULTATION_STATUSES)}): ").strip()
    if status:
        updates['status'] = status
    lawyer = input(f"Lawyer [{consultation.get('lawyer_name', 'None')}]: ").strip()
    if lawyer:
        updates['lawyer_name'] = lawyer
    notes = input("Add notes (optional): ").strip()
    if notes:
        updates['notes'] = notes

    if updates:
        if ConsultationManager.update_consultation(consultation_id, **updates):
            print("Consultation updated successfully.")
        else:
            print("Failed to update consultation.")
    else:
        print("No changes made.")


def _cancel_consultation():
    """Cancel a consultation."""
    print("\n--- Cancel Consultation ---")
    consultation_id = int(input("Consultation ID: ").strip())
    reason = input("Reason for cancellation: ").strip()

    if ConsultationManager.cancel_consultation(consultation_id, reason):
        print("Consultation cancelled successfully.")
    else:
        print("Failed to cancel consultation.")


def _upcoming_consultations():
    """View upcoming consultations."""
    print("\n--- Upcoming Consultations ---")
    days_str = input("Number of days ahead (default 7): ").strip()
    days = int(days_str) if days_str else 7

    consultations = ConsultationManager.get_upcoming_consultations(days)
    if not consultations:
        print("No upcoming consultations.")
        return

    for c in consultations:
        print(
            f"  [{c['consultation_id']}] {c['scheduled_date']} {c['scheduled_time']} | "
            f"Client: {c['client_name']} | "
            f"Type: {c['consultation_type']} | "
            f"Lawyer: {c.get('lawyer_name', 'Unassigned')}"
        )


def _create_document():
    """Create a legal document."""
    print("\n--- Create Document ---")
    case_id = int(input("Case ID: ").strip())
    document_type = input("Document type (e.g. brief, contract, letter, filing): ").strip()
    document_name = input("Document name: ").strip()
    file_path = input("File path (optional): ").strip() or None
    file_content = input("Content text (optional, Enter to skip): ").strip() or None
    created_by = input("Created by: ").strip() or None
    notes = input("Notes (optional): ").strip() or ""

    doc_id = DocumentManager.create_document(
        case_id, document_type, document_name,
        file_path, file_content, created_by, notes,
    )
    if doc_id:
        print(f"Document created. Document ID: {doc_id}")
    else:
        print("Failed to create document.")


def _view_document():
    """View document details."""
    print("\n--- View Document ---")
    document_id = int(input("Document ID: ").strip())

    doc = DocumentManager.get_document(document_id)
    if not doc:
        print("Document not found.")
        return

    print(f"\n  Document ID:    {doc['document_id']}")
    print(f"  Name:           {doc['document_name']}")
    print(f"  Type:           {doc['document_type']}")
    print(f"  Case ID:        {doc.get('case_id', 'N/A')}")
    print(f"  Version:        {doc.get('version', 1)}")
    print(f"  Created By:     {doc.get('created_by', 'N/A')}")
    print(f"  Created:        {doc.get('created_at', 'N/A')}")
    if doc.get('file_path'):
        print(f"  File Path:      {doc['file_path']}")
    if doc.get('notes'):
        print(f"  Notes:          {doc['notes']}")


def _list_case_documents():
    """List documents for a case."""
    print("\n--- Case Documents ---")
    case_id = int(input("Case ID: ").strip())

    docs = DocumentManager.get_case_documents(case_id)
    if not docs:
        print("No documents found.")
        return

    print(f"\n{'ID':<8}{'Name':<30}{'Type':<15}{'Version':<10}{'Created':<20}")
    print("-" * 83)
    for d in docs:
        print(
            f"{d['document_id']:<8}{d['document_name']:<30}{d['document_type']:<15}"
            f"v{d.get('version', 1):<9}{str(d.get('created_at', 'N/A')):<20}"
        )


def _view_document_history():
    """View version history for a document."""
    print("\n--- Document Version History ---")
    document_name = input("Document name: ").strip()
    case_id = int(input("Case ID: ").strip())

    history = DocumentManager.get_document_history(document_name, case_id)
    if not history:
        print("No version history found.")
        return

    for d in history:
        print(
            f"  v{d.get('version', 1)} | ID: {d['document_id']} | "
            f"By: {d.get('created_by', 'N/A')} | "
            f"Date: {d.get('created_at', 'N/A')}"
        )


def _record_payment():
    """Record a legal services payment."""
    print("\n--- Record Payment ---")
    client_id = input("Client ID: ").strip()
    client_email = input("Client email: ").strip()
    amount = float(input("Amount (GBP): ").strip())

    print("Payment types: consultation, case_filing, document_review, other")
    payment_type = input("Payment type: ").strip()
    payment_method = input("Payment method (card/cash/bank_transfer): ").strip()

    case_id_str = input("Case ID (optional): ").strip()
    case_id = int(case_id_str) if case_id_str else None
    consultation_id_str = input("Consultation ID (optional): ").strip()
    consultation_id = int(consultation_id_str) if consultation_id_str else None

    payment_id = PaymentManager.record_payment(
        client_id, client_email, amount, payment_type, payment_method,
        case_id, consultation_id,
    )
    if payment_id:
        print(f"Payment recorded. Payment ID: {payment_id}")
    else:
        print("Failed to record payment.")


def _view_payment():
    """View payment details."""
    print("\n--- View Payment ---")
    payment_id = int(input("Payment ID: ").strip())

    payment = PaymentManager.get_payment(payment_id)
    if not payment:
        print("Payment not found.")
        return

    print(f"\n  Payment ID:     {payment['payment_id']}")
    print(f"  Client:         {payment.get('client_id', 'N/A')}")
    print(f"  Amount:         GBP {payment.get('amount', 0):.2f}")
    print(f"  Type:           {payment.get('payment_type', 'N/A')}")
    print(f"  Method:         {payment.get('payment_method', 'N/A')}")
    print(f"  Status:         {payment.get('status', 'N/A')}")
    print(f"  Reference:      {payment.get('transaction_reference', 'N/A')}")
    if payment.get('case_id'):
        print(f"  Case ID:        {payment['case_id']}")
    if payment.get('consultation_id'):
        print(f"  Consultation:   {payment['consultation_id']}")
    print(f"  Date:           {payment.get('created_at', 'N/A')}")


def _list_payments():
    """List payments."""
    print("\n--- List Payments ---")
    client_id = input("Filter by client ID (Enter for all): ").strip() or None
    case_id_str = input("Filter by case ID (Enter for all): ").strip()
    case_id = int(case_id_str) if case_id_str else None
    status = input("Filter by status (pending/completed/refunded, Enter for all): ").strip() or None

    filters = {}
    if client_id:
        filters['client_id'] = client_id
    if case_id:
        filters['case_id'] = case_id
    if status:
        filters['status'] = status

    payments = PaymentManager.get_all_payments(filters if filters else None)
    if not payments:
        print("No payments found.")
        return

    print(f"\n{'ID':<8}{'Client':<15}{'Amount':<12}{'Type':<18}{'Status':<12}{'Date':<20}")
    print("-" * 85)
    for p in payments:
        print(
            f"{p['payment_id']:<8}{p.get('client_id', 'N/A'):<15}"
            f"GBP {p.get('amount', 0):<7.2f}{p.get('payment_type', 'N/A'):<18}"
            f"{p.get('status', 'N/A'):<12}{str(p.get('created_at', 'N/A'))[:10]:<20}"
        )


def _process_refund():
    """Process a payment refund."""
    print("\n--- Process Refund ---")
    payment_id = int(input("Payment ID: ").strip())
    reason = input("Reason for refund: ").strip()
    confirm = input("Confirm refund? (y/n): ").strip().lower()
    if confirm != "y":
        print("Cancelled.")
        return

    if PaymentManager.process_refund(payment_id, reason):
        print("Refund processed successfully.")
    else:
        print("Failed to process refund.")


def _revenue_statistics():
    """Display revenue statistics."""
    print("\n--- Revenue Statistics ---")
    start_date = input("Start date (YYYY-MM-DD, Enter for all): ").strip() or None
    end_date = input("End date (YYYY-MM-DD, Enter for all): ").strip() or None

    stats = PaymentManager.get_revenue_statistics(start_date, end_date)
    if not stats:
        print("No data available.")
        return

    print(f"  Total Revenue:   GBP {stats.get('total_revenue', 0):.2f}")
    print(f"  Total Refunds:   GBP {stats.get('total_refunds', 0):.2f}")
    print(f"  Net Revenue:     GBP {stats.get('net_revenue', 0):.2f}")
    print(f"  Refund Count:    {stats.get('refund_count', 0)}")

    by_type = stats.get('by_payment_type', {})
    if by_type:
        print("\n  By Payment Type:")
        for ptype, info in by_type.items():
            print(f"    {ptype}: GBP {info['total']:.2f} ({info['count']} payments)")

    by_method = stats.get('by_payment_method', {})
    if by_method:
        print("\n  By Payment Method:")
        for method, info in by_method.items():
            print(f"    {method}: GBP {info['total']:.2f} ({info['count']} payments)")


def _calculate_fee():
    """Calculate a service fee."""
    print("\n--- Calculate Service Fee ---")
    print("Available service fees:")
    for key, fee in SERVICE_FEES.items():
        print(f"  {key}: GBP {fee:.2f}")

    service_type = input("\nService type: ").strip()
    duration_str = input("Duration in minutes (default 30): ").strip()
    duration = int(duration_str) if duration_str else 30

    fee = calculate_service_fee(service_type, duration)
    print(f"\nCalculated fee: GBP {fee:.2f}")


def _generate_invoice():
    """Generate an invoice for a case."""
    print("\n--- Generate Invoice ---")
    case_id = int(input("Case ID: ").strip())

    case = CaseManager.get_case(case_id)
    if not case:
        print("Case not found.")
        return

    payments = PaymentManager.get_all_payments({'case_id': case_id})
    services_input = input("List services provided (comma-separated): ").strip()
    services = [s.strip() for s in services_input.split(",") if s.strip()]

    invoice = generate_invoice_text(case, payments, services)
    print(invoice)


if __name__ == "__main__":
    display_menu()
