"""Extracted AcademicCalendarManager exports methods."""

from ._shared import *  # noqa: F401,F403


class ExportsMixin:
    def export_calendar(self, file_path: str, format_type: str,
                       academic_year: Optional[str] = None) -> Dict[str, Any]:
        """Export calendar with security validation"""
        if not self.auth_manager.check_permission('export_data'):
            raise PermissionError("Insufficient permissions to export data")

        # Resolve the path inside the exports directory. Reducing it to a bare
        # basename (as this did) wrote the export to the process's working
        # directory, wherever the app happened to be launched from.
        safe_path = ValidationUtils.resolve_safe_path(
            file_path, self.config.export_directory, allow_absolute=True
        )
        if not safe_path:
            raise ValidationError("Invalid file name")

        # Validate format
        supported_formats = {'json', 'csv', 'xlsx', 'pdf', 'ics', 'txt'}
        format_type = format_type.lower()
        if format_type not in supported_formats:
            raise ValidationError(f"Unsupported format. Use: {', '.join(supported_formats)}")

        # Get export data
        try:
            export_data = self._get_export_data(academic_year)

            if not export_data:
                return {'success': False, 'message': 'No data to export'}

            # Limit export size
            if len(export_data) > self.config.max_export_records:
                raise ValidationError(f"Export too large. Maximum {self.config.max_export_records} records allowed")

            # Export based on format
            export_methods = {
                'json': self._export_json,
                'csv': self._export_csv,
                'xlsx': self._export_excel,
                'pdf': self._export_pdf,
                'ics': self._export_ical,
                'txt': self._export_txt
            }

            export_method = export_methods[format_type]
            success = export_method(export_data, safe_path)

            if success:
                logger.info(f"Calendar exported to {safe_path}")
                return {'success': True, 'message': f'Calendar exported to {safe_path}', 'file_path': safe_path}
            else:
                return {'success': False, 'message': 'Export failed'}

        except Exception as e:
            logger.error(f"Export failed: {e}")
            raise ExportError(f"Export failed: {e}")

    def _get_export_data(self, academic_year: Optional[str] = None) -> List[Dict]:
        """Get formatted data for export"""
        try:
            query = """
                SELECT s.name AS semester_name, s.start_date AS semester_start,
                       s.end_date AS semester_end, e.name AS event_name,
                       COALESCE(e.date, e.date_start) as event_date,
                       e.date_end, e.event_type, e.description
                FROM semesters s
                LEFT JOIN (SELECT source_event_id AS id, title AS name, event_date AS date, start_datetime AS date_start, end_datetime AS date_end, description, event_type, created_at AS date_added, updated_at AS last_modified, created_by, start_time, end_time, location, audience, assignment_id, trip_id, organizer_name AS organizer, participants, status, country_code, region, is_active FROM unified_events uev WHERE uev.source_type = 'academic_calendar') e ON (
                    (e.date BETWEEN s.start_date AND s.end_date) OR
                    (e.date_start BETWEEN s.start_date AND s.end_date) OR
                    (e.date_end BETWEEN s.start_date AND s.end_date)
                )
            """
            params = []

            if academic_year:
                academic_year = ValidationUtils.sanitize_string(academic_year, 20)
                query += " WHERE s.academic_year_id = ?"
                params.append(academic_year)

            query += " ORDER BY s.start_date, event_date"

            rows = self.db_manager.execute_query(query, tuple(params))

            export_data = []
            for row in rows:
                if row['event_name']:  # Only include rows with events
                    event_date = row['event_date']
                    if row['date_end'] and row['date_end'] != row['event_date']:
                        event_date += f" to {row['date_end']}"

                    export_data.append({
                        'Academic Year': academic_year or 'All',
                        'Semester': row['semester_name'],
                        'Semester Start': row['semester_start'],
                        'Semester End': row['semester_end'],
                        'Event Name': row['event_name'],
                        'Event Date': event_date,
                        'Event Type': row['event_type'],
                        'Description': row['description'] or ''
                    })

            return export_data

        except Exception as e:
            logger.error(f"Failed to get export data: {e}")
            raise DatabaseError(f"Failed to get export data: {e}")

    def _export_json(self, data: List[Dict], file_path: str) -> bool:
        """Export to JSON format"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"JSON export failed: {e}")
            return False

    def _export_csv(self, data: List[Dict], file_path: str) -> bool:
        """Export to CSV format"""
        try:
            if not data:
                return False

            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
            return True
        except Exception as e:
            logger.error(f"CSV export failed: {e}")
            return False

    def _export_excel(self, data: List[Dict], file_path: str) -> bool:
        """Export to Excel format"""
        if not PANDAS_AVAILABLE:
            logger.error("pandas not available for Excel export")
            return False

        try:
            df = pd.DataFrame(data)
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Academic Calendar', index=False)

                # Auto-adjust column widths
                worksheet = writer.sheets['Academic Calendar']
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except (AttributeError, TypeError):
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width

            return True
        except Exception as e:
            logger.error(f"Excel export failed: {e}")
            return False

    def _export_pdf(self, data: List[Dict], file_path: str) -> bool:
        """Export to PDF format"""
        if not REPORTLAB_AVAILABLE:
            logger.error("reportlab not available for PDF export")
            return False

        try:
            doc = SimpleDocTemplate(file_path, pagesize=A4)
            story = []
            styles = getSampleStyleSheet()

            # Add title
            title = Paragraph("Academic Calendar", styles['Title'])
            story.append(title)
            story.append(Spacer(1, 12))

            # Add generation info
            generation_info = Paragraph(
                f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                styles['Normal']
            )
            story.append(generation_info)
            story.append(Spacer(1, 12))

            # Group by semester
            semesters = {}
            for item in data:
                semester = item['Semester']
                if semester not in semesters:
                    semesters[semester] = {
                        'info': {'start': item['Semester Start'], 'end': item['Semester End']},
                        'events': []
                    }
                semesters[semester]['events'].append(item)

            # Create tables for each semester
            for semester_name, semester_data in semesters.items():
                # Semester header
                semester_title = Paragraph(f"{semester_name} Semester", styles['Heading2'])
                story.append(semester_title)

                period_info = Paragraph(
                    f"Period: {semester_data['info']['start']} to {semester_data['info']['end']}",
                    styles['Normal']
                )
                story.append(period_info)
                story.append(Spacer(1, 6))

                # Events table
                table_data = [['Date', 'Event', 'Type', 'Description']]
                for event in semester_data['events']:
                    description = event['Description'][:50] + ('...' if len(event['Description']) > 50 else '')
                    table_data.append([
                        event['Event Date'],
                        event['Event Name'],
                        event['Event Type'],
                        description
                    ])

                table = Table(table_data, colWidths=[100, 200, 80, 150])
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('FONTSIZE', (0, 1), (-1, -1), 8),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ]))

                story.append(table)
                story.append(Spacer(1, 20))

            doc.build(story)
            return True
        except Exception as e:
            logger.error(f"PDF export failed: {e}")
            return False

    def _export_txt(self, data: List[Dict], file_path: str) -> bool:
        """Export to plain text format"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("ACADEMIC CALENDAR\n")
                f.write("=" * 80 + "\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("\n")

                current_semester = None
                for item in data:
                    if current_semester != item['Semester']:
                        current_semester = item['Semester']
                        f.write(f"\n{current_semester} SEMESTER\n")
                        f.write(f"Period: {item['Semester Start']} to {item['Semester End']}\n")
                        f.write("-" * 60 + "\n")

                    f.write(f"{item['Event Date']:<20} {item['Event Name']:<30} ({item['Event Type']})\n")
                    if item['Description']:
                        f.write(f"{'':20} {item['Description']}\n")

                f.write("\n" + "=" * 80 + "\n")

            return True
        except Exception as e:
            logger.error(f"TXT export failed: {e}")
            return False

    def _export_ical(self, data: List[Dict], file_path: str) -> bool:
        """Export to iCal format"""
        try:
            ical_lines = [
                "BEGIN:VCALENDAR",
                "VERSION:2.0",
                "PRODID:-//Academic Calendar Manager//EN",
                "CALSCALE:GREGORIAN"
            ]

            for item in data:
                if item['Event Name']:
                    event_id = str(uuid.uuid4())
                    event_lines = [
                        "BEGIN:VEVENT",
                        f"UID:{event_id}@academic-calendar",
                        f"SUMMARY:{item['Event Name']}",
                        f"DESCRIPTION:{item['Description']}",
                        f"CATEGORIES:{item['Event Type']}"
                    ]

                    # Handle date formatting
                    try:
                        if ' to ' in item['Event Date']:
                            start_date, end_date = item['Event Date'].split(' to ')
                            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                        else:
                            start_dt = datetime.strptime(item['Event Date'], "%Y-%m-%d")
                            end_dt = start_dt + timedelta(days=1)

                        event_lines.extend([
                            f"DTSTART;VALUE=DATE:{start_dt.strftime('%Y%m%d')}",
                            f"DTEND;VALUE=DATE:{end_dt.strftime('%Y%m%d')}",
                            f"DTSTAMP:{datetime.now().strftime('%Y%m%dT%H%M%SZ')}"
                        ])
                    except ValueError:
                        continue

                    event_lines.append("END:VEVENT")
                    ical_lines.extend(event_lines)

            ical_lines.append("END:VCALENDAR")

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(ical_lines))

            return True
        except Exception as e:
            logger.error(f"iCal export failed: {e}")
            return False

    def safe_open_file(self, file_path: str):
        """Safely open a file with security checks"""
        try:
            # Confine the path to a directory this system writes to, keeping
            # the directory itself: stripping it to a basename meant only
            # files in the current working directory could ever be opened.
            # Resolve where the file actually is: a bare name means the
            # exports directory, an absolute path is taken as given (it is
            # what export_calendar just returned to the caller).
            safe_path = ValidationUtils.resolve_safe_path(
                file_path, self.config.export_directory, create=False, allow_absolute=True
            )
            if not safe_path:
                raise ValidationError("Invalid file name")

            if not os.path.exists(safe_path):
                raise ValidationError(f"File {safe_path} not found")

            # Check file extension
            _, ext = os.path.splitext(safe_path)
            if ext.lower() not in self.config.allowed_file_types:
                raise ValidationError(f"File type {ext} not allowed")

            # Open file with appropriate application
            if platform.system() == "Windows":
                os.startfile(safe_path)
            elif platform.system() == "Darwin":
                subprocess.call(["open", safe_path])
            else:
                subprocess.call(["xdg-open", safe_path])

            logger.info(f"Opened file: {safe_path}")

        except Exception as e:
            logger.error(f"Failed to open file: {e}")
            raise CalendarError(f"Failed to open file: {e}")
