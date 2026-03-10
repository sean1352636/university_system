# Equipment Management - User Guide

## Overview

The Equipment Management system handles the university's equipment rental programme, including inventory tracking, rental bookings, returns with payment processing, maintenance scheduling, and comprehensive reporting. It supports 12 equipment categories from cameras and laptops to lab equipment and sports gear, with full integration to the university finance system.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Equipment Inventory](#equipment-inventory)
3. [Renting Equipment](#renting-equipment)
4. [Returns & Payments](#returns--payments)
5. [Reports & Analytics](#reports--analytics)
6. [Administration](#administration)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)
9. [Contact Information](#contact-information)

---

## Getting Started

### Accessing the Equipment System

**GUI Mode:**
1. Launch the application → **Campus Services** → **Equipment Rental**
2. Login with university credentials
3. Multi-tab interface loads: Inventory, Rentals, Returns, Reports

**CLI Mode:**
1. Navigate to **Main Menu** → **Equipment Rental**
2. Select from the available options:
   - View Equipment Inventory
   - Book Rental
   - View All Rentals
   - Return Equipment
   - View Statistics

### First-Time Setup

1. Log in with your university credentials
2. Browse the equipment inventory
3. Select an item and complete the booking form
4. Collect the equipment at the specified time
5. Return by the due date

---

## Equipment Inventory

### Equipment Categories

| Category | Description | Examples |
|----------|-------------|---------|
| **Audio Visual** | Presentation equipment | Projectors, screens |
| **Computers** | Computing devices | Laptops, desktops, tablets |
| **Cameras** | Photography and video | DSLR cameras, camcorders |
| **Sports** | Sports and fitness gear | Tennis rackets, basketballs |
| **Tools** | Hand and power tools | Drills, measuring tools |
| **Lab Equipment** | Scientific instruments | Oscilloscopes, microscopes |
| **Projectors** | Dedicated projectors | Epson, BenQ models |
| **Lighting** | Lighting equipment | LED panels, stage lighting |
| **Furniture** | Temporary furniture | Tables, stands, chairs |
| **Event Supplies** | Event materials | Decorations, party supplies |
| **Outdoor** | Outdoor and camping | Tents, hiking gear |
| **Other** | Miscellaneous items | Specialised equipment |

### Sample Equipment

| Item | Category | Daily Rate | Available |
|------|----------|-----------|-----------|
| Canon EOS R5 | Cameras | £50.00 | 3 units |
| MacBook Pro 16" | Computers | £35.00 | 5 units |
| Sony A7 III | Cameras | £45.00 | 2 units |
| Dell XPS 15 | Computers | £30.00 | 4 units |
| Epson PowerLite 4K | Projectors | £25.00 | 6 units |
| BenQ TH685 | Projectors | £20.00 | 4 units |
| Shure SM7B Microphone | Audio Visual | £15.00 | 8 units |
| Zoom H6 Recorder | Audio Visual | £18.00 | 4 units |
| Digital Oscilloscope | Lab Equipment | £40.00 | 2 units |
| Digital Microscope | Lab Equipment | £30.00 | 3 units |
| Tennis Racket Set | Sports | £5.00 | 10 units |
| Basketball | Sports | £3.00 | 15 units |

### Browsing Equipment

**GUI:**
1. Navigate to the **Inventory** tab
2. Use the **Category Filter** dropdown to filter by type
3. View: Item Code, Name, Category, Daily Rate, Available/Total, Condition
4. Double-click an item to see full details

**CLI:**
1. Select **View Equipment Inventory**
2. Filter by category (optional)
3. View the equipment table

### Equipment Conditions

| Condition | Description |
|-----------|-------------|
| **Excellent** | Like new, no visible wear |
| **Good** | Normal operational condition |
| **Fair** | Minor wear, fully functional |
| **Needs Repair** | Not available for rental |
| **Out of Service** | Permanently unavailable |

---

## Renting Equipment

### Booking via GUI

1. Navigate to the **Rentals** tab
2. Browse available items in the left panel
3. Double-click an item to select it
4. Your name and email auto-populate from your account
5. Fill in the rental details:
   - **Department** - Your department or organisation
   - **Quantity** - Number of units (default: 1)
   - **Checkout Date** (YYYY-MM-DD, default: today)
   - **Checkout Time** (HH:MM, default: 09:00)
   - **Due Date** (YYYY-MM-DD, default: today + 7 days)
   - **Due Time** (HH:MM, default: 17:00)
   - **Purpose** - Describe your intended use
6. Click **Calculate Cost** to see the estimated total
7. Click **Book Rental**
8. Receive a rental number (format: EQR-YYYYMMDDHHMMSS)
9. Confirmation email sent automatically

### Booking via CLI

1. Select **Book Rental**
2. View available equipment and select by ID
3. Enter details (name, email, phone, student ID)
4. Specify number of rental days
5. Review and confirm the booking

### Rental Statuses

| Status | Description |
|--------|-------------|
| **Reserved** | Booked, awaiting checkout |
| **Checked Out** | Equipment in borrower's possession |
| **Returned** | Equipment returned and processed |
| **Overdue** | Past the due date |
| **Cancelled** | Booking cancelled |

---

## Returns & Payments

### Returning Equipment (GUI)

1. Navigate to the **Returns** tab
2. Select your rental from the active rentals list
3. Fill in the return form:
   - **Return Condition** (excellent, good, fair, needs_repair, out_of_service)
   - **Late Fee** (£, if returning after due date)
   - **Damage Fee** (£, if equipment was damaged)
4. Click **Return & Pay**
5. Review the payment summary:
   - Base rental amount
   - Late fee (if applicable)
   - Damage fee (if applicable)
   - Total amount due
6. Select payment method:
   - **Cash**
   - **Card**
   - **Student Account** (balance displayed)
7. Confirm payment
8. Receipt sent via email

### Extending a Rental

If you need more time:
1. Select the rental in the **Returns** tab
2. Click **Extend Rental**
3. Enter the new due date (default: +7 days from today)
4. System recalculates the total amount
5. Confirm the extension

### Cancelling a Rental

1. Select the rental in the **Returns** tab
2. Click **Cancel Rental**
3. Confirm the cancellation
4. Equipment returned to available inventory

### Checking Out Equipment

For reserved items awaiting pickup:
1. Select the rental in the **Returns** tab
2. Click **Checkout Item**
3. Status changes from "Reserved" to "Checked Out"

### Payment Methods

| Method | Description |
|--------|-------------|
| **Cash** | Pay at the equipment desk |
| **Card** | Debit or credit card |
| **Student Account** | Deduct from university finance account (balance checked) |

---

## Reports & Analytics

### Quick View Reports (GUI)

In the **Reports** tab, click any report button for an inline display:

| Report | Content |
|--------|---------|
| **Inventory Summary** | Total items, quantities, available counts |
| **Revenue Report** | Total rentals, revenue, average value, fees |
| **Popular Items** | Top 10 most rented equipment by count and revenue |
| **Overdue Rentals** | Items past their due date with borrower details |
| **Admin Report** | Comprehensive combined report |

### Report Windows

Click the corresponding button in the lower panel to open reports in a new window with additional options:
- **Save as TXT** - Export to a text file
- **Email to Admin** - Send the report to the system administrator

### Statistics (CLI)

Select **View Statistics** to see:
- Total equipment items and quantities
- Equipment breakdown by category
- Current availability
- Total revenue collected

---

## Administration

### Adding Equipment (Admin/Staff)

1. Navigate to the **Inventory** tab
2. Fill in the right panel form:
   - Item Code (unique identifier)
   - Name, Brand, Model
   - Daily Rate and Deposit
   - Quantity, Location
   - Category and Condition
   - Description
3. Click **Add Item**

### Updating Equipment (Admin/Staff)

1. Double-click an item in the inventory list
2. Modify the desired fields
3. Click **Update Item**

### Maintenance Records

Track maintenance activities including:
- Maintenance type and description
- Cost and service date
- Performed by and completion status
- Next scheduled maintenance date

### Reservations Queue

When equipment is unavailable:
- Users can request reservations
- Priority levels assigned
- Notifications sent when items become available

---

## Best Practices

1. **Book early** - Popular items (cameras, laptops) are in high demand
2. **Return on time** - Late fees apply after the due date
3. **Handle with care** - Damage fees are assessed for returned items in worse condition
4. **Specify your purpose** - Helps staff prepare the right equipment
5. **Check condition at checkout** - Note any pre-existing issues
6. **Extend before overdue** - Request an extension before the due date to avoid late fees
7. **Report issues immediately** - Contact the equipment desk if something breaks during use

---

## Troubleshooting

### Common Issues

**Cannot book equipment:**
- Verify the item has available quantity
- Ensure you are logged in
- Check that checkout date is today or later
- Fill in all required fields

**Payment failed:**
- If using student account, check your balance
- Try an alternative payment method
- Contact the equipment desk for manual processing

**Equipment not available:**
- Check other items in the same category
- Try different dates
- Submit a reservation request

**Overdue notification received:**
- Return the equipment as soon as possible
- Late fees accrue daily
- Contact the equipment desk to discuss extensions

---

## Contact Information

**University Equipment Rental**
- **Phone**: (555) 123-EQUIP
- **Email**: equipment@university.edu
- **Location**: Student Services Building, Room 105

**Equipment Desk Hours**
- Monday-Friday: 8:00 AM - 6:00 PM
- Saturday: 9:00 AM - 1:00 PM
- Sunday: Closed

---

**Last Updated**: February 2026
**Module**: `university_system/modules/domain/equipment/`
**Support**: equipment@university.edu | (555) 123-EQUIP
