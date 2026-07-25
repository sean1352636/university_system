# Barber Shop Management - User Guide

## Overview

The Barber Shop Management system provides comprehensive appointment scheduling, customer management, staff tracking, and financial processing for the university campus barber shop. It supports walk-in and scheduled appointments, loyalty tracking, gift cards, and detailed analytics with full integration to the university finance and email systems.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Appointments](#appointments)
3. [Customers](#customers)
4. [Services](#services)
5. [Staff Management](#staff-management)
6. [Finance & Payments](#finance--payments)
7. [Analytics & Reports](#analytics--reports)
8. [Administration](#administration)
9. [Best Practices](#best-practices)
10. [Troubleshooting](#troubleshooting)
11. [Contact Information](#contact-information)

---

## Getting Started

### Accessing the Barber Shop System

**GUI Mode:**
1. Launch the application → **Campus Services** → **Barber Shop**
2. Login with university credentials
3. Multi-tab interface loads with Appointments, Customers, Services, Staff, Finance, Analytics, Reports, and Refunds tabs

**CLI Mode:**
1. Navigate to **Main Menu** → **Barber Shop**
2. Select from: Services, Staff, Appointments, or Reports submenus

### Opening Hours

- **Time Slots**: 30-minute intervals from 9:00 AM to 5:30 PM
- **Total Slots**: 18 per barber per day
- **Available Slots**: 09:00, 09:30, 10:00, 10:30, 11:00, 11:30, 12:00, 12:30, 13:00, 13:30, 14:00, 14:30, 15:00, 15:30, 16:00, 16:30, 17:00, 17:30

---

## Appointments

### Booking an Appointment

**Via GUI:**
1. Navigate to the **Appointments** tab
2. Select a service from the dropdown
3. Choose a barber (or select "Any Available")
4. Pick a date and time slot
5. Add any special requests or notes
6. Click **Book Appointment**
7. Receive a unique appointment number

**Via CLI:**
1. Select **Appointments** → **Book Appointment**
2. Follow the interactive prompts for service, barber, date, and time
3. Confirm the booking

### Appointment Lifecycle

| Stage | Status | Description |
|-------|--------|-------------|
| **Booked** | `scheduled` | Appointment created, awaiting arrival |
| **Arrived** | `checked_in` | Customer checked in at the shop |
| **In Progress** | `in_progress` | Barber has started the service |
| **Done** | `completed` | Service finished |
| **Payment** | `paid` | Payment processed and receipt sent |

**Alternative Flows:**
- **Cancel**: Cancel with a reason (tracked for analytics)
- **Reschedule**: Move to a new date, time, or barber
- **No-Show**: Mark as no-show (tracked per customer)

### Recurring Appointments

1. Navigate to **Appointments** → **Create Recurring**
2. Select service, barber, and preferred time
3. Set frequency (weekly) and end date
4. System auto-generates appointments

### Waitlist

- If your preferred slot is full, join the waitlist
- Receive notification when a slot opens
- Confirm within 30 minutes to secure the spot

---

## Customers

### Customer Profiles

The system tracks detailed customer information:

| Field | Description |
|-------|-------------|
| **Name & Contact** | Name, email, phone, student ID |
| **Preferences** | Hair type, preferred style, allergies |
| **Visit History** | Total visits, last visit, total spent |
| **Favourite** | Preferred barber and service |
| **VIP Status** | Automatically flagged after 10+ visits |

### Managing Your Profile

1. Navigate to the **Customers** tab
2. Search by name, email, phone, or ID
3. View or update your preferences
4. Review appointment history and notes

### Customer Notes

Staff can add categorised notes to customer profiles for personalised service on future visits.

---

## Services

### Available Services

| Service | Duration | Description |
|---------|----------|-------------|
| **Standard Haircut** | 30 min | Classic haircut |
| **Beard Trim** | 15-30 min | Beard shaping and trimming |
| **Haircut & Beard** | 45-60 min | Full grooming package |
| **Traditional Shave** | 30 min | Hot towel straight razor shave |
| **Hair Wash & Style** | 30 min | Wash, dry, and style |
| **Buzz Cut** | 15-30 min | All-over clipper cut |
| **Fade Cut** | 30 min | Graduated fade styling |
| **Line Up** | 15 min | Edge and hairline clean-up |
| **Kids Haircut** | 30 min | Children's haircut |
| **Senior Haircut** | 30 min | Discounted senior rate |
| **Hair Colouring** | 60+ min | Professional colour treatment |
| **Head Shave** | 30 min | Full head shave |

### Service Packages

Bundled services at a discount (e.g., "Full Grooming Package" combining haircut, beard trim, and wash). View available packages under **Services** → **Service Packages**.

### Add-On Services

Optional extras such as beard oil, styling cream, or hot towel treatment can be added to any appointment.

---

## Staff Management

### Viewing Staff

The **Staff** tab displays all barbers with:
- Staff ID and employee ID
- Name and specialties
- Contact information
- Current status

### Staff Schedules

- View working hours by day of the week
- Check barber availability for specific dates
- See appointment load per barber

### Performance Metrics (Admin/Staff)

Via CLI: **Reports** → **Staff Performance**

| Metric | Description |
|--------|-------------|
| Total Appointments | Number of appointments handled |
| Completion Rate | Completed vs cancelled/no-show ratio |
| Revenue Generated | Total earnings from services |
| Tips Received | Total tips earned |
| Average Rating | Customer feedback score |

---

## Finance & Payments

### Processing Payments

1. Complete the service and mark as **Completed**
2. Click **Process Payment** in the Appointments tab
3. Select payment method:
   - **Cash**
   - **Card**
   - **Student Account** (linked to university finance system)
4. Optionally add tip amount
5. Confirm payment
6. Receipt sent via email automatically

### Gift Cards

**Creating a Gift Card:**
1. Navigate to **Finance** → **Create Gift Card**
2. Set the value and optional recipient details
3. System generates a unique gift card code
4. Gift card can be redeemed at payment

**Redeeming a Gift Card:**
1. Navigate to **Finance** → **Redeem Gift Card**
2. Enter the gift card code
3. Check balance and apply to payment

### Discounts

Staff can apply percentage or fixed-amount discounts to appointments with a recorded reason.

### Refunds

1. Navigate to the **Refunds** tab
2. Select a transaction from the list
3. Click **Process Refund**
4. Choose refund method (cash, card, or student account)
5. Refund receipt sent via email
6. Refund data exportable to CSV

### Cash Drawer Management

Track opening and closing cash amounts with automatic discrepancy calculation.

---

## Analytics & Reports

### Dashboard (Analytics Tab)

Real-time statistics including:
- Today's appointments (total, completed, scheduled, no-show)
- Daily revenue and tips
- Active staff count
- Monthly statistics overview

### Available Reports

| Report | Description |
|--------|-------------|
| **Sales Report** | Revenue by date range, service, and staff |
| **Staff Performance** | Appointments, completion rate, tips, ratings |
| **Service Popularity** | Booking count and revenue per service |
| **Customer Retention** | New vs returning customers, retention rate |
| **Peak Hours** | Busiest time slots for capacity planning |
| **Daily Revenue** | Transactions, tips, and daily totals |
| **Financial Report** | Revenue breakdown and outstanding payments |
| **Admin Report** | Comprehensive weekly overview |

### Exporting Reports

- **PDF Export**: Generate downloadable PDF reports
- **CSV Export**: Export refund data to CSV
- **Email**: Send reports to staff or management
- **Scheduled Reports**: Configure automated delivery (daily, weekly, monthly)

---

## Administration

### Managing Services (Admin/Staff)

1. Navigate to the **Services** tab
2. **Add Service**: Enter name, type, price, duration, and description
3. **Update Service**: Select and modify existing service details
4. **Toggle Availability**: Activate or deactivate services

### Commission Management

- Set percentage-based commission rates per barber
- Calculate commissions by service or overall
- Generate commission reports by date range

### Audit Log

All system actions are logged with:
- Action type (create, update, delete, payment, refund)
- User ID and timestamp
- Relevant details (amounts, statuses)

Access the audit log via **Analytics** → **View Audit Log**.

---

## Best Practices

1. **Book in advance** - Popular time slots fill quickly, especially lunch hours
2. **Arrive on time** - Late arrivals may lose their slot
3. **Update preferences** - Keep your hair type and style notes current for better service
4. **Cancel early** - Cancel at least 2 hours before your appointment
5. **Provide feedback** - Rate your experience to help improve service quality
6. **Use recurring bookings** - Set up weekly appointments for consistent grooming

---

## Troubleshooting

### Common Issues

**Cannot book an appointment:**
- Check that the barber is available on your selected date
- Verify the time slot is not already taken or blocked
- Ensure you are logged in

**Payment failed:**
- If using student account, check your balance
- Try an alternative payment method (cash or card)
- Contact the front desk for manual processing

**Appointment not showing:**
- Refresh the appointments list
- Check the date filter is set correctly
- Verify the appointment was confirmed (not waitlisted)

**Gift card not working:**
- Verify the gift card code is correct
- Check the remaining balance
- Ensure the gift card has not expired

---

## Contact Information

**Campus Barber Shop**
- **Phone**: (555) 123-HAIR
- **Email**: barber@university.edu
- **Location**: Student Centre, Ground Floor

**Appointments**
- **Online**: Via GUI or CLI system
- **Walk-ins**: Subject to availability

---

**Last Updated**: February 2026
**Module**: `university_system/modules/domain/barber/`
**Support**: barber@university.edu | (555) 123-HAIR
