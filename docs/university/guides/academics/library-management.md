# Library Management Guide

This guide covers book management, checkout/return operations, reservations, digital library, fines, analytics, and administration within the University Management System.

## Table of Contents

- [Overview](#overview)
- [Getting Started](#getting-started)
- [Book Management](#book-management)
- [Checkout & Returns](#checkout--returns)
- [Reservations](#reservations)
- [Search & Discovery](#search--discovery)
- [Fines & Payments](#fines--payments)
- [Reading Lists](#reading-lists)
- [Reviews & Ratings](#reviews--ratings)
- [Digital Library](#digital-library)
- [Barcode & Library Cards](#barcode--library-cards)
- [Reports & Analytics](#reports--analytics)
- [Notifications](#notifications)
- [Import & Export](#import--export)
- [System Maintenance](#system-maintenance)
- [Settings](#settings)

## Overview

The Library Management module provides comprehensive library operations including catalog management, circulation (checkout/return/renewal), reservations, digital resource management, fine processing, and analytics. It integrates with the email system for notifications and the finance system for payment processing.

**Key files:**
- Services: `modules/domain/academics/services/library/`
- GUI: `modules/domain/academics/gui/library/`

## Getting Started

### CLI Access

From the main menu, select **Library Management**. The CLI menu is organized into sections:

- **Book Management**: Add, import, update, delete books
- **Book Discovery**: Search, view details, get recommendations
- **Circulation**: Check out, return, renew books
- **Reservations**: Reserve books and manage queue
- **Reading Lists & Social**: Lists, reviews, achievements
- **Digital Library**: Manage digital resources
- **Analytics & Reports**: Dashboard, reports, exports
- **System Administration**: Notifications, backup, settings, audit

### GUI Access

The GUI uses a sidebar navigation with these sections:

| Section | Purpose |
|---------|---------|
| Dashboard | Statistics overview and quick actions |
| Books | Catalog management |
| Checkout/Return | Circulation operations |
| Reservations | Reservation queue management |
| Search | Advanced search and filtering |
| Fines | Fine management and payments |
| Overdue | Overdue book tracking |
| Reports | Report generation |
| Reading Lists | List creation and management |
| Reviews | Book review moderation |
| Digital Library | Digital resource management |
| Analytics | Charts and metrics |
| Finance | Payment integration |
| Barcode/Cards | Barcode and card generation |
| Import/Export | Bulk data operations |
| Maintenance | Database optimization |
| Settings | System configuration |

## Book Management

### Adding a Book

1. Navigate to **Books** > **Add Book**
2. Enter book details:
   - **Title** and **Author** (required)
   - **ISBN** (optional but recommended)
   - Publisher, Category, Year Published
   - Description, Location (shelf/section)
   - Reading Level, Tags
3. If an ISBN is provided, click **Fetch Metadata** to auto-fill from OpenLibrary or Google Books APIs
4. Save the book

### ISBN Auto-Fetch

The system can automatically retrieve book metadata:
- **OpenLibrary API**: Title, author, publisher, year, description
- **Google Books API**: Cover images and additional metadata

### Bulk Import

Import books from CSV files:
1. Select **Import** from the menu
2. Choose a CSV file with columns: title, author, isbn, publisher, category, year
3. The system validates and imports records
4. A summary shows successful imports and any errors

### Book Statuses

| Status | Description |
|--------|-------------|
| available | Ready for checkout |
| checked_out | Currently borrowed |
| reserved | Held for a reservation |
| maintenance | Being repaired or processed |
| lost | Reported lost |

## Checkout & Returns

### Checking Out a Book

1. Navigate to **Checkout/Return**
2. Select or search for the book
3. Enter the borrower's user ID
4. The system checks eligibility:
   - Maximum loans not exceeded (default: 5)
   - No overdue books
   - Outstanding fines below threshold (default: $10)
5. If eligible, the book is checked out with:
   - Default loan period: 14 days
   - Due date calculated automatically
6. A confirmation email is sent to the borrower

### Returning a Book

1. Select the active loan
2. Click **Return**
3. The system:
   - Calculates any overdue fines
   - Updates the book status to "available"
   - Notifies the next person in the reservation queue (if any)
   - Sends a return confirmation email

### Renewing a Book

1. Select an active loan
2. Click **Renew**
3. Rules:
   - Maximum renewals: 2 (configurable)
   - Cannot renew if the book is reserved by another user
   - Due date extends by the standard loan period
   - Existing fines are not waived by renewal

### Loan Lifecycle

```
Available → Checked Out → [Renewed x2] → Returned → Available
                ↓
            Overdue (fines accrue daily)
```

## Reservations

### Reserving a Book

1. Navigate to **Reservations**
2. Search for the desired book
3. Click **Reserve**
4. The reservation is added to the queue with a priority order

### Reservation Rules

- Books must be currently unavailable (checked out or reserved by others)
- Reservations expire after 3 days (configurable) once the book becomes available
- Notifications are sent when a reserved book becomes available

### Managing Reservations

Administrators can:
- View the reservation queue
- Cancel reservations
- Adjust priority order
- Manually process reservations

## Search & Discovery

### Basic Search

Search by:
- Title
- Author
- ISBN
- Category

### Advanced Search

Combine multiple criteria:
- Title contains
- Author name
- Category filter
- Year range
- Availability status
- Reading level

### Saved Searches

Save frequently used search queries for quick access later.

### Recommendations

The recommendation engine suggests books based on:
- Borrowing history
- Category preferences
- Similar users' reading patterns
- Confidence scoring

## Fines & Payments

### Fine Calculation

Fines accrue automatically for overdue books:
- **Rate**: $0.50 per day (configurable)
- **Calculation**: Days overdue x daily rate
- Fines stop accruing when the book is returned

### Paying Fines

1. Navigate to **Fines**
2. Select the fine to pay
3. Choose payment method:
   - **Direct Payment**: Cash or card
   - **Student Finance Account**: Deducted from student account balance
   - **Account Top-Up**: Add funds to student account first, then pay
4. A receipt is generated

### Fine Adjustments

Administrators can:
- Waive fines with documented reason
- Adjust fine amounts
- Process refunds for incorrect fines
- Export fine records to CSV

### Finance Integration

Fine payments sync with the main Finance module:
- Payments recorded in the finance system
- Student account balances updated
- Transaction history maintained

## Reading Lists

### Creating a Reading List

1. Navigate to **Reading Lists**
2. Click **Create List**
3. Enter:
   - List name and description
   - Category
   - Target reading level
   - Visibility: Public or Private
   - Collaborative: Allow others to add books
4. Add books to the list

### Collaborative Lists

Enable collaborative mode to allow other users to:
- Add books to the list
- Add notes to entries
- Reorder items

### Sharing

Public lists are visible to all library users. Share lists directly via the interface.

## Reviews & Ratings

### Submitting a Review

1. Navigate to **Reviews**
2. Select a book
3. Rate from 1-5 stars
4. Write a review (optional)
5. Submit for moderation

### Moderation

If review moderation is enabled (default: on):
1. New reviews enter "pending" status
2. Moderators approve or reject reviews
3. Approved reviews become visible
4. Rejected reviews include a reason

### Helpful Votes

Users can mark reviews as helpful, which influences the review display order.

## Digital Library

### Adding Digital Resources

1. Navigate to **Digital Library**
2. Click **Add Resource**
3. Upload the file (PDF, EPUB, MOBI, TXT)
4. Enter metadata: title, author, category, description
5. Set access level: Public or Restricted

### Linking to Physical Books

Associate digital copies with physical book records:
1. Select a digital resource
2. Click **Link to Physical Book**
3. Choose the corresponding book from the catalog

### Access Control

- **Public**: Available to all authenticated users
- **Restricted**: Requires specific permissions

### Download Statistics

Track downloads per resource, including:
- Total download count
- Download trends over time
- Most popular resources

## Barcode & Library Cards

### Book Barcodes

Generate barcodes for physical books:
1. Navigate to **Barcode/Cards**
2. Select a book
3. Click **Generate Barcode**
4. Print the barcode label

### QR Codes

Generate QR codes that link to book details in the system.

### Library Cards

Generate library cards for students:
1. Select a student
2. Click **Generate Library Card**
3. The card includes:
   - Student name and ID
   - Barcode for scanning
   - Expiration date

### Bulk Generation

Generate barcodes or library cards in batch for multiple books or students.

## Reports & Analytics

### Available Reports

| Report | Description |
|--------|-------------|
| Collection Overview | Inventory breakdown by status and category |
| Circulation Summary | Checkout/return trends and statistics |
| Overdue Books | List of all overdue items with borrower details |
| User Activity | Borrowing patterns per user |
| Popular Books | Most checked-out titles |
| Fine Collection | Revenue from fines with payment method breakdown |
| Library Card Usage | Card utilization statistics |
| System Health | Database integrity and performance metrics |
| Maintenance Activity | Recent maintenance operations |

### Generating Reports

1. Navigate to **Reports**
2. Select the report type
3. Configure parameters (date range, filters)
4. Generate the report

### Export Options

- Display in GUI window
- Save as PDF, CSV, or TXT
- Email directly to administrators
- Open in a separate window

### Analytics Dashboard

The analytics section provides:
- Collection overview charts
- Circulation trend graphs
- User activity metrics
- Category analysis
- Matplotlib/Seaborn visualizations

## Notifications

### Automated Notifications

| Notification | Trigger |
|-------------|---------|
| Checkout Confirmation | Book checked out |
| Return Confirmation | Book returned |
| Due Date Reminder | Approaching due date |
| Overdue Alert | Book overdue |
| Reservation Available | Reserved book becomes available |
| Fine Notice | Fine exceeds threshold |

### Configuration

Enable or disable notification types from **Settings**:
- Email notifications (default: enabled)
- SMS notifications (default: disabled)

### Calendar Integration

Due dates can be exported as calendar events for student reminders.

## Import & Export

### Bulk Import

Import books from CSV:
- Map CSV columns to book fields
- Validate data before import
- Progress tracking for large imports
- Error reporting for failed records

### Bulk Export

Export the entire catalog or filtered results to CSV:
- All book fields included
- Configurable column selection

### System Backup

Create a complete backup of library data:
1. Navigate to **Maintenance** > **Backup**
2. The system creates a timestamped database backup

### System Restore

Restore from a previous backup:
1. Select the backup file
2. Confirm the restoration
3. The system replaces current data with backup data

## System Maintenance

### Database Optimization

Run periodic optimization:
- **VACUUM**: Reclaim unused space
- **ANALYZE**: Update query statistics
- **REINDEX**: Rebuild indexes

### Integrity Checks

Verify database consistency:
- Check foreign key relationships
- Validate data constraints
- Identify orphaned records

### Automated Tasks

- **Expired Reservation Cleanup**: Remove expired reservations
- **Overdue Status Update**: Mark overdue books automatically
- **Fine Calculation**: Batch calculate outstanding fines
- **Archive Old Records**: Move old completed loans to archive
- **Cache Clearing**: Clean temporary data

### Audit Log

View all system actions:
- User, action, timestamp
- Table and record affected
- Success/failure status

## Settings

### Configurable Parameters

| Setting | Default | Range | Description |
|---------|---------|-------|-------------|
| `loan_period_days` | 14 | 1-365 | Standard loan duration |
| `max_loans` | 5 | 1-50 | Maximum concurrent loans per user |
| `fine_per_day` | 0.50 | 0.0-10.0 | Daily overdue fine amount |
| `reservation_period_days` | 3 | 1-30 | Days to collect a reserved book |
| `max_renewals` | 2 | 0-10 | Maximum renewals per loan |
| `email_notifications` | true | - | Enable email notifications |
| `sms_notifications` | false | - | Enable SMS notifications |
| `auto_backup` | true | - | Enable automatic backups |
| `review_moderation` | true | - | Require review approval |
| `recommendation_engine` | true | - | Enable book recommendations |
| `social_features` | true | - | Enable reading lists and reviews |
| `barcode_scanning` | false | - | Enable barcode scanning |

Settings are stored in the `library_settings` database table and can be modified from the Settings section in either the CLI or GUI.

### Permissions

| Permission | Description |
|-----------|-------------|
| `manage_books` | Add, update, delete books |
| `view_books` | Search and view book information |
| `manage_loans` | Checkout/return/renew operations |
| `checkout_books` | Perform checkouts |
| `generate_reports` | Create reports |
| `view_reports` | View generated reports |
| `system_config` | Modify system settings |
