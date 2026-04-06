# Housing & Accommodation Management Guide

This guide covers student housing allocation, room management, applications, maintenance, payments, and reporting within the University Management System.

## Table of Contents

- [Overview](#overview)
- [Getting Started](#getting-started)
- [Building Management](#building-management)
- [Room Management](#room-management)
- [Housing Applications](#housing-applications)
- [Room Assignments](#room-assignments)
- [Maintenance Requests](#maintenance-requests)
- [Payment Management](#payment-management)
- [Room Inspections](#room-inspections)
- [Room Inventory](#room-inventory)
- [Reports & Analytics](#reports--analytics)
- [Student Portal](#student-portal)
- [Permissions](#permissions)

## Overview

The Housing & Accommodation module manages the full lifecycle of student housing, from building and room setup through applications, assignments, maintenance, and payments. It supports both CLI and GUI interfaces with role-based access for administrators, staff, and students.

**Key files:**
- Service: `modules/domain/housing/services/housing_accommodation.py`
- GUI: `modules/domain/housing/gui/housing_accommodation_gui/`

## Getting Started

### CLI Access

From the main menu, select **Housing Accommodation Management**. The menu adapts based on your role:

- **Admin**: Full access to all 10 menu sections
- **Staff**: Read-only access to buildings, applications, assignments, and maintenance
- **Student**: Access to personal applications, assignments, and maintenance requests

### GUI Access

Launch the GUI from the main application window or directly:

```python
from university_system.modules.domain.housing.gui.housing_accommodation_gui import display_housing_accommodation_menu_gui
display_housing_accommodation_menu_gui(auth_instance)
```

The GUI uses a modular manager pattern with specialized views for each function area.

## Building Management

### Creating a Building

1. Select **Building Management** from the menu
2. Choose **Add Building**
3. Enter the building details:
   - **Building Name** (e.g., "University Residence Hall")
   - **Address**
   - **Campus Location** (e.g., "North Campus")
   - **Total Rooms**
   - **Amenities**: Elevator, Accessible Rooms, Kitchen, Laundry (yes/no)
4. After creation, you will be prompted to create rooms for the building

### Viewing Buildings

The buildings list displays:
- Building ID, Name, Location
- Total Rooms, Available Rooms
- Occupancy Rate (%)

### Editing and Deleting

Select a building from the list to edit its details or delete it. Deletion cascades to associated rooms and assignments.

## Room Management

### Creating Rooms

Rooms can be created individually or in batch:

1. Select a building, then choose **Manage Rooms**
2. For batch creation, specify:
   - Number of floors
   - Rooms per floor
3. For each room, configure:
   - **Room Type**: Single, Double, Triple, Suite, Studio, Apartment
   - **Max Occupants**: Based on room type
   - **Monthly Rent**
   - **Accessibility**: Whether the room is accessible

### Room Status

Rooms have four possible statuses:
- **Available**: Ready for assignment
- **Occupied**: Currently assigned to a student
- **Maintenance**: Under repair or renovation
- **Reserved**: Held for a specific purpose

### Editing Rooms

Update room type, occupancy limits, rental rate, status, or accessibility flags from the room management interface.

## Housing Applications

### Submitting an Application (Student)

1. Select **My Housing Application** > **Apply for Housing**
2. Choose a preferred building (or select "No Preference")
3. Select a room type (Single, Double, Triple, Suite, Studio, Apartment)
4. Enter your requested move-in date (YYYY-MM-DD format)
5. Specify duration in months
6. Add any special requirements (accessibility needs, noise sensitivity, etc.)
7. Submit the application

The system prevents duplicate active applications per student.

### Processing Applications (Admin)

1. Select **Housing Applications** > **View Applications**
2. Filter by status: Pending, Under Review, Approved, Rejected, Waiting List
3. Select an application to process
4. Choose an action:
   - **Approve**: Moves the application to approved status
   - **Reject**: Rejects with reason
   - **Waiting List**: Places on the waiting list
5. The system sends email notifications to the student automatically

### Application Statuses

| Status | Description |
|--------|-------------|
| Pending | Newly submitted, awaiting review |
| Under Review | Being evaluated by housing staff |
| Approved | Approved and ready for room assignment |
| Rejected | Denied with reason provided |
| Waiting List | Placed on waiting list for availability |

## Room Assignments

### Creating an Assignment

After an application is approved:

1. Select **Housing Assignments** > **Create Assignment**
2. Choose the approved application
3. Assign a specific room from available rooms
4. The system generates:
   - A unique contract number
   - Monthly rent based on the room
   - Move-in documents
5. The room status updates to "Occupied"

### Managing Assignments

View active assignments filtered by building, student, or status. Each assignment shows:
- Student name and ID
- Room and building details
- Move-in/move-out dates
- Contract number
- Monthly rent

### Updating Assignment Status

- **Active**: Currently in effect
- **Terminated**: Ended early (records actual move-out date)
- **Expired**: Reached planned end date

When an assignment is terminated or expired, the room status reverts to "Available" and occupancy counts update.

## Maintenance Requests

### Submitting a Request (Student)

1. Select **Maintenance Requests** > **Report Maintenance Issue**
2. Describe the issue
3. Select the issue type:
   - Plumbing, Electrical, HVAC, Furniture, Damage, Other
4. Set priority: Low, Medium, High, Critical
5. Submit the request

### Managing Requests (Admin)

1. View all requests, filtered by status or priority
2. Assign a request to maintenance staff
3. Set a scheduled completion date
4. Update status as work progresses:
   - **Open**: Newly submitted
   - **In Progress**: Being worked on
   - **Complete**: Work finished
   - **Closed**: Verified and closed

### Tracking

Students can view their own requests and see current status, scheduled dates, and completion feedback.

## Payment Management

### Recording a Payment

1. Select **Payment Management** > **Record New Payment**
2. Select the student and their active assignment
3. Enter payment details:
   - **Amount**
   - **Payment Method**: Cash, Check, Card, Bank Transfer, Online
   - **Payment Period**: Start and end dates
   - **Transaction Reference**
4. The payment is recorded in the housing system and synced with the Finance module

### Viewing Payment History

Filter payment history by student or date range. Each record shows:
- Payment ID, Student Name
- Amount, Date, Method
- Status (Pending, Completed, Overdue)
- Transaction reference

## Room Inspections

### Creating an Inspection

1. Select **Room Inspections** > **Create Inspection**
2. Choose the inspection type:
   - **Move-in**: Document room condition at move-in
   - **Move-out**: Assess condition at departure
   - **Routine**: Regular scheduled inspection
   - **Damage Assessment**: Specific damage evaluation
3. Enter inspector name and date
4. Document findings and any required actions
5. Schedule follow-up inspections if needed

### Viewing Inspections

Browse inspection history filtered by room, type, or status. View detailed findings and recommended actions.

## Room Inventory

Track furniture and equipment in each room:

- **Item Types**: Bed, Desk, Chair, Wardrobe, Shelving, Other
- **Condition**: Good, Fair, Poor, Damaged
- **Status**: In Stock, In Use, Damaged, Missing

Use the inventory management interface to add, update, or remove items from room records.

## Reports & Analytics

The reporting system provides five main report types:

### Occupancy Report
- Building-level occupancy rates
- Room availability breakdown by type
- Occupancy trends over time

### Financial Summary
- Total rent collected
- Outstanding balances
- Payment method distribution
- Revenue forecasts

### Maintenance Summary
- Open request counts by priority
- Completion rates and average resolution time
- Staff workload distribution

### Room Availability Report
- Available rooms by building and type
- Upcoming move-outs
- Predicted future availability

### Export Options
- **CSV**: All housing data
- **PDF**: Formatted reports
- **Excel**: Spreadsheet-compatible exports

## Student Portal

Students have a simplified interface with three main sections:

1. **My Housing Application**: Apply for housing and track application status
2. **My Housing Assignment**: View assigned room details, contract information, and payment history
3. **Maintenance Requests**: Report issues and track request status

## Permissions

| Permission | Admin | Staff | Student |
|-----------|-------|-------|---------|
| Manage buildings/rooms | Full | View only | No access |
| Process applications | Full | View only | Own application |
| Create assignments | Full | View only | View own |
| Manage maintenance | Full | View only | Own requests |
| Record payments | Full | View only | View own |
| Create inspections | Full | View only | No access |
| Generate reports | Full | View only | No access |
| Manage inventory | Full | View only | No access |
