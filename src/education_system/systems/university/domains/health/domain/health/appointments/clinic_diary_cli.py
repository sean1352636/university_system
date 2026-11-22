"""Clinic diary screens for the health CLI: provider time off, schedule
templates, the waiting list, feedback, rescheduling and other clinics'
appointments — all over ``application/health/diary``. Split out of
``appointment_booking`` (which re-exports these names) to keep it under the
layout size limit."""

from datetime import datetime

from education_system.systems.university.domains.health.infrastructure.health.storage import get_connection
from education_system.systems.university.domains.health.domain.health.records.db.audit import log_audit_event
from education_system.systems.university.domains.health.domain.health.services import get_user_student_id


def _send_appointment_email(template_name, recipient_email, template_vars):
    from education_system.systems.university.domains.health.domain.health.appointments.appointment_booking import (
        _send_appointment_email as send,
    )
    return send(template_name, recipient_email, template_vars)


def manage_provider_time_off(auth):
    """Manage provider time off/vacation (``provider_time_off``; blocks booking)."""
    from education_system.systems.university.domains.health.application.health import diary
    print("\n===== Provider Time Off Management =====")

    provider_name = input("Provider name: ").strip()

    print("Time Off Options:")
    print("1. Add Vacation/Time Off")
    print("2. View Scheduled Time Off")
    print("3. Remove Time Off")
    print("4. Return to schedule menu")

    choice = input("\nSelect option (1-4): ")
    conn = get_connection()
    try:
        diary.ensure_schema(conn)
        if choice == '1':
            if not provider_name:
                print("A provider name is required.")
                return
            while True:
                start_date = input("Start date (YYYY-MM-DD): ").strip()
                end_date = input("End date (YYYY-MM-DD) [same day]: ").strip() or start_date
                try:
                    datetime.strptime(start_date, '%Y-%m-%d')
                    datetime.strptime(end_date, '%Y-%m-%d')
                    break
                except ValueError:
                    print("Invalid date format. Please use YYYY-MM-DD.")
            start_time = end_time = None
            if start_date == end_date:
                part = input("Part of the day only? Enter HH:MM-HH:MM, or blank for all day: ").strip()
                if "-" in part:
                    start_time, end_time = [t.strip() for t in part.split("-", 1)]
            reason = input("Reason (vacation/conference/sick/other): ").strip()
            try:
                tid, affected = diary.add_time_off(
                    conn, provider=provider_name, start_date=start_date, end_date=end_date,
                    start_time=start_time, end_time=end_time, reason=reason,
                    by=auth.current_user.get('username'))
            except ValueError as exc:
                print(f"Not saved: {exc}")
                return
            log_audit_event(auth.current_user['id'], 'add_provider_time_off', 'provider_time_off',
                            tid, {"provider": provider_name, "from": start_date, "to": end_date},
                            conn=conn)
            conn.commit()
            print(f"Time off scheduled for {provider_name} from {start_date} to {end_date}.")
            print("New bookings in this period are now blocked.")
            if affected:
                print(f"\n{len(affected)} existing appointment(s) fall in this period and should "
                      "be rescheduled:")
                for a in affected:
                    print(f"  • {a['date']} {a['time']}  {a['type']}  student {a['student_id']}  "
                          f"({a['source'].replace('_', ' ')} #{a['id']})")
        elif choice == '2':
            rows = diary.list_time_off(conn, provider_name or None)
            print(f"\nScheduled Time Off{' for ' + provider_name if provider_name else ''}:")
            if not rows:
                print("  None scheduled.")
            for r in rows:
                span = r['start_date'] if r['start_date'] == r['end_date'] else \
                    f"{r['start_date']} to {r['end_date']}"
                hours = f" {r['start_time']}-{r['end_time']}" if r['start_time'] else ""
                print(f"• [{r['id']}] {r['provider']}: {span}{hours}: {r['reason'] or 'time off'}")
        elif choice == '3':
            tid = input("Time off ID to remove: ").strip()
            if tid.isdigit() and diary.remove_time_off(conn, int(tid)):
                log_audit_event(auth.current_user['id'], 'remove_provider_time_off',
                                'provider_time_off', tid, None, conn=conn)
                conn.commit()
                print("Time off removed.")
            else:
                print("No such time off.")
    finally:
        conn.close()

