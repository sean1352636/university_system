# Finance and Funding Guide

This guide covers the finance and funding modules in the Sixth Form College Management System, including financial management, ESFA funding and ILR reporting, bursary allocation, department budgets, expense claims, print credits, and meal ordering.

---

## Financial Management

The **finance** module manages fees, invoices, payments, and payroll across the college.

### Fee Items

Fee items define the charges that can be applied to students.

| Field         | Description                              |
|---------------|------------------------------------------|
| title         | Name of the fee item                     |
| fee_type      | tuition, registration, material, trip, etc. |
| amount        | Monetary amount                          |
| academic_year | Academic year the fee applies to         |
| mandatory     | Whether the fee is compulsory            |

### Invoices

Invoices link fee items to individual students.

#### Invoice Workflow

1. Create fee items for the academic year (e.g., registration fee, trip charges)
2. Generate invoices for students, automatically pulling the amount from the fee item
3. Optionally override the amount for individual students
4. Set due dates for payment
5. Track invoice status through to payment

### Payments

Record payments against invoices to track outstanding balances. Each payment records the amount, date, and payment method.

### Key Features

- Create and manage fee item catalogues by type and academic year
- Generate student invoices individually or in bulk
- Record partial and full payments
- Track outstanding balances
- Financial reporting by fee type and period

---

## ESFA Funding and ILR

The **funding** module manages Individualised Learner Record (ILR) data and ESFA funding compliance for 16-19 education.

### Funding Records

Each funding record tracks a learning aim for a student.

| Field            | Description                                    |
|------------------|------------------------------------------------|
| student_id       | Student the funding record applies to          |
| learning_aim     | Learning aim reference (e.g., qualification)   |
| aim_type         | Type of learning aim                           |
| funding_model    | Funding model (defaults to 16-19)              |
| planned_hours    | Planned guided learning hours                  |
| actual_hours     | Hours actually delivered                       |
| start_date       | Learning aim start date                        |
| planned_end_date | Expected completion date                       |
| outcome          | achieved, partially_achieved, not_achieved     |
| completion_status| Current status of the funding record           |

### Funding Workflow

1. Create funding records for each student's learning aims at the start of the year
2. Track planned hours against actual delivered hours throughout the year
3. Update records with actual hours at regular intervals
4. Complete funding records with outcomes at the end of the programme
5. Generate ILR returns using the accumulated data

### Integration with Study Programmes

Funding records work alongside the study programmes module. The study programmes module validates ESFA condition of funding rules (maths and English requirements, minimum planned hours, work experience completion), while the funding module tracks the detailed ILR data per learning aim.

---

## Bursary Management

The **bursary** module manages the 16-19 Bursary Fund, including vulnerable group bursaries and discretionary awards.

### Bursary Types

| Type            | Description                                          |
|-----------------|------------------------------------------------------|
| vulnerable      | For students in defined vulnerable groups             |
| discretionary   | Awarded at college discretion based on need           |
| free_meals      | Free meals entitlement                               |

### Bursary Record Fields

| Field              | Description                                  |
|--------------------|----------------------------------------------|
| student_id         | Recipient student                            |
| bursary_type       | vulnerable, discretionary, free_meals        |
| amount             | Monetary value of the bursary                |
| evidence_type      | Type of evidence provided                    |
| evidence_verified  | Whether evidence has been verified            |
| payment_frequency  | one_off, weekly, monthly, termly             |
| academic_year      | Year the bursary applies to                  |
| award_date         | Date the bursary was awarded                 |
| status             | pending, approved, rejected, paid            |

### Bursary Workflow

1. Student applies for a bursary or is identified as eligible
2. Create a bursary record with type, amount, and evidence details
3. Verify the supporting evidence
4. Approve or reject the application
5. Update payment status as payments are made
6. Track bursary allocation by type and academic year

### Free Meals

The system tracks free meal eligibility linked to bursary records, allowing canteen and meal ordering systems to verify entitlement.

---

## Department Management

The **departments** module manages college departments and faculties with budget tracking.

### Department Records

| Field                | Description                              |
|----------------------|------------------------------------------|
| code                 | Department code (e.g., ENG, SCI)         |
| name                 | Full department name                     |
| faculty              | Parent faculty grouping                  |
| head_of_department   | Staff member leading the department      |
| curriculum_area      | Curriculum area classification           |
| description          | Department description                   |

### Key Features

- Create and manage departments with unique codes
- Assign heads of department from staff records
- Group departments into faculties
- Link courses to departments via subject area
- Track department-level budgets and expenditure

---

## Expense Claims

The **expense_claims** module manages staff expense reimbursement.

### Claim Fields

| Field         | Description                                    |
|---------------|------------------------------------------------|
| claimant_id   | Staff member submitting the claim              |
| description   | Description of the expense                     |
| amount        | Total claim amount                             |
| claim_date    | Date of the expense                            |
| category      | travel, subsistence, equipment, training, etc. |
| mileage       | Miles travelled (for mileage claims)           |
| mileage_rate  | Rate per mile applied                          |
| receipt_path  | Path to uploaded receipt                       |
| status        | submitted, approved, rejected, paid            |

### Expense Claim Workflow

1. Staff member creates a claim with description, amount, and category
2. Upload supporting receipt or documentation
3. For mileage claims, record miles and rate separately
4. Line manager reviews and approves or rejects the claim
5. Finance processes approved claims for payment
6. Status updates to paid when reimbursement is complete

---

## Print Credits

The **print_credits** module manages student printing accounts and quotas.

### Print Account Features

| Field             | Description                              |
|-------------------|------------------------------------------|
| student_id        | Student the account belongs to           |
| balance           | Current credit balance                   |
| quota_remaining   | Remaining pages in the current quota     |
| quota_reset_date  | Date the quota next resets               |

### Key Features

- Create print accounts for students with an initial balance and quota
- Track balance and quota usage
- Automatic quota reset on configured dates
- Top up balances via payment or allocation
- Monitor usage patterns across the student body

---

## Meal Ordering

The **meal_ordering** module manages the college canteen menu and student meal orders.

### Menu Items

| Field         | Description                              |
|---------------|------------------------------------------|
| name          | Item name                                |
| category      | Category: main, side, drink, dessert     |
| price         | Item price                               |
| dietary_tags  | Dietary information (vegan, gluten-free)  |
| description   | Item description                         |
| is_available  | Whether currently available              |

### Key Features

- Manage menu items with categories and dietary information
- Toggle item availability based on daily offerings
- Students place orders linked to their accounts
- Integration with bursary free meals for eligible students
- Track orders by date and student
