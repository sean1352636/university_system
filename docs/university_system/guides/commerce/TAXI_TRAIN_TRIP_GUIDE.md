# Taxi Booking, Train Station & Trip Management - User Guide

## Overview

This guide covers three campus mobility services: **Taxi Booking** (on-demand campus taxi with 8 service tiers and a 15% student discount), **Train Station** (intercity train tickets with a 30% student discount), and **Trip Management** (organised group trips with participant tracking, itineraries, and expense management). All three integrate with the university finance system for student account payments and refunds.

## Table of Contents

1. [Taxi Booking](#taxi-booking)
2. [Train Station](#train-station)
3. [Trip Management](#trip-management)
4. [Best Practices](#best-practices)
5. [Troubleshooting](#troubleshooting)
6. [Contact Information](#contact-information)

---

# Taxi Booking

## Getting Started - Taxi

**GUI Mode:**
1. Launch the application → **Mobility** → **Taxi Booking**
2. Login with university credentials
3. Browse available taxi services, book a ride, and view your tickets

## Available Services

| Service | Vehicle | Capacity | Base Fare | Per km | Description |
|---------|---------|----------|-----------|--------|-------------|
| **City Express** | Sedan | 4 | £5.00 | £2.50 | Standard campus taxi |
| **Premium Luxury** | SUV | 6 | £10.00 | £4.00 | Premium ride |
| **Budget Saver** | Hatchback | 4 | £3.00 | £1.75 | Affordable option |
| **Family Van** | Minivan | 8 | £8.00 | £3.50 | Group travel |
| **Eco Green** | Electric | 4 | £4.00 | £2.00 | Eco-friendly electric |
| **Executive Class** | Luxury Sedan | 4 | £15.00 | £5.00 | Business class |
| **Airport Shuttle** | Van | 10 | £20.00 | £3.00 | Airport transfers |
| **Night Owl** | Sedan | 4 | £7.00 | £3.00 | 24/7 late-night service |

## Fare Calculation

**Formula**: Total Fare = Base Fare + (Distance in km × Price per km)

**Student Discount**: **15% off** when paying with Student Account

### Example Fares

| Service | Distance | Standard Fare | Student Fare (15% off) |
|---------|----------|---------------|----------------------|
| City Express | 5 km | £17.50 | £14.88 |
| Budget Saver | 3 km | £8.25 | £7.01 |
| Premium Luxury | 10 km | £50.00 | £42.50 |
| Airport Shuttle | 20 km | £80.00 | £68.00 |

## Booking a Taxi

1. Select a service from the grid display
2. Your name auto-populates from your login
3. Enter pickup location and dropoff location
4. Enter the distance in kilometres
5. Fare is calculated in real-time
6. Select payment method: **Cash**, **Card**, or **Student Account** (15% discount)
7. Confirm the booking
8. Ticket number generated (format: `TXI-YYYYMMDD-XXXXXX`)
9. Confirmation email sent with booking details

## Viewing Tickets

- View all your bookings in the tickets table
- Double-click a ticket to view the full receipt
- Receipts can be saved to a text file

## Refunds

1. Navigate to the refunds section
2. Select a ticket to refund
3. Choose refund method: **Cash**, **Card**, or **Student Account**
4. Refund processed and reference generated

---

# Train Station

## Getting Started - Train

**GUI Mode:**
1. Launch the application → **Mobility** → **Train Station**
2. Login with university credentials
3. Browse train services, purchase tickets, and view your bookings

## Available Services

| Service # | Route | Departure | Arrival | Price | Seats |
|-----------|-------|-----------|---------|-------|-------|
| EXP001 | London Kings Cross → Edinburgh | 06:00 | 10:30 | £89.50 | 150 |
| EXP002 | London Euston → Manchester | 07:15 | 09:30 | £65.00 | 200 |
| EXP003 | London Paddington → Bristol | 08:00 | 09:45 | £45.00 | 180 |
| EXP004 | London Victoria → Brighton | 09:30 | 10:30 | £25.00 | 250 |
| EXP005 | London St Pancras → Paris | 10:00 | 13:00 | £120.00 | 300 |
| REG001 | Birmingham → Liverpool | 11:00 | 13:15 | £35.00 | 120 |
| REG002 | Leeds → Sheffield | 12:30 | 13:15 | £18.50 | 100 |
| REG003 | Glasgow → Edinburgh | 14:00 | 15:00 | £22.00 | 90 |
| EXP006 | Newcastle → London Kings Cross | 15:30 | 18:45 | £95.00 | 175 |
| REG004 | Cardiff → Swansea | 16:00 | 17:00 | £15.00 | 80 |

## Student Discount

**30% off** all train tickets when paying with Student Account.

### Example Prices

| Route | Standard | Student (30% off) |
|-------|----------|-------------------|
| London → Edinburgh | £89.50 | £62.65 |
| London → Manchester | £65.00 | £45.50 |
| London → Paris | £120.00 | £84.00 |
| Cardiff → Swansea | £15.00 | £10.50 |

## Purchasing a Ticket

1. View all available services in the table
2. Your name auto-populates from your login
3. Select a service from the dropdown
4. Choose payment method: **Card**, **Cash**, or **Student Account** (30% discount)
5. Review the price and confirm
6. Ticket and receipt numbers generated automatically
7. Available seats decremented by 1
8. Confirmation email sent

## Viewing Tickets

- View all your tickets in the tickets list
- Active tickets shown in green, refunded in red
- Double-click for full ticket details

## Refunds

1. Select a ticket to refund
2. Choose refund method: **Cash**, **Card**, or **Student Account**
3. Refund processed and receipt sent
4. Ticket status changes to "Refunded"

---

# Trip Management

## Getting Started - Trips

**GUI Mode:**
1. Launch the application → **Mobility** → **Trip Management**
2. Login with university credentials
3. Browse available trips, register, and manage your bookings

## Trip Lifecycle

### Trip Statuses

| Status | Description |
|--------|-------------|
| **Planning** | Trip being organised, not yet open |
| **Open** | Accepting registrations |
| **Full** | Maximum capacity reached |
| **Cancelled** | Trip cancelled |
| **Completed** | Trip finished |

### Participant Statuses

| Status | Description |
|--------|-------------|
| **Registered** | Confirmed participant |
| **Waitlist** | On the waiting list |
| **Cancelled** | Registration cancelled |
| **Attended** | Participated in the trip |

### Payment Statuses

| Status | Description |
|--------|-------------|
| **Pending** | Payment not yet received |
| **Partial** | Partial payment made |
| **Paid** | Full payment received |
| **Refunded** | Payment refunded |

## Registering for a Trip

1. Browse available trips (status: Open)
2. View trip details: destination, dates, cost per person, available spaces
3. Click **Register**
4. Provide:
   - Emergency contact name and phone
   - Medical information (if any)
   - Dietary requirements
5. Registration confirmed with status "Registered"

## Trip Features

### Itineraries
Each trip has a day-by-day itinerary with:
- Activity description
- Location and timing
- Notes and special instructions

### Staff Assignment
Trips are supported by assigned staff in roles:
- **Supervisor** — overall trip lead
- **Coordinator** — planning and logistics
- **Medical** — health emergencies
- **Transport** — driving and transport logistics

### Expense Tracking
Trip expenses are tracked by category with:
- Description and amount
- Date and who recorded the expense

## Reports (Admin/Staff)

- **Trip Summary**: Trip counts by status, total participants, total revenue
- **Participant List**: Names, emails, registration dates
- **Financial Report**: Revenue potential, actual costs, breakeven analysis

## Permissions

| Feature | Student | Instructor | Staff | Admin |
|---------|---------|------------|-------|-------|
| View trips | Yes | Yes | Yes | Yes |
| Register for trips | Yes | Yes | — | — |
| Cancel own registration | Yes | Yes | — | — |
| Create trips | — | — | Yes | Yes |
| Manage participants | — | — | Yes | Yes |
| Track expenses | — | — | Yes | Yes |
| Generate reports | — | — | Yes | Yes |

---

## Best Practices

1. **Taxi** — use Budget Saver for short campus trips to save money
2. **Taxi** — pay with student account for the 15% discount
3. **Train** — book early for popular routes; seats are limited
4. **Train** — always pay with student account for the 30% discount
5. **Trips** — register early for popular trips; spaces fill quickly
6. **Trips** — provide accurate medical and dietary information for safety
7. **All services** — keep confirmation emails for your records

---

## Troubleshooting

### Common Issues

**Taxi booking failed:**
- Ensure all fields are filled (pickup, dropoff, distance)
- Verify the service is available
- Check student account balance if paying with finance account

**Train ticket not issued:**
- Verify there are available seats on the selected service
- Try a different payment method if payment fails

**Cannot register for trip:**
- Check the trip status is "Open"
- Verify there are available spaces
- Ensure you are logged in

**Trip payment status not updated:**
- Contact the trip coordinator for manual payment processing

---

## Contact Information

**University Taxi Service**
- **Phone**: (555) 123-TAXI
- **Email**: taxi@university.edu
- **Available**: 24/7

**University Train Station**
- **Phone**: (555) 123-RAIL
- **Email**: trains@university.edu
- **Location**: Campus Transport Hub

**Trip Management Office**
- **Phone**: (555) 123-TRIP
- **Email**: trips@university.edu
- **Location**: Student Services Building, Room 201

---

**Last Updated**: February 2026
**Module**: `university_system/modules/domain/mobility/`
**Support**: Contact individual service emails listed above
