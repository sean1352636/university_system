# Admissions & CRM System - User Guide

## Overview

The Admissions and Customer Relationship Management (CRM) system manages the full admissions lifecycle from prospect capture through enrollment. It provides tools for tracking prospective students, managing applications, uploading documents, logging interactions, and making admissions decisions. Designed for admissions staff and administrators.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Prospect Management](#prospect-management)
3. [Interaction Tracking](#interaction-tracking)
4. [Application Management](#application-management)
5. [Document Management](#document-management)
6. [Admissions Decisions](#admissions-decisions)
7. [Reporting & Analytics](#reporting--analytics)
8. [Administration](#administration)
9. [Best Practices](#best-practices)
10. [Troubleshooting](#troubleshooting)
11. [Contact Information](#contact-information)

---

## Getting Started

### Accessing the Admissions CRM

**For Admissions Staff:**
1. Navigate to **Administration** → **Admissions CRM**
2. Login with staff credentials
3. Access the admissions dashboard

**For Admissions Administrators:**
1. Navigate to **Administration** → **Admissions CRM**
2. Full access to all CRM features, settings, and reports

### Admissions Dashboard

**Dashboard Overview:**
- **Pipeline Summary**: Prospects by status (prospect, applicant, enrolled, rejected)
- **Recent Interactions**: Latest communications with prospects
- **Application Status**: Pending, under review, decided
- **Upcoming Follow-ups**: Scheduled follow-up tasks
- **Conversion Metrics**: Prospect to applicant to enrolled ratios

---

## Prospect Management

### Adding a New Prospect

**Create Prospect:**
1. Navigate to **Prospects** → **Add New**
2. Enter prospect information:
   - **Personal Details**:
     - First name, last name
     - Email address
     - Phone number
     - Date of birth
   - **Background**:
     - Location (city, state, country)
     - Current school or institution
     - Intended major/program
   - **Source**: How they found us (website, referral, event, social media, direct inquiry)
3. Save prospect record
4. Prospect added with status: **Prospect**

### Viewing & Searching Prospects

**Prospect List:**
1. Navigate to **Prospects** → **All Prospects**
2. View prospects with key details:
   - Name and contact information
   - Status (prospect, applicant, enrolled, rejected)
   - Intended major
   - Source
   - Last interaction date
3. Search by name, email, or location
4. Filter by status, source, or intended program

### Updating Prospect Status

**Status Workflow:**

```
Prospect → Applicant → Enrolled
                    ↘ Rejected
```

**Changing Status:**
1. Open prospect record
2. Click **Update Status**
3. Select new status:
   - **Prospect**: Initial inquiry stage
   - **Applicant**: Application submitted
   - **Enrolled**: Accepted and confirmed enrollment
   - **Rejected**: Application not accepted
4. Add notes about the status change
5. Save

---

## Interaction Tracking

### Logging an Interaction

**Record Communication:**
1. Open prospect record
2. Navigate to **Interactions** → **Log New**
3. Enter interaction details:
   - **Type**: Phone call, email, in-person meeting, campus tour, webinar, text message
   - **Notes**: Summary of the conversation
   - **Staff Member**: Who conducted the interaction
   - **Next Follow-up Date**: When to follow up next
4. Save interaction
5. Interaction added to prospect's timeline

### Viewing Interaction History

**Prospect Timeline:**
1. Open prospect record
2. Navigate to **Interactions**
3. View chronological list of all interactions:
   - Date and time
   - Interaction type
   - Staff member involved
   - Notes and outcomes
   - Follow-up dates

### Follow-Up Management

**Managing Follow-ups:**
1. Navigate to **Tasks** → **Follow-ups**
2. View all upcoming follow-up tasks
3. Filter by:
   - Due date (today, this week, overdue)
   - Staff member
   - Prospect status
4. Mark follow-ups as completed
5. Schedule new follow-ups as needed

---

## Application Management

### Creating an Application

**Initiating an Application:**
1. Open prospect record (prospect must exist first)
2. Navigate to **Applications** → **Create Application**
3. Enter application details:
   - **Application Type**: Undergraduate, graduate, transfer, international
   - **Program**: Intended program/major
   - **Academic Year**: Target enrollment year
4. Submit application
5. Status set to **Submitted**

### Application Status Tracking

**Application Workflow:**

```
Submitted → Under Review → Decision Made → Offer Sent → Accepted/Declined
```

**Status Definitions:**
- **Submitted**: Application received, pending review
- **Under Review**: Admissions committee reviewing
- **Documents Pending**: Missing required documents
- **Decision Made**: Admission decision reached
- **Offer Sent**: Acceptance letter sent
- **Accepted**: Student accepted the offer
- **Declined**: Student declined the offer
- **Rejected**: Application denied

### Viewing Applications

**Application List:**
1. Navigate to **Applications** → **All Applications**
2. View with filters:
   - Application status
   - Program/major
   - Academic year
   - Application type
3. Click on application for full details

---

## Document Management

### Uploading Documents

**Adding Documents to an Application:**
1. Open the application
2. Navigate to **Documents** → **Upload**
3. Select document type:
   - Transcripts (official/unofficial)
   - Letters of recommendation
   - Personal statement/essay
   - Standardized test scores (SAT, GRE, GMAT)
   - Financial documents
   - Identification documents
   - Certificates and awards
4. Upload file (PDF, DOCX, JPG, PNG)
5. Enter document description
6. Submit

### Document Tracking

**Document Checklist:**
- View required documents for each application type
- Track received vs. missing documents
- Mark documents as verified
- Flag incomplete applications
- Send document request reminders to applicants

---

## Admissions Decisions

### Making a Decision

**Decision Process:**
1. Open the application
2. Review all materials:
   - Academic records and transcripts
   - Test scores
   - Personal statement
   - Letters of recommendation
   - Interaction history
3. Navigate to **Decision** → **Record Decision**
4. Select decision:
   - **Admit**: Full admission
   - **Conditional Admit**: Admission with conditions
   - **Waitlist**: Placed on waiting list
   - **Deny**: Application rejected
5. Enter decision date
6. Add decision notes/rationale
7. Save decision

### Communicating Decisions

**After Decision:**
1. Generate decision letter
2. Send via email or postal mail
3. Track response from applicant
4. Update application status based on response
5. Process enrollment for accepted students

---

## Reporting & Analytics

### Available Reports

**Pipeline Reports:**
- Prospect pipeline by status
- Conversion rates (prospect → applicant → enrolled)
- Source effectiveness (which channels produce the most enrollments)
- Time-to-decision metrics

**Application Reports:**
- Applications by program and year
- Admit rates by program
- Document completion rates
- Decision timeline analysis

**Engagement Reports:**
- Interaction volume by type
- Staff activity and productivity
- Follow-up completion rates
- Response time metrics

### Generating Reports

**Create a Report:**
1. Navigate to **Reports** → **Generate**
2. Select report type
3. Set date range and filters
4. Choose format (PDF, CSV, Excel)
5. Generate and download

---

## Administration

### User Management

**Managing CRM Users:**
1. Navigate to **Admin** → **User Management**
2. Add/remove admissions staff
3. Assign roles and permissions:
   - **Viewer**: Read-only access to prospects and applications
   - **Staff**: Create/edit prospects, log interactions, upload documents
   - **Reviewer**: Make admission decisions
   - **Admin**: Full system access and configuration

### System Configuration

**CRM Settings:**
- Configure application types and required documents
- Set up email templates for communications
- Define admission criteria by program
- Configure workflow stages
- Manage source/channel categories

### Data Management

**Data Operations:**
- Import prospects from external sources (CSV)
- Export data for reporting
- Archive old records
- Merge duplicate prospect records
- Audit trail for all changes

---

## Best Practices

1. **Log every interaction** - Maintain a complete communication history for each prospect
2. **Follow up promptly** - Contact prospects within 24-48 hours of inquiry
3. **Keep documents organized** - Ensure all required documents are uploaded and verified
4. **Track sources** - Record how prospects found the university for marketing insights
5. **Set follow-up dates** - Never leave a prospect without a scheduled next step
6. **Use status consistently** - Update prospect and application statuses as they change
7. **Review pipeline regularly** - Monitor conversion rates and identify bottlenecks

---

## Troubleshooting

### Common Issues

**Cannot create application:**
- Ensure prospect record exists first (application requires a linked prospect)
- Verify all required fields are completed
- Check that the program/academic year combination is valid

**Document upload fails:**
- Accepted formats: PDF, DOCX, JPG, PNG
- Maximum file size: 10 MB
- Ensure file is not corrupted or password-protected
- Try a different browser

**Prospect not appearing in search:**
- Check spelling of name or email
- Verify the prospect has been saved (not just started)
- Remove filters that may be hiding the record
- Try searching by different fields

**Cannot record decision:**
- Ensure all required documents are uploaded
- Verify you have reviewer or admin permissions
- Check that the application is in "Under Review" status
- Ensure the decision fields are complete

---

## Contact Information

**Admissions Office**
- **Phone**: (555) 123-ADMIT
- **Email**: admissions@university.edu
- **Location**: Administration Building, Room 100
- **Hours**: Monday-Friday 8:30 AM - 5 PM

**CRM Technical Support**
- **Phone**: (555) 123-TECH
- **Email**: crmsupport@university.edu

**Enrollment Services**
- **Phone**: (555) 123-ENRL
- **Email**: enrollment@university.edu

---

**Last Updated**: February 2026
**Module**: `university_system/modules/domain/admissions/gui/admissions_crm_gui.py`
**Support**: admissions@university.edu | (555) 123-ADMIT
