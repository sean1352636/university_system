"""Extracted function implementation."""

from .. import menus_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def display_pdf_reports_menu(scheduler):
    """Display PDF reports menu"""
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    print("\n📄 PDF Reports:")
    print("1. Room Utilization Report")
    print("2. Instructor Workload Report")
    print("3. Complete Analytics Report")

    choice = input("Enter your choice (1-3): ")

    if choice == '1':
        filename = scheduler.generate_room_utilization_report('pdf')
        if filename:
            print(f"PDF report generated: {filename}")

    elif choice == '2':
        filename = scheduler.generate_instructor_workload_report('pdf')
        if filename:
            print(f"PDF report generated: {filename}")

    elif choice == '3':
        print("Generating comprehensive analytics report...")
        # Generate multiple reports and combine them
        room_data = scheduler.generate_room_utilization_report('data')
        workload_data = scheduler.generate_instructor_workload_report('data')

        # Create combined report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = paths.ANALYTICS_DIR / f"comprehensive_report_{timestamp}.pdf"

        doc = SimpleDocTemplate(str(filename), pagesize=landscape(letter))
        styles = getSampleStyleSheet()
        elements = []

        # Title
        elements.append(Paragraph("Comprehensive Scheduling Analytics Report", styles["Title"]))
        elements.append(Spacer(1, 0.5*inch))

        # Room utilization section
        elements.append(Paragraph("Room Utilization Analysis", styles["Heading1"]))
        if room_data:
            room_table_data = [list(room_data[0].keys())]
            for room in room_data:
                room_table_data.append(list(room.values()))

            room_table = Table(room_table_data)
            room_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            elements.append(room_table)

        elements.append(Spacer(1, 0.5*inch))

        # Instructor workload section
        elements.append(Paragraph("Instructor Workload Analysis", styles["Heading1"]))
        if workload_data:
            workload_table_data = [list(workload_data[0].keys())]
            for instructor in workload_data:
                workload_table_data.append(list(instructor.values()))

            workload_table = Table(workload_table_data)
            workload_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgreen),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            elements.append(workload_table)

        # Generate timestamp
        elements.append(Spacer(1, 0.5*inch))
        elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles["Normal"]))

        doc.build(elements)
        print(f"Comprehensive PDF report generated: {filename}")

    else:
        print("Invalid choice.")
