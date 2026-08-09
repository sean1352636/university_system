# Car Rental - User Guide

## Overview

The Car Rental system manages the university's vehicle fleet, including booking, returns, payments, maintenance tracking, and reporting. It supports multiple vehicle categories from economy to luxury, integrates with the university finance system for student account payments, and provides comprehensive fleet analytics.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Vehicle Fleet](#vehicle-fleet)
3. [Booking a Rental](#booking-a-rental)
4. [Vehicle Returns](#vehicle-returns)
5. [Payments & Refunds](#payments--refunds)
6. [Reports & Analytics](#reports--analytics)
7. [Administration](#administration)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)
10. [Contact Information](#contact-information)

---

## Getting Started

### Accessing the Car Rental System

**GUI Mode:**
1. Launch the application → **Commerce & Facilities** → **Car Rental**
2. Login with university credentials
3. Multi-tab interface loads: Vehicles, Rentals, Returns, Reports, Refunds

**CLI Mode:**
1. Navigate to **Main Menu** → **Car Rental**
2. Select from the available menu options:
   - View Vehicle Fleet
   - Book Rental
   - View All Rentals
   - Return Vehicle
   - View Statistics

### Requirements

- Valid university login
- Valid driving licence (required for booking)
- Payment method (cash, card, or student account)

---

## Vehicle Fleet

### Vehicle Categories

| Category | Description | Example Rate |
|----------|-------------|-------------|
| **Economy** | Budget-friendly compact cars | From £35/day |
| **Compact** | Small to mid-size vehicles | From £38/day |
| **Mid-Size** | Standard sedans | From £48/day |
| **Full-Size** | Larger sedans | From £55/day |
| **SUV** | Sport utility vehicles | From £70/day |
| **Luxury** | Premium vehicles | From £120/day |
| **Minivan** | Multi-passenger vehicles | Varies |
| **Pickup** | Utility vehicles | Varies |
| **Convertible** | Open-top vehicles | Varies |
| **Electric** | Fully electric vehicles | Varies |
| **Hybrid** | Hybrid fuel vehicles | Varies |

### Sample Fleet

| Vehicle | Category | Rate/Day | Transmission |
|---------|----------|----------|-------------|
| Toyota Corolla 2022 | Economy | £35 | Automatic |
| Honda Civic 2023 | Compact | £40 | Automatic (Hybrid) |
| Ford Focus 2021 | Compact | £38 | Manual |
| Toyota Camry 2022 | Mid-Size | £50 | Automatic |
| Nissan Altima 2023 | Mid-Size | £48 | Automatic (Hybrid) |
| Honda Accord 2022 | Full-Size | £55 | Automatic |
| Toyota RAV4 2023 | SUV | £70 | Automatic (Hybrid) |
| Ford Explorer 2022 | SUV | £75 | Automatic |
| BMW 3 Series 2023 | Luxury | £120 | Automatic |
| Mercedes C-Class 2023 | Luxury | £130 | Automatic |
| Ford Transit 2021 | Van | £65 | Manual |

### Browsing Vehicles (GUI)

1. Navigate to the **Vehicles** tab
2. Use the **Category Filter** dropdown to narrow results
3. View vehicle details: Registration, make, model, daily rate, status
4. Double-click a vehicle to see full specifications

### Browsing Vehicles (CLI)

1. Select **View Vehicle Fleet**
2. Optionally filter by category
3. View the table of available vehicles

---

## Booking a Rental

### Via GUI

1. Navigate to the **Rentals** tab
2. Browse available vehicles in the left panel
3. Double-click a vehicle to select it
4. Your details auto-populate (name, email from your account)
5. Fill in the rental form:
   - **Licence Number** (required)
   - **Pickup Date** (YYYY-MM-DD, default: today)
   - **Pickup Time** (HH:MM, default: 10:00)
   - **Return Date** (YYYY-MM-DD, default: tomorrow)
   - **Return Time** (HH:MM, default: 10:00)
6. Click **Calculate Cost** to see the estimated total
7. Click **Book Rental** to confirm
8. Receive a unique rental number (format: RNT-YYYYMMDDHHMMSS)
9. Confirmation email sent automatically

### Via CLI

1. Select **Book Rental**
2. View available vehicles and select by ID
3. Enter your details (name auto-filled from login)
4. Specify number of rental days
5. Review the cost summary
6. Confirm with "yes"

### Rental Statuses

| Status | Description |
|--------|-------------|
| **Reserved** | Booking confirmed, awaiting pickup |
| **Active** | Vehicle picked up, rental in progress |
| **Completed** | Vehicle returned, rental finalised |
| **Cancelled** | Reservation cancelled before pickup |
| **Overdue** | Vehicle not returned by due date |

---

## Vehicle Returns

### Processing a Return (GUI)

1. Navigate to the **Returns** tab
2. Select the active rental from the left panel
3. Fill in the return form:
   - **Return Mileage** (required)
   - **Fuel Level** (Full, 3/4, 1/2, 1/4, Empty)
   - **Fuel Fee** (£, if not returned full)
   - **Late Fee** (£, if returned past due date)
   - **Damage Fee** (£, if any damage occurred)
4. Click **Return Vehicle & Pay**
5. Review the payment summary dialog:
   - Base rental cost
   - Additional fees breakdown
   - Total amount due
6. Select payment method and confirm

### Processing a Return (CLI)

1. Select **Return Vehicle**
2. Enter the Rental ID
3. Confirm the return
4. System updates the rental status and frees the vehicle

### Cancelling a Rental

1. In the **Returns** tab, select the rental
2. Click **Cancel Rental**
3. Confirm the cancellation
4. Vehicle becomes available immediately

---

## Payments & Refunds

### Payment Methods

| Method | Description |
|--------|-------------|
| **Cash** | Pay at the counter |
| **Card** | Debit or credit card |
| **Student Account** | Deduct from university finance account |

For student account payments, the system checks your balance before processing and displays your current available funds.

### Payment Processing

Payment is handled during the vehicle return process:
1. Fees are calculated (base rental + fuel + late + damage)
2. Select your payment method
3. For student accounts: balance is verified before deduction
4. Transaction recorded in the finance system
5. Receipt sent via email

### Refunds

1. Navigate to the **Refunds** tab
2. Search for a transaction by ID, customer, or reference
3. Select the transaction to refund
4. Click **Process Refund**
5. Choose refund method:
   - **Cash** - Refund in cash
   - **Card** - Refund to original card
   - **Student Account** - Credit back to finance account
6. Refund reference generated (format: CARRENTAL-REFUND-YYYYMMDDHHMMSS)
7. Refund receipt sent via email
8. Export refund data to CSV via **Export to CSV**

---

## Reports & Analytics

### Available Reports (GUI - Reports Tab)

| Report | Description |
|--------|-------------|
| **Fleet Summary** | Total vehicles, available, rented, maintenance counts |
| **Revenue Report** | Total rentals, completed count, total revenue, average value |
| **Popular Vehicles** | Top 10 vehicles by rental count and revenue |
| **Admin Report** | Comprehensive report combining all metrics |

### Generating Reports

1. Navigate to the **Reports** tab
2. Click the desired report button in the left panel
3. Report displays in the right panel text area
4. Click **Email Admin Report** to send via email

### Statistics (CLI)

Select **View Statistics** to see:
- Total vehicles and rentals
- Vehicles by status breakdown
- Total revenue
- Vehicles by category

---

## Administration

### Fleet Management (Admin/Staff)

**Adding a Vehicle:**
1. Navigate to the **Vehicles** tab
2. Fill in the right panel form:
   - Registration, Make, Model, Year
   - Category, Daily Rate, Colour
   - Seats, Mileage, Transmission, Fuel Type
3. Click **Add Vehicle**

**Updating a Vehicle:**
1. Double-click a vehicle in the list to load its details
2. Modify the fields as needed
3. Click **Update Vehicle**

### Vehicle Statuses

| Status | Description |
|--------|-------------|
| **Available** | Ready for rental |
| **Rented** | Currently on a rental |
| **Maintenance** | Under service or repair |
| **Unavailable** | Temporarily out of service |

### Maintenance Tracking

The system tracks:
- Maintenance type and description
- Service dates and costs
- Mileage at service
- Next scheduled service date

---

## Best Practices

1. **Book early** - Popular vehicles (SUVs, luxury) fill up fast during peak periods
2. **Return on time** - Late returns incur additional fees
3. **Return with full fuel** - Fuel fees apply for vehicles not returned with a full tank
4. **Inspect before pickup** - Note any existing damage during pickup
5. **Report damage immediately** - Contact the rental office for any incidents
6. **Keep your licence current** - A valid licence is required for all rentals

---

## Troubleshooting

### Common Issues

**Cannot book a vehicle:**
- Ensure the vehicle status is "Available"
- Verify you have entered a valid licence number
- Check that your pickup date is today or in the future
- Confirm return date is after pickup date

**Payment failed:**
- If using student account, verify sufficient balance
- Try an alternative payment method
- Contact the rental office for manual processing

**Vehicle not available:**
- Check other categories for similar vehicles
- Try different dates for your preferred vehicle
- Contact the office about upcoming returns

**Email receipt not received:**
- Verify your email address is correct in your profile
- Check spam/junk folders
- Contact support for manual receipt

---

## Contact Information

**University Car Rental**
- **Phone**: (555) 123-CARS
- **Email**: carrental@university.edu
- **Location**: Campus Parking, Building B

**Roadside Assistance**
- **Phone**: (555) 123-HELP
- **Available**: 24/7

---

**Last Updated**: February 2026
**Module**: `university_system/modules/domain/carrental/`
**Support**: carrental@university.edu | (555) 123-CARS
