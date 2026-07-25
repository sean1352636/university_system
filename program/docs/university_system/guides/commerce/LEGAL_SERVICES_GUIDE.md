# Legal Services - User Guide

## Overview

The Legal Services system provides university students and staff with access to legal consultations, case management, document handling, and various legal specialisations. It supports case tracking from creation through resolution, fee management with student account integration, invoice generation, and comprehensive reporting.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Legal Consultations](#legal-consultations)
3. [Case Management](#case-management)
4. [Documents](#documents)
5. [Fees & Payments](#fees--payments)
6. [Reports](#reports)
7. [Refunds](#refunds)
8. [Administration](#administration)
9. [Best Practices](#best-practices)
10. [Troubleshooting](#troubleshooting)
11. [Contact Information](#contact-information)

---

## Getting Started

### Accessing Legal Services

**GUI Mode:**
1. Launch the application → **Student Services** → **Legal Services**
2. Login with university credentials
3. Multi-tab interface loads: Cases, Consultations, Documents, Payments, Reports, Refunds

**CLI Mode:**
1. Navigate to **Main Menu** → **Legal Services**
2. Select from the available menu options

### Available Legal Areas

The university legal service covers a wide range of practice areas to support students and staff with legal matters.

---

## Legal Consultations

### Service Types & Fees

| Service | Fee | Duration |
|---------|-----|----------|
| **30-Minute Consultation** | £25.00 | 30 min |
| **60-Minute Consultation** | £45.00 | 60 min |
| **Document Review** | £35.00 | Varies |
| **Contract Review** | £50.00 | Varies |
| **Case Filing** | £75.00 | Varies |
| **Immigration Consultation** | £60.00 | 60 min |
| **IP Consultation** | £55.00 | 60 min |
| **Criminal Consultation** | £70.00 | 60 min |
| **Family Law Consultation** | £50.00 | 60 min |
| **Tenant Dispute** | £40.00 | 30 min |
| **Employment Consultation** | £45.00 | 60 min |
| **Consumer Rights** | £30.00 | 30 min |
| **Pro Bono** | Free | Varies |

### Booking a Consultation

1. Navigate to the **Consultations** tab
2. Select the service type from the dropdown
3. Choose your preferred date and time
4. Add any notes or specific concerns
5. Review the fee and confirm
6. Receive a consultation reference number

### Consultation Statuses

| Status | Description |
|--------|-------------|
| **Scheduled** | Consultation booked, awaiting appointment |
| **Completed** | Consultation held successfully |
| **Cancelled** | Consultation cancelled |
| **No-Show** | Client did not attend |

---

## Case Management

### Case Types

| Type | Description |
|------|-------------|
| **Consultation** | General legal advice |
| **Immigration** | Visa, work permits, immigration matters |
| **IP/Patent** | Intellectual property and patent issues |
| **Criminal** | Criminal defence and advice |
| **Family Law** | Family-related legal matters |
| **Pro Bono** | Free legal assistance for eligible cases |
| **Tenant Dispute** | Housing and tenancy issues |
| **Employment** | Workplace rights and disputes |
| **Consumer Rights** | Consumer protection matters |
| **Contract Review** | Contract analysis and advice |

### Creating a Case

1. Navigate to the **Cases** tab
2. Click **New Case**
3. Fill in the case form:
   - **Client Name** (required)
   - **Client ID** (required)
   - **Client Email**
   - **Case Type** (required)
   - **Case Title** (required)
   - **Description** - Detailed description of the legal matter
4. Click **Submit**
5. System generates a unique case number

### Case Statuses

| Status | Description |
|--------|-------------|
| **Open** | Case created, initial review |
| **In Progress** | Actively being worked on |
| **Pending Review** | Awaiting decision or additional information |
| **Closed** | Case resolved or concluded |

### Viewing Cases

- Browse all cases in the case list with filtering options
- Click a case to view full details including:
  - Case number, client, type, and title
  - Description and assigned advisor
  - Status and timeline
  - Associated consultations and documents
  - Fee information

---

## Documents

### Document Management

The system supports document storage and tracking for each case:

**Uploading Documents:**
1. Navigate to the **Documents** tab
2. Select the related case
3. Click **Upload Document**
4. Enter document type (e.g., Evidence, Contract, ID, Correspondence)
5. Select the file to upload
6. Document is stored with version tracking

**Viewing Documents:**
1. Select a case from the case list
2. View all associated documents with:
   - Document type
   - Version number
   - Upload date
   - File details

**Document Types:**
- Evidence
- Contracts
- Identification documents
- Correspondence
- Court filings
- Agreements
- Reference materials

---

## Fees & Payments

### Fee Calculation

Fees are automatically calculated based on:
- Service type selected
- Consultation duration
- Any additional filing fees

The fee display updates dynamically when you select a service type.

### Processing Payments

1. Navigate to the **Payments** tab
2. View outstanding payment records
3. Select a payment to process
4. Choose payment method:
   - **Cash**
   - **Card**
   - **Student Account** (balance displayed and verified)
5. Confirm the payment
6. Transaction recorded with reference number

### Generating Invoices

1. Navigate to **Payments** → **Generate Invoice**
2. System creates a detailed invoice including:
   - Client details
   - Service description
   - Fee breakdown
   - Payment terms
3. Options:
   - **Save Invoice** - Save to file
   - **Email Invoice** - Send directly to client's email

### Payment Statuses

| Status | Description |
|--------|-------------|
| **Pending** | Payment not yet received |
| **Paid** | Payment processed successfully |
| **Refunded** | Payment returned to client |

---

## Reports

### Generating Reports

1. Navigate to the **Reports** tab
2. Click **Generate Admin Report** for a comprehensive overview including:
   - Total cases by status
   - Revenue by service type
   - Consultation statistics
   - Outstanding payments
3. Reports can be:
   - Viewed in the report display area
   - Saved to file
   - Emailed to administrators

### Email Reports

1. Click **Email Admin Report**
2. System sends the comprehensive report to the administrator email
3. Confirmation message displayed

---

## Refunds

### Processing a Refund

1. Navigate to the **Refunds** tab
2. Search for the payment by transaction ID, client, or reference
3. Select the payment record from the list
4. Click **Process Refund**
5. Choose the refund method:
   - **Cash** - Refund in cash
   - **Card** - Refund to original card
   - **Student Account** - Credit back to finance account
6. Confirm the refund amount
7. Refund reference generated (format: LEGAL-REFUND-YYYYMMDDHHMMSS)
8. Refund receipt sent via email

### Viewing Refund Details

- Transaction list shows colour-coded status (red for refunded, green for completed)
- Click **View Details** to see full transaction and client information
- Search and filter by transaction ID, client, type, or status

### Exporting Refund Data

Click **Export to CSV** to download refund records with:
- Transaction ID, date, client ID
- Amount, type, payment method
- Status and reference number

---

## Administration

### Case Assignment

Administrators can:
- Assign cases to specific legal advisors
- Transfer cases between advisors
- Update case statuses and notes
- Close resolved cases

### Client Management

- View client consultation history
- Track total fees and payments per client
- Manage client contact information
- Identify pro bono eligible cases

### Financial Overview

- Track total revenue by service type
- Monitor outstanding payments
- Review refund history
- Generate financial reports for the legal department

---

## Best Practices

1. **Book consultations early** - Available slots fill up during term time
2. **Prepare your documents** - Bring relevant paperwork to your consultation
3. **Be specific about your issue** - This helps assign the right advisor
4. **Keep case numbers** - Reference your case number in all communications
5. **Check pro bono eligibility** - Free services are available for qualifying cases
6. **Follow up on cases** - Check your case status regularly for updates
7. **Review invoices promptly** - Settle outstanding payments to avoid delays

---

## Troubleshooting

### Common Issues

**Cannot create a case:**
- Ensure all required fields are filled (client name, ID, case type, title)
- Verify you are logged in
- Contact the legal office if the issue persists

**Payment failed:**
- If using student account, check your balance
- Try an alternative payment method
- Contact the legal services office for manual processing

**Document upload failed:**
- Check the file size is within limits
- Ensure the file format is supported
- Try uploading again or contact support

**Cannot find my case:**
- Use the search function with your case number
- Check that you are logged in with the correct account
- Contact the legal office with your reference details

---

## Contact Information

**University Legal Services**
- **Phone**: (555) 123-LEGAL
- **Email**: legal@university.edu
- **Location**: Administration Building, Room 302

**Office Hours**
- Monday-Friday: 9:00 AM - 5:00 PM
- Emergency consultations by appointment

**Pro Bono Enquiries**
- **Email**: probono@university.edu

---

**Last Updated**: February 2026
**Module**: `university_system/modules/domain/legal/`
**Support**: legal@university.edu | (555) 123-LEGAL
