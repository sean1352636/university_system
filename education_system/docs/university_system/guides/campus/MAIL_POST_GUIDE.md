# Mail/Post System - User Guide

## Overview

The Mail/Post system manages the university's physical mail and package services, including package receiving and tracking, PO box rentals, mail forwarding, and financial transactions. It provides real-time tracking, automated email notifications, and full integration with the university finance system for seamless payment processing.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Package Tracking](#package-tracking)
3. [PO Box Rental](#po-box-rental)
4. [Mail Forwarding](#mail-forwarding)
5. [Payments & Fees](#payments--fees)
6. [Administration](#administration)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)
9. [Contact Information](#contact-information)

---

## Getting Started

### Accessing Mail/Post Services

**GUI Mode:**
1. Launch the application → **Campus Services** → **Mail/Post**
2. Login with university credentials
3. Multi-tab interface loads: Packages, My Mail, PO Box, Forwarding, Admin

**CLI Mode:**
1. Navigate to **Main Menu** → **Mail/Post Services**
2. Select from:
   - Track Package
   - View My Packages
   - Receive New Package (staff)
   - Collect Package (staff)
   - Package Statistics (staff)
   - Manage PO Boxes

### Service Hours

- **Mail Room**: Monday-Friday, 8:00 AM - 6:00 PM
- **PO Box Access**: 24/7 with university ID
- **Package Collection**: During mail room hours

---

## Package Tracking

### Tracking a Package

**GUI:**
1. Navigate to the **My Mail** tab
2. Enter your tracking number in the search field
3. Or view all your packages in the list

**CLI:**
1. Select **Track Package**
2. Enter your tracking number
3. View full package details

### Tracking Number Format

All packages receive a unique tracking number: `UNI-YYYYMMDD-XXXXXXXX`

### Package Information Displayed

| Field | Description |
|-------|-------------|
| **Tracking Number** | Unique identifier |
| **Recipient** | Name and email |
| **Sender** | Sender name and address |
| **Package Type** | Letter, parcel, registered, etc. |
| **Status** | Current status (see below) |
| **Received Date** | When the package arrived |
| **Storage Location** | Where the package is stored |
| **Fees** | Any accrued storage charges |

### Package Statuses

| Status | Description |
|--------|-------------|
| **Received** | Package logged into the system |
| **Stored** | Package in storage awaiting collection |
| **Notified** | Collection notification sent to recipient |
| **Collected** | Package picked up by recipient |
| **Returned** | Package returned to sender |
| **Forwarded** | Package forwarded to another address |

### Package Types

| Type | Storage Fee |
|------|------------|
| **Letter** | Free |
| **Small Parcel** | Free |
| **Large Parcel** | £2.50 |
| **Registered** | £1.00 |
| **Express** | Free |
| **International** | £3.00 |

### Storage Fees

- **First 7 days**: Free storage for all package types
- **After 7 days**: £0.50 per day additional charge
- **Base fee**: Charged at reception based on package type (see table above)

---

## PO Box Rental

### Available PO Boxes

The university offers 50 PO boxes (PO-001 to PO-050) in three sizes:

| Size | Monthly Fee | Description |
|------|------------|-------------|
| **Standard** | £10.00/month | Suitable for letters and small items |
| **Medium** | £12.00/month | Fits larger envelopes and small parcels |
| **Large** | £15.00/month | Accommodates parcels and larger items |

### Renting a PO Box (GUI)

1. Navigate to the **PO Box** tab
2. Click **Rent PO Box**
3. Select an available box from the list
4. Set the rental period (months)
5. Choose your payment method:
   - Cash
   - Card
   - Student Account (balance displayed)
6. Confirm the rental
7. Receipt email sent automatically

### Renting a PO Box (CLI)

1. Select **Manage PO Boxes** → **Rent a PO box**
2. View available boxes and select one
3. Enter rental duration (months)
4. Confirm and pay

### Managing Your PO Box

**View your box:**
- GUI: PO Box tab shows your box details (number, size, fee, rental period)
- CLI: **Manage PO Boxes** → **View my PO box**

**Release your box:**
- GUI: Click **Release Box** and confirm
- CLI: **Manage PO Boxes** → **Cancel PO box rental**

**Auto-renewal:**
- Enabled by default
- PO box rentals auto-renew at the end of the rental period
- Disable via account settings

---

## Mail Forwarding

### Setting Up Forwarding

1. Navigate to the **Forwarding** tab
2. Enter the forwarding address
3. Select forwarding type:
   - **Domestic**: £5.00 setup fee
   - **International**: £15.00 setup fee
4. Set the start date (defaults to today)
5. Optionally set an end date
6. Click **Setup Forwarding**
7. Choose payment method and confirm
8. Receipt email sent automatically

### Forwarding Fees

| Type | Setup Fee |
|------|----------|
| **Domestic** | £5.00 |
| **International** | £15.00 |

### Cancelling Forwarding

1. Navigate to the **Forwarding** tab
2. Click **Cancel Forwarding**
3. Confirm the cancellation
4. Status changes to "Cancelled"
5. Mail delivery resumes to your original address

---

## Payments & Fees

### Fee Summary

| Service | Fee |
|---------|-----|
| Letter storage | Free |
| Small Parcel storage | Free |
| Large Parcel storage | £2.50 |
| Registered storage | £1.00 |
| Express storage | Free |
| International storage | £3.00 |
| Daily storage (after 7 days) | £0.50/day |
| PO Box - Standard | £10.00/month |
| PO Box - Medium | £12.00/month |
| PO Box - Large | £15.00/month |
| Domestic Forwarding | £5.00 setup |
| International Forwarding | £15.00 setup |

### Payment Methods

| Method | Description |
|--------|-------------|
| **Cash** | Pay at the mail room counter |
| **Card** | Debit or credit card |
| **Student Account** | Deduct from university finance account |

For student account payments, the system verifies your balance before processing.

### Transaction References

All transactions receive a unique reference: `REF-XXXXXXXXXXXX`

---

## Administration

### Receiving Packages (Staff)

**GUI:**
1. Navigate to the **Packages** tab
2. Fill in the package form:
   - Recipient ID and Name (required)
   - Recipient Email
   - Sender Name
   - Storage Location
   - Package Type
3. Click **Submit**
4. System generates tracking number
5. Notification email sent to recipient automatically

**CLI:**
1. Select **Receive New Package**
2. Enter recipient details, sender information, and package type
3. Confirm the entry
4. Tracking number displayed

### Collecting Packages (Staff)

**GUI:**
1. Select the package from the pending list
2. Click **Mark Collected**
3. Confirm the collection
4. Package status updates to "Collected"

**CLI:**
1. Select **Collect Package**
2. Enter the tracking number
3. Confirm the person collecting
4. Process any outstanding storage fees
5. Package marked as collected

### Package Notifications

Staff can send notification emails to recipients:
1. Select a package in the list
2. Click **Send Notification**
3. Email sent to the recipient's email address
4. Notification status updated

### Statistics (Staff)

View package statistics including:
- Total packages in the system
- Breakdown by status (received, stored, collected, etc.)
- Breakdown by package type

### Reports (Admin)

1. Navigate to the **Admin** tab
2. Select a date for the report
3. Click **Daily Report** to generate:
   - Packages received and collected counts
   - Storage fees collected
   - Total daily revenue
4. Click **Email Report** to send to administrators

---

## Best Practices

1. **Check your mail regularly** - Collect packages promptly to avoid storage fees
2. **Update your email** - Ensure your email is current to receive notifications
3. **Keep tracking numbers** - Save your tracking number for reference
4. **Set up forwarding early** - If going away, set up forwarding before you leave
5. **Collect within 7 days** - Free storage period is 7 days for all packages
6. **Check PO box** - If you have a PO box, check it regularly
7. **Report missing packages** - Contact the mail room immediately if a notified package is missing

---

## Troubleshooting

### Common Issues

**Tracking number not found:**
- Verify the tracking number format (UNI-YYYYMMDD-XXXXXXXX)
- Check for typos in the tracking number
- The package may not yet be logged - check again later
- Contact the mail room for assistance

**Storage fees higher than expected:**
- Fees accrue at £0.50/day after the 7-day free period
- Check the received date to calculate days stored
- Contact the mail room for fee disputes

**Cannot rent a PO box:**
- Verify there are available boxes in your preferred size
- Ensure you are logged in
- Check that your payment method has sufficient funds

**Not receiving notification emails:**
- Verify your email address is correct in your profile
- Check spam/junk folders
- Contact the mail room to update your email

**PO box not accessible:**
- Ensure your rental is still active (check expiry date)
- Verify your university ID is working
- Contact security or mail room during office hours

---

## Contact Information

**University Mail Room**
- **Phone**: (555) 123-MAIL
- **Email**: mailroom@university.edu
- **Location**: Student Services Building, Ground Floor

**Mail Room Hours**
- Monday-Friday: 8:00 AM - 6:00 PM
- Saturday: 9:00 AM - 12:00 PM
- Sunday: Closed

**PO Box Access**
- 24/7 with valid university ID

---

**Last Updated**: February 2026
**Module**: `university_system/modules/domain/mail/`
**Support**: mailroom@university.edu | (555) 123-MAIL