def schedule_templates(auth):
    """Manage schedule templates (weekly patterns that write provider_schedules)."""
    from education_system.systems.university.domains.health.application.health import diary
    print("\n===== Schedule Templates =====")
    day_names = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat", 0: "Sun"}

    conn = get_connection()
    try:
        templates = diary.list_templates(conn)
        print("Available Schedule Templates:")
        for i, template in enumerate(templates):
            days = ", ".join(f"{day_names[s['day']]} {s['start']}-{s['end']}"
                             for s in template['pattern'])
            print(f"{i+1}. {template['name']}  [{days}; max {template['max_appointments']}/day]")

        print("\nTemplate Actions:")
        print("1. Apply Template to Provider")
        print("2. Create New Template")
        print("3. Modify Existing Template")
        print("4. Return to schedule menu")

        choice = input("\nSelect action (1-4): ")

        def pick():
            num = input("Template number: ").strip()
            if num.isdigit() and 1 <= int(num) <= len(templates):
                return templates[int(num) - 1]
            print("Invalid template number.")
            return None

        def ask_pattern():
            print("Enter one line per day as DAY HH:MM-HH:MM (e.g. Mon 09:00-17:00); blank to finish.")
            lookup = {v.lower(): k for k, v in day_names.items()}
            pattern = []
            while True:
                line = input("  > ").strip()
                if not line:
                    return pattern
                try:
                    day, hours = line.split(None, 1)
                    start, end = [h.strip() for h in hours.split("-", 1)]
                    pattern.append({"day": lookup[day[:3].lower()], "start": start, "end": end})
                except (ValueError, KeyError):
                    print("  Not understood; use e.g. Tue 08:00-12:00")

        if choice == '1':
            provider = input("Provider name: ").strip()
            template = pick()
            if provider and template:
                n = diary.apply_template(conn, template['id'], provider)
                log_audit_event(auth.current_user['id'], 'apply_schedule_template',
                                'provider_schedule', provider, {"template": template['name']},
                                conn=conn)
                conn.commit()
                print(f"Template applied to {provider}: {n} weekly clinic(s); the previous "
                      "schedule rows were deactivated.")
        elif choice in ('2', '3'):
            template = pick() if choice == '3' else None
            if choice == '3' and not template:
                return
            name = input(f"Template name{' [' + template['name'] + ']' if template else ''}: ").strip() \
                or (template['name'] if template else '')
            pattern = ask_pattern() or (template['pattern'] if template else [])
            max_raw = input("Max appointments per day [8]: ").strip()
            try:
                tid = diary.save_template(conn, name=name, pattern=pattern,
                                          max_appointments=int(max_raw) if max_raw.isdigit() else 8,
                                          by=auth.current_user.get('username'),
                                          template_id=template['id'] if template else None)
            except (ValueError, KeyError) as exc:
                print(f"Not saved: {exc}")
                return
            conn.commit()
            print(f"Template '{name}' saved (#{tid}).")
    finally:
        conn.close()

def _reschedule_into_new(auth, conn, student_id, apt_type, provider, old_date, old_time, context):
    from education_system.systems.university.domains.health.application.health import diary
    new_date = input("New date (YYYY-MM-DD): ").strip()
    new_time = input("New time (HH:MM): ").strip()
    try:
        datetime.strptime(new_date, '%Y-%m-%d')
        datetime.strptime(new_time, '%H:%M')
    except ValueError:
        print("Invalid date or time; use Schedule Appointment to book the new time.")
        return
    check = diary.check_booking(conn, student_id=student_id, provider=provider, date=new_date,
                                time=new_time)
    override_reason = None
    if not check.ok:
        print("⚠️  " + check.summary().replace("\n", "\n⚠️  "))
        if check.blocked:
            return
        override_reason = input("Book anyway? Enter the reason (blank to cancel): ").strip()
        if len(override_reason) < 5:
            return
    new_id = diary.book(conn, student_id=student_id, appointment_type=apt_type, date=new_date,
                        time=new_time, provider=provider,
                        reason=f"Rescheduled from {old_date} {old_time}",
                        has_conflict=bool(override_reason))
    if override_reason:
        diary.record_booking_override(conn, auth.current_user.get('username'), new_id, check,
                                      override_reason)
    conn.commit()
    diary.publish_booking(new_id, student_id=student_id, date=new_date, time=new_time,
                          provider=provider, appointment_type=apt_type)
    print(f"New appointment {new_id} booked for {new_date} at {new_time}.")
    if context and context.get('student_email'):
        sent = _send_appointment_email('campus_services/health/appointment_rescheduled',
                                       context['student_email'], {
                                           'patient_name': context.get('student_name'),
                                           'old_date': old_date, 'old_time': old_time,
                                           'date': new_date, 'new_date': new_date,
                                           'time': new_time, 'new_time': new_time,
                                           'practitioner': provider or 'the health team',
                                           'department': apt_type,
                                           'location': 'University Health Centre'})
        print("Reschedule e-mail sent." if sent else
              "Note: the reschedule e-mail could not be sent.")


