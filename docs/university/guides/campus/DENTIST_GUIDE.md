# Dentist - User Guide

## Overview

The University Dental Clinic provides comprehensive dental care for students and staff, including routine check-ups, professional cleaning, fillings, extractions, root canals, crowns, whitening, and emergency treatments. The system manages patient registration, appointment scheduling, treatment records, prescriptions, X-ray/imaging records, and financial processing with full integration to the university finance and email systems.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Patient Registration](#patient-registration)
3. [Appointments](#appointments)
4. [Treatments & Procedures](#treatments--procedures)
5. [Prescriptions](#prescriptions)
6. [Patient Records](#patient-records)
7. [Payments & Refunds](#payments--refunds)
8. [Administration](#administration)
9. [Best Practices](#best-practices)
10. [Troubleshooting](#troubleshooting)
11. [Contact Information](#contact-information)

---

## Getting Started

### Accessing the Dental Clinic System

**GUI Mode:**
1. Launch the application → **Health Services** → **Dentist**
2. Login with university credentials
3. Multi-tab interface loads: Appointments, Treatments, Patient Records, Administration, Payments & Refunds

### Clinic Hours

- **Monday-Thursday**: 09:00 - 17:00
- **Friday**: 09:00 - 16:00
- **Saturday**: 10:00 - 14:00

### Time Slots

Appointments are available in 30-minute intervals:
- Morning: 09:00, 09:30, 10:00, 10:30, 11:00, 11:30
- Afternoon: 13:00, 13:30, 14:00, 14:30, 15:00, 15:30, 16:00

---

## Patient Registration

### Registering as a New Patient

1. Navigate to the **Appointments** tab
2. Click **Register**
3. Complete the registration form:
   - Phone number
   - Date of birth
   - Emergency contact name and phone
   - Medical history
   - Allergies
4. System generates a unique patient number (format: `PAT-XXXXXXXX`)
5. You can now book appointments

### Your Patient Profile

Your patient record includes:
- Patient number and personal details
- Medical history and allergies
- Insurance provider and number (if applicable)
- Emergency contact information
- Last visit date (updated automatically)

---

## Appointments

### Our Dentists

| Dentist | ID | Specialisation |
|---------|----|----------------|
| Dr. Sarah Mitchell | DEN001 | General Dentistry |
| Dr. James Wilson | DEN002 | Orthodontics |
| Dr. Emily Chen | DEN003 | Periodontics |
| Dr. Michael Brown | DEN004 | Endodontics |

### Booking an Appointment

1. Navigate to the **Appointments** tab
2. Select a dentist from the dropdown
3. Enter your preferred date (YYYY-MM-DD)
4. Choose an available time slot
5. Select your treatment type
6. Review the estimated fee
7. Click **Book**
8. Process payment (see [Payments](#payments--refunds))
9. Appointment reference generated (format: `DEN-YYYYMMDD-XXXXXX`)
10. Confirmation and receipt email sent automatically

### Appointment Statuses

| Status | Description |
|--------|-------------|
| **Scheduled** | Appointment booked |
| **Confirmed** | Patient confirmed attendance |
| **In Progress** | Treatment currently underway |
| **Completed** | Treatment finished |
| **Cancelled** | Appointment cancelled |
| **No Show** | Patient did not attend |

### Cancelling an Appointment

1. Select the appointment from your list
2. Click **Cancel Appointment**
3. Confirm the cancellation
4. Cancellation email sent automatically

### Rescheduling an Appointment

1. Select the appointment from your list
2. Click **Reschedule**
3. Choose a new date, time, and optionally a different dentist
4. System validates no conflicts exist
5. Rescheduling confirmation email sent

---

## Treatments & Procedures

### Treatment Menu

| Treatment | Duration | Fee |
|-----------|----------|-----|
| Routine Check-up | 30 min | £25.00 |
| Professional Cleaning | 45 min | £45.00 |
| Dental Filling | 60 min | £80.00 |
| Tooth Extraction | 45 min | £100.00 |
| Root Canal | 90 min | £350.00 |
| Dental Crown | 60 min | £450.00 |
| Teeth Whitening | 60 min | £150.00 |
| Dental X-Ray | 15 min | £35.00 |
| Emergency Treatment | 60 min | £120.00 |
| Consultation | 30 min | £30.00 |

### Viewing Treatment History

1. Navigate to the **Treatments** tab
2. View your complete treatment history with: Date, Treatment, Dentist, Fee, Payment Status, Follow-up
3. Filter by treatment type or payment status
4. Double-click a treatment for full details including tooth number, description, and notes

### Follow-Up Appointments

- When a treatment requires follow-up, the **Follow-up Required** flag is set
- A follow-up date is recorded
- You can schedule a follow-up directly from the Treatments tab

### Exporting Treatment History

Click **Export to CSV** to download your treatment history for personal records.

---

## Prescriptions

### Viewing Prescriptions

1. Navigate to the **Treatments** tab
2. Click **View Prescriptions**
3. View all your prescriptions with:
   - Medication name
   - Dosage and frequency
   - Duration
   - Prescribed date
   - Special instructions

Prescriptions are linked to specific treatments and created by your dentist after completing a procedure.

---

## Patient Records

### Viewing Your Profile

1. Navigate to the **Patient Records** tab
2. View your patient number, name, email, phone, date of birth, allergies, and last visit
3. Click **Update Profile** to change your phone number

### Dental History

Click **View Dental History** to see a chronological record of all treatments including dates, treatment types, dentists, and clinical notes.

### Available Treatments Reference

View the complete treatment list with durations and fees for reference when planning appointments.

---

## Payments & Refunds

### Payment Methods

| Method | Description |
|--------|-------------|
| **Cash** | Pay at the clinic reception |
| **Card** | Debit or credit card |
| **Student Account** | Deduct from university finance account (balance verified) |

### Paying for Appointments

Payment is processed during the booking process:
1. Select your treatment type
2. Fee is displayed based on the treatment
3. Choose your payment method
4. For student accounts: balance is verified and deducted immediately
5. Transaction reference generated
6. Receipt email sent automatically

### Paying for Treatments

For treatments recorded by staff with pending payment:
1. Navigate to the **Treatments** tab
2. Select the unpaid treatment
3. Click **Process Payment**
4. Choose payment method and confirm

### Processing Refunds (Admin/Staff)

1. Navigate to the **Payments & Refunds** tab
2. Search for a payment by patient ID or name
3. Select the transaction and click **Process Refund**
4. Choose the refund method:
   - **Cash** — refund in cash
   - **Card** — refund to original card
   - **Student Account** — credit back to finance account (balance shown before/after)
5. Refund reference generated (format: `DENTIST-REFUND-XXXXXXXXXXXX`)
6. Refund receipt sent via email
7. Export payment records to CSV via **Export to CSV**

---

## Administration

### Today's Appointments (Admin/Staff)

View all appointments scheduled for the current day with time, patient name, dentist, treatment, and status.

### Reports

**Daily Report:**
- Total appointments scheduled
- Completed appointments
- Treatments performed
- Daily revenue

**Monthly Report:**
- Total appointments for the month
- New patients registered
- Total revenue
- Treatment breakdown by type with counts and revenue

### Email Reports

Click **Email Report** to send the generated report to all administrator email addresses.

### Appointment Reminders

Send email reminders to patients with upcoming appointments (looks ahead 7 days). Only sends to scheduled and confirmed appointments.

### Recording Treatments (Staff)

Staff can manually record completed treatments with patient number, treatment type, date, and clinical notes.

### Creating Prescriptions (Staff)

Staff can create prescriptions with medication, dosage, frequency, duration, and instructions linked to the patient record.

---

## Best Practices

1. **Register early** — complete your patient registration before booking your first appointment
2. **Book routine check-ups** — schedule regular check-ups every 6 months
3. **Update medical history** — inform the clinic of any changes to your health or medications
4. **Arrive on time** — late arrivals may need rescheduling
5. **List all allergies** — ensure your allergy information is up to date
6. **Follow prescriptions** — take prescribed medications as directed
7. **Schedule follow-ups** — don't delay follow-up appointments when recommended

---

## Troubleshooting

### Common Issues

**Cannot book appointment:**
- Ensure you are registered as a patient first
- Verify the dentist is available on the selected date/time
- Check that the date is valid (YYYY-MM-DD format)

**Payment failed:**
- If using student account, check your balance
- Try an alternative payment method
- Contact the clinic reception for manual processing

**Cannot find my records:**
- Verify you are logged in with the correct account
- Contact the clinic with your patient number

**Appointment reminder not received:**
- Check your spam/junk folder
- Verify your email address is correct in your profile
- Contact the clinic to update your email

---

## Contact Information

**University Dental Clinic**
- **Phone**: (555) 123-DENT
- **Email**: dentist@university.edu
- **Location**: Health Services Building, First Floor

**Clinic Hours**
- Monday-Thursday: 09:00 - 17:00
- Friday: 09:00 - 16:00
- Saturday: 10:00 - 14:00

**Emergency Dental**
- **Phone**: (555) 123-DENT (select emergency option)
- Available during clinic hours

---

**Last Updated**: February 2026
**Module**: `university_system/modules/domain/dentist/`
**Support**: dentist@university.edu | (555) 123-DENT
