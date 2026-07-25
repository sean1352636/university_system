# General Finance Management Guide

This guide covers fee structures, payment processing, payment plans, scholarships, financial reporting, budgeting, and fraud detection within the University Management System.

## Table of Contents

- [Overview](#overview)
- [Getting Started](#getting-started)
- [Fee Management](#fee-management)
- [Payment Processing](#payment-processing)
- [Payment Plans](#payment-plans)
- [Invoices & Refunds](#invoices--refunds)
- [Multi-Currency Support](#multi-currency-support)
- [Scholarships & Financial Aid](#scholarships--financial-aid)
- [Budgeting](#budgeting)
- [Financial Reporting](#financial-reporting)
- [Fraud Detection](#fraud-detection)
- [Automated Notifications](#automated-notifications)
- [Bank App](#bank-app)
- [Permissions](#permissions)

## Overview

The Finance Management module handles all financial operations for the university, including student billing, payment processing, scholarships, budgeting, and compliance reporting. It supports multiple payment methods, multi-currency transactions, and machine learning-based fraud detection.

**Key files:**
- Core: `modules/domain/finance/core/`
- Billing: `modules/domain/finance/billing/`
- Reporting: `modules/domain/finance/reporting/`
- Scholarships: `modules/domain/finance/scholarships/`
- GUI: `modules/domain/finance/gui/`

## Getting Started

### CLI Access

From the main menu, select **Finance Management**. The CLI provides 29 options organized into sections covering account management, billing, currency, analytics, scholarships, security, budgets, and collections.

### GUI Access

The Finance module has multiple GUI interfaces:

| Interface | Purpose |
|-----------|---------|
| Finance GUI | Primary manager-based interface with modular tabs |
| Finance Reporting GUI | Dashboard, analysis, reports, and settings tabs |
| Financial Aid GUI | Admin and student portals for aid management |
| Bank App | Student banking interface for deposits and transfers |

## Fee Management

### Fee Types

The system supports multiple fee categories:
- Tuition fees
- Accommodation/housing fees
- Library fees
- Lab fees
- Registration fees
- Examination fees
- Custom fee types

### Assigning Fees to Students

1. Select **Assign Fees to Students** (CLI option 1)
2. Choose a student
3. Select the fee type
4. Enter the amount
5. Set the due date
6. The fee is recorded in the `student_fees` table

### Program-Specific Fees

Configure different fee structures per program:
- Base tuition by program
- Early payment discounts
- Per-credit-hour rates

### Late Fees

The system automatically calculates late fees based on configurable rules:

| Method | Description |
|--------|-------------|
| Fixed | Flat fee applied after due date |
| Percentage | Percentage of outstanding balance |
| Daily | Per-day penalty amount |

Configure late fee rules per fee type, including grace periods before penalties begin.

### Waiving Fees

Administrators can waive late fees:
1. Select **Waive Late Fee** (CLI option 10)
2. Choose the student and fee
3. Enter a reason for the waiver
4. The waiver is logged for audit purposes

## Payment Processing

### Recording Payments

1. Select **Record Payment** (CLI option 2)
2. Choose the student
3. Enter payment details:
   - **Amount**
   - **Payment Method**: Cash, Card, Bank Transfer, Online, Check
   - **Transaction Reference**
4. The system allocates the payment against outstanding fees
5. A receipt is generated

### Payment Methods

| Method | Description |
|--------|-------------|
| Cash | In-person cash payment |
| Card | Credit/debit card (Stripe integration available) |
| Bank Transfer | Direct bank transfer |
| Online | Web-based payment portal |
| Check | Physical check payment |
| QR Code | Mobile payment via QR code |

### Stripe Integration

For card payments, the system integrates with Stripe:
- Creates payment intents
- Processes confirmation
- Records transaction IDs
- Handles payment failures

### QR Code Payments

Generate QR codes for mobile payments:
- Encodes student ID, amount, and currency
- 24-hour expiration
- Scannable from any QR reader

## Payment Plans

### Creating a Payment Plan

1. Select **Manage Payment Plans** (CLI option 7)
2. Choose a student with outstanding fees
3. Select a plan template or create a custom plan:
   - Number of installments
   - Payment frequency (weekly, monthly, quarterly)
   - Auto-payment option
4. The system generates installment records with due dates

### Payment Plan Templates

Create reusable plan structures:
- Define installment count and intervals
- Set down payment requirements
- Configure auto-payment settings

### Processing Installments

1. Select **Process Payment Plan Payment** (CLI option 8)
2. Choose the student's active plan
3. Record payment against the next due installment
4. The system updates the plan status automatically

### Plan Statuses

| Status | Description |
|--------|-------------|
| Active | Plan in progress with future installments |
| Completed | All installments paid |
| Defaulted | Missed payments beyond threshold |
| Cancelled | Plan terminated early |

## Invoices & Refunds

### Generating Invoices

1. Select **Generate Invoice** (CLI option 3)
2. Choose the student
3. Select fees to include
4. The system generates a formal invoice with:
   - Invoice number
   - Itemized fees
   - Payment terms
   - Due date

### Processing Refunds

1. Select **Process Refund** (CLI option 4)
2. Choose the student and payment
3. Select refund type:
   - **Full Refund**: Return entire payment
   - **Partial Refund**: Return a specified amount
   - **Withdrawal Refund**: Based on withdrawal policy
4. Enter reason and approve
5. The refund is recorded and the student's balance updated

## Multi-Currency Support

### Supported Currencies

GBP, USD, EUR, CAD, AUD

### Exchange Rate Management

1. Select **Update Exchange Rates** (CLI option 11)
2. Options:
   - **Automatic**: Fetch rates from external API
   - **Manual**: Enter rates for each currency pair
3. Rates are stored with timestamps in the `exchange_rates` table

### Currency Conversion Tool

1. Select **Currency Conversion Tool** (CLI option 12)
2. Enter the source currency and amount
3. Select the target currency
4. The system calculates the conversion using current rates

### Multi-Currency Payments

When recording a payment in a non-default currency:
- The system converts to the base currency using current rates
- Both the original and converted amounts are recorded
- Exchange rate at time of transaction is preserved

## Scholarships & Financial Aid

### Managing Scholarships

1. Select **Manage Scholarships** (CLI option 18)
2. Create scholarship programs with:
   - Name and description
   - Award amount
   - Eligibility criteria (GPA, financial need, etc.)
   - Application deadline
   - Number of awards available

### Financial Aid Management

1. Select **Manage Financial Aid** (CLI option 19)
2. Process aid applications:
   - Review applications
   - Approve or reject with reason
   - Set disbursement schedule

### Aid Types

| Type | Description |
|------|-------------|
| Grant | Non-repayable financial assistance |
| Loan | Repayable with terms |
| Work-Study | Earn through campus employment |
| Emergency Aid | One-time emergency assistance |

### Disbursement

Aid is disbursed according to the configured schedule:
- Lump sum or installments
- Linked to enrollment verification
- Tracked in student financial records

## Budgeting

### Budget Management

1. Select **Manage Budgets** (CLI option 25)
2. Create budget plans:
   - Define categories (revenue or expense)
   - Set allocated amounts
   - Assign to departments or programs
3. Track actual spending against budget

### Budget Reports

- **Variance Analysis**: Compare budgeted vs. actual amounts
- **Category Breakdown**: Spending by category
- **Trend Analysis**: Budget performance over time

## Financial Reporting

### Dashboard

The financial dashboard (CLI option 13) provides real-time metrics:
- Total revenue collected
- Outstanding balances
- Payment collection rate
- Recent transactions

### Available Reports

| Report | CLI Option | Description |
|--------|-----------|-------------|
| Financial Dashboard | 13 | Real-time financial overview |
| Predictive Analytics | 14 | Forecasted financial metrics |
| Financial Reports | 15 | Comprehensive financial statements |
| Outstanding Fees | 16 | Overdue accounts and amounts |
| Payment Collection | 17 | Collection rates and trends |
| Audit Report | 21 | Compliance-focused audit trail |
| Revenue Forecast | 26 | Projected future revenue |

### Exporting Reports

Reports can be exported as:
- CSV for spreadsheet analysis
- PDF for formal distribution
- Custom formats via the GUI export tools

## Fraud Detection

### ML-Based Detection

The system uses an Isolation Forest model for anomaly detection:

1. Select **Detect Payment Fraud** (CLI option 20)
2. The system analyzes recent transactions for:
   - Unusual payment amounts
   - Suspicious timing patterns
   - Abnormal payment methods
   - Geographic anomalies
3. Flagged transactions are marked with a fraud score
4. Administrators receive alerts for review

### Approval Workflows

For high-value or flagged transactions:

1. Select **Create Approval Workflow** (CLI option 22)
2. Define approval rules:
   - Transaction amount thresholds
   - Required approver roles
   - Multi-level approval chains
3. Transactions matching rules are held for approval
4. Approvers review and approve or reject

## Automated Notifications

### Setting Up Notifications

1. Select **Setup Automated Notifications** (CLI option 23)
2. Configure triggers:
   - Payment due reminders (days before due date)
   - Overdue notices
   - Payment confirmations
   - Plan installment reminders
3. Set delivery method (email)
4. Define recipient lists

### Sending Notifications

1. Select **Send Automated Notifications** (CLI option 24)
2. The system processes all pending notifications
3. Results summary shows sent count and any failures

## Bank App

The Bank App provides a standalone banking interface for students:

### Features
- View account balance
- Make deposits/top-ups
- View transaction history
- Transfer between accounts

### Integration
- Linked to the student finance account
- Deposits sync with the main finance system
- Transaction history includes all financial activity

## Permissions

| Permission | Description |
|-----------|-------------|
| `manage_finances` | Full financial management access |
| `record_payments` | Record student payments |
| `view_financial_reports` | View financial reports |
| `view_audit_logs` | Access audit trail |
| `manage_workflows` | Create and manage approval workflows |

### Role Access

| Feature | Admin | Staff | Student |
|---------|-------|-------|---------|
| Assign fees | Full | Limited | No access |
| Record payments | Full | Full | No access |
| Generate invoices | Full | Full | No access |
| Process refunds | Full | No access | No access |
| Manage scholarships | Full | View only | Apply |
| View reports | Full | Limited | Own statement |
| Fraud detection | Full | No access | No access |
| Budget management | Full | Department | No access |
| Bank App | N/A | N/A | Full |