def manage_waiting_list(auth):
    """The appointment waiting list: join, view, accept an offer, withdraw."""
    from education_system.systems.university.domains.health.application.health import diary
    staff = auth.check_permission('manage_health_appointments')
    own = None if staff else get_user_student_id(auth)
    if not staff and not own:
        print("Error: No student ID associated with your account.")
        return
    conn = get_connection()
    try:
        diary.ensure_schema(conn)
        print("\n===== Appointment Waiting List =====")
        print("1. Join the waiting list")
        print("2. View the waiting list")
        print("3. Accept an offered slot")
        print("4. Withdraw an entry")
        choice = input("Select option (1-4): ").strip()
        if choice == '1':
            student_id = own or input("Student ID: ").strip()
            appointment_type = input("Appointment type: ").strip()
            if not student_id or not appointment_type:
                print("Student and appointment type are required.")
                return
            wid = diary.join_waitlist(conn, student_id=student_id, appointment_type=appointment_type,
                                      provider=input("Provider (blank = any): ").strip() or None,
                                      preferred_from=input("Earliest date (YYYY-MM-DD, blank = any): ").strip() or None,
                                      preferred_to=input("Latest date (blank = any): ").strip() or None,
                                      notes=input("Notes: ").strip(),
                                      by=auth.current_user.get('username'))
            conn.commit()
            print(f"Added (entry {wid}). A freed slot will be offered by e-mail.")
        elif choice == '2':
            rows = [r for r in diary.list_waitlist(conn, student_id=own)
                    if r['status'] in ('waiting', 'offered')]
            if not rows:
                print("Nobody is waiting.")
            for r in rows:
                offer = (f" — offered {r['offered_date']} {r['offered_time']} until "
                         f"{r['offer_expires_at']}" if r['status'] == 'offered' else "")
                print(f"[{r['id']}] {r['student_id']}  {r['appointment_type']}  "
                      f"provider {r['provider'] or 'any'}  {r['status']}{offer}")
        elif choice in ('3', '4'):
            wid = input("Entry ID: ").strip()
            if not wid.isdigit():
                print("Invalid ID.")
                return
            row = conn.execute("SELECT student_id FROM appointment_waitlist WHERE id = ?",
                               (int(wid),)).fetchone()
            if not row or (own and str(row[0]) != str(own)):
                print("No such entry.")
                return
            if choice == '3':
                try:
                    appt = diary.accept_offer(conn, int(wid), by=auth.current_user.get('username'))
                except ValueError as exc:
                    print(f"Not booked: {exc}")
                    return
                conn.commit()
                r = conn.execute("SELECT student_id, appointment_date, appointment_time, provider, "
                                 "appointment_type FROM health_appointments WHERE id = ?",
                                 (appt,)).fetchone()
                diary.publish_booking(appt, student_id=r[0], date=r[1], time=r[2], provider=r[3],
                                      appointment_type=r[4])
                print(f"Booked: appointment {appt} on {r[1]} at {r[2]}.")
            else:
                diary.withdraw(conn, int(wid))
                conn.commit()
                print("Withdrawn.")
    finally:
        conn.close()


def give_appointment_feedback(auth):
    """Rate a completed appointment (1-5) — the satisfaction figures come from these."""
    from education_system.systems.university.domains.health.application.health import diary
    student_id = get_user_student_id(auth)
    if not student_id:
        print("Feedback is given by the student who attended.")
        return
    conn = get_connection()
    try:
        pending = diary.awaiting_feedback(conn, student_id)
        if not pending:
            print("No completed appointments are waiting for your feedback.")
            return
        for i, a in enumerate(pending, 1):
            print(f"{i}. {a['date']} {a['time']}  {a['type']} with {a['provider'] or 'the health team'}")
        pick = input("Which appointment? ").strip()
        if not pick.isdigit() or not 1 <= int(pick) <= len(pending):
            return
        rating = input("Rating 1 (poor) - 5 (excellent): ").strip()
        a = pending[int(pick) - 1]
        try:
            diary.submit_feedback(conn, source=a['source'], appointment_id=a['id'],
                                  student_id=student_id, rating=int(rating),
                                  comments=input("Comments (optional): ").strip() or None)
        except (ValueError, LookupError) as exc:
            print(f"Not recorded: {exc}")
            return
        conn.commit()
        print("Thank you — your feedback has been recorded.")
    finally:
        conn.close()


def _other_clinic_appointments(conn, *, student_id=None, provider=None):
    """Dental / counselling / mental-health bookings for the same student or
    provider, from the clinic diary (wave 3 merges the tables)."""
    from education_system.systems.university.domains.health.application.health import diary
    rows = [a for a in diary.appointments(conn, student_id=student_id, provider=provider)
            if a['source'] != 'health_appointments']
    if rows:
        print("\n===== Other clinics =====")
        for a in rows:
            who = "anonymous" if a['anonymous'] else a['student_id']
            print(f"{a['source'].replace('_appointments', '').replace('_', ' ').title()} "
                  f"#{a['id']}: {a['date']} {a['time']}  {a['type']}  "
                  f"{a['provider'] or ''}  student {who}  [{a['status']}]")
