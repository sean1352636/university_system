# Assignment System Guide

Complete guide for managing assignments, submissions, grading, and analytics in the University Management System.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Getting Started](#getting-started)
- [Creating Assignments](#creating-assignments)
- [Managing Submissions](#managing-submissions)
- [Grading & Rubrics](#grading--rubrics)
- [Group Assignments](#group-assignments)
- [Peer Review](#peer-review)
- [Analytics & Reports](#analytics--reports)
- [Templates](#templates)
- [File Management](#file-management)
- [Troubleshooting](#troubleshooting)

---

## Overview

The Assignment System is a comprehensive module with 19 specialized managers providing complete assignment lifecycle management from creation to grading and analytics.

### Key Capabilities

- **Assignment Creation**: Multiple assignment types (homework, project, exam, quiz, essay)
- **Submission Management**: File uploads, late submissions, resubmissions
- **Advanced Grading**: Rubric-based grading, weighted components, partial credit
- **Group Work**: Group formation, collaborative submissions, individual grading
- **Peer Review**: Anonymous peer feedback with moderation
- **Plagiarism Detection**: Automated similarity checking
- **Analytics**: Performance tracking, grade distribution, submission patterns
- **Templates**: Reusable assignment templates

### Access Levels

- **Instructors**: Full access (create, grade, manage)
- **Students**: Submit assignments, view grades and feedback
- **Admins**: Override permissions, access analytics

---

## Features

### Assignment Types

1. **Homework**: Regular assignments with file submissions
2. **Projects**: Long-term assignments with multiple deliverables
3. **Exams**: Time-limited assessments
4. **Quizzes**: Short assessments with auto-grading options
5. **Essays**: Written submissions with plagiarism detection
6. **Lab Reports**: Structured submissions with specific sections
7. **Presentations**: Slide deck submissions with peer evaluation

### Submission Options

- **File Upload**: Multiple file types (PDF, DOCX, ZIP, images)
- **Text Entry**: Direct text submission in the interface
- **External Tool**: Link to external resources (GitHub, Google Docs)
- **Group Submission**: Single submission for entire group
- **Resubmission**: Allow students to resubmit before deadline

### Grading Features

- **Rubric-Based Grading**: Define criteria with point values
- **Quick Grading**: Fast numerical grading with comments
- **Partial Credit**: Award points for partial completion
- **Late Penalties**: Automatic deduction for late submissions
- **Grade Override**: Instructor can override automated grades
- **Bulk Grading**: Grade multiple submissions simultaneously

---

## Getting Started

### For Instructors

**Access the Assignment System:**

**GUI:**
1. Login with instructor credentials
2. Navigate to **Academics → Assignment System**
3. Select your course from the dropdown

**CLI:**
```bash
python run.py --cli
# Select: Academic Management → Assignment System
```

### For Students

**Access Assignments:**

**GUI:**
1. Login with student credentials
2. Navigate to **My Courses → [Course Name] → Assignments**
3. View all assignments for the course

**CLI:**
```bash
python run.py --cli
# Select: Student Portal → My Assignments
```

---

## Creating Assignments

### Basic Assignment Creation

**GUI Method:**

1. Go to **Assignment System → Create New Assignment**
2. Fill in required fields:
   - **Assignment Title**: Clear, descriptive name
   - **Course**: Select from dropdown
   - **Due Date**: Set deadline (date and time)
   - **Total Points**: Maximum points possible
   - **Description**: Detailed instructions
   - **Type**: Select assignment type
3. Configure optional settings:
   - **Late Submission**: Allow/disallow late work
   - **Late Penalty**: Percentage deduction per day
   - **Max Attempts**: Limit resubmissions
   - **Plagiarism Check**: Enable similarity detection
4. Click **Create Assignment**

**CLI Method:**

```bash
# Start assignment creation wizard
> create assignment

# Follow prompts:
Course ID: CS101
Title: Python Programming Assignment 1
Description: Implement a binary search tree
Due Date: 2026-02-15
Time: 23:59
Total Points: 100
Late Submission Allowed: Y
Late Penalty (%): 10
```

### Advanced Options

**Rubric Creation:**

1. In assignment creation, click **Add Rubric**
2. Define criteria:
   - **Criterion Name**: e.g., "Code Quality"
   - **Points**: e.g., 25
   - **Description**: Grading guidelines
3. Add multiple criteria (up to 10)
4. System automatically calculates total points

**Example Rubric:**
```
Criterion              Points   Description
-------------------    ------   ------------------------------------
Code Functionality     40       Code runs without errors and meets requirements
Code Quality           25       Well-organized, follows style guidelines
Documentation          20       Clear comments and README
Testing                15       Comprehensive test cases
Total:                100
```

**Submission Settings:**

- **Accepted File Types**: PDF, DOCX, TXT, ZIP, PY, JAVA, CPP
- **Max File Size**: Set limit (default 50MB)
- **Max Files**: Number of files allowed
- **Group Assignment**: Enable group submissions
- **Peer Review**: Enable peer feedback

---

## Managing Submissions

### Viewing Submissions

**GUI:**

1. Navigate to **Assignment System → View Submissions**
2. Select assignment from list
3. View submission statistics:
   - Total submissions
   - On-time vs late
   - Pending grading
   - Average grade (if graded)

**Filter Options:**
- By status (submitted, graded, late, missing)
- By student name or ID
- By submission date range

### Downloading Submissions

**Bulk Download:**

1. Select assignment
2. Click **Download All Submissions**
3. Choose format:
   - ZIP file (all submissions)
   - Individual files (organized by student)
   - CSV with metadata

**Individual Download:**

1. Click on student submission
2. Click **Download Files**
3. Files download with student name prefix

### Late Submissions

**Handling Late Work:**

1. System automatically marks late submissions
2. Late penalty applied based on settings
3. Instructor can:
   - **Accept with penalty**: Auto-deduct points
   - **Accept without penalty**: Waive late penalty
   - **Reject**: Don't accept late work

**Deadline Extensions:**

1. Select student(s)
2. Click **Extend Deadline**
3. Set new due date for selected students
4. System tracks extensions in audit log

---

## Grading & Rubrics

### Rubric-Based Grading

**Step-by-Step:**

1. Open student submission
2. Click **Grade with Rubric**
3. For each criterion:
   - Award points (0 to max)
   - Add comments (optional)
4. System calculates total automatically
5. Add overall feedback
6. Click **Submit Grade**

**Quick Rubric Grading:**
- Use number keys 0-9 for quick point entry
- Tab to move between criteria
- Enter for next submission

### Manual Grading

**Without Rubric:**

1. Open submission
2. Review student work
3. Enter numerical grade (0-100 or points)
4. Add written feedback
5. Click **Submit Grade**

**Feedback Options:**
- **Inline Comments**: Comment on specific files
- **Overall Comments**: General feedback
- **Audio Feedback**: Record voice comments (if enabled)
- **Attachments**: Attach reference files

### Bulk Grading

**Grade Multiple Submissions:**

1. Click **Bulk Grading Mode**
2. View submissions in grid layout
3. Rapid grading options:
   - Enter grades in spreadsheet-style interface
   - Copy grade to similar submissions
   - Apply same rubric scores
4. Click **Save All Grades**

### Grade Adjustments

**Curve Grading:**

1. Select assignment
2. Click **Grade Adjustments → Apply Curve**
3. Choose curve type:
   - **Linear**: Add fixed points to all grades
   - **Square Root**: √(grade × 100)
   - **Percentage**: Multiply by percentage
4. Preview adjusted grades
5. Click **Apply**

**Grade Override:**

1. Open graded submission
2. Click **Override Grade**
3. Enter new grade
4. Provide reason (required for audit)
5. System logs override

---

## Group Assignments

### Creating Group Assignments

1. Create assignment as normal
2. Enable **Group Assignment** option
3. Set group parameters:
   - **Group Size**: Min and max members
   - **Self-Formation**: Allow students to form groups
   - **Random Assignment**: System assigns groups
   - **Instructor Assignment**: Manually create groups

### Managing Groups

**Create Groups (Instructor):**

1. Go to **Assignment → Manage Groups**
2. Click **Create New Group**
3. Add students to group
4. Assign group name/number
5. Click **Save Group**

**Auto-Generate Groups:**

1. Click **Auto-Generate Groups**
2. Set group size (e.g., 3-4 students)
3. Choose assignment method:
   - Random
   - By performance (similar grades)
   - By diversity (mixed grades)
4. Click **Generate**

### Group Grading Options

**Same Grade for All:**
- Enter one grade, applied to all group members
- All members see same feedback

**Individual Grades:**
- Grade each student separately
- Account for individual contribution
- Use peer evaluation data

**Peer Evaluation:**
1. Enable peer evaluation in settings
2. Students rate each member's contribution
3. System calculates grade adjustments
4. Final grade = Base Grade × Contribution Factor

---

## Peer Review

### Enabling Peer Review

1. In assignment settings, enable **Peer Review**
2. Configure parameters:
   - **Number of Reviews**: How many peers each student reviews (2-5)
   - **Review Deadline**: When reviews are due
   - **Anonymous**: Hide reviewer identity
   - **Points for Reviewing**: Award points for quality reviews

### Review Assignment

**Automated Assignment:**
- System randomly assigns submissions to reviewers
- Each student reviews X other submissions
- No student reviews their own work

**Manual Assignment:**
- Instructor assigns specific reviewers
- Useful for targeted feedback

### Review Rubric

**Create Review Guidelines:**

1. Define review criteria:
   - Content accuracy
   - Organization
   - Creativity
   - Technical execution
2. Provide guiding questions
3. Set character limits for comments

### Moderating Reviews

**Instructor Oversight:**

1. View all peer reviews
2. Flag inappropriate reviews:
   - Unhelpful comments
   - Offensive content
   - Copied reviews
3. Override review scores if needed
4. Provide feedback on review quality

---

## Analytics & Reports

### Assignment Analytics

**Performance Dashboard:**

Access via **Assignment System → Analytics**

**Metrics Displayed:**
- **Submission Rate**: Percentage of students who submitted
- **On-Time Rate**: Percentage submitted before deadline
- **Average Grade**: Mean score for assignment
- **Grade Distribution**: Histogram of scores
- **Time to Submit**: When most students submit

**Grade Distribution Chart:**
```
  A (90-100): ████████████░░ 40%
  B (80-89):  ██████████████ 30%
  C (70-79):  ██████░░░░░░░░ 15%
  D (60-69):  ████░░░░░░░░░░ 10%
  F (0-59):   ██░░░░░░░░░░░░  5%
```

### Student Progress Tracking

**Individual Student View:**

1. Select student
2. View assignment history:
   - Submission timeliness
   - Grade trend over time
   - Common feedback themes
   - Improvement areas

**Cohort Comparison:**
- Compare student to class average
- Identify struggling students
- Highlight top performers

### Predictive Analytics

**Early Warning System:**

System analyzes:
- Late submission patterns
- Declining grades
- Missing assignments
- Low rubric scores in key areas

**Alerts Generated For:**
- Students at risk of failing
- Consistent late submissions
- Sudden grade drops

### Reports

**Generate Reports:**

1. Go to **Reports** tab
2. Select report type:
   - **Gradebook**: All grades for course
   - **Submission Report**: Submission statistics
   - **Grade Distribution**: Visual grade analysis
   - **Missing Assignments**: Students with missing work
   - **Peer Review Summary**: Review completion and quality
3. Choose format: PDF, Excel, CSV
4. Click **Generate Report**

**Scheduled Reports:**
- Set up weekly grade reports
- Email to instructors automatically
- Archive in reports folder

---

## Templates

### Using Templates

**Benefits:**
- Reuse common assignment structures
- Ensure consistency across sections
- Save time on assignment creation

**Create from Template:**

1. Go to **Assignment System → Templates**
2. Select template
3. Click **Create from Template**
4. Modify specific details (due date, points, etc.)
5. Click **Create**

### Creating Templates

**Save Assignment as Template:**

1. Create assignment with all desired settings
2. Click **Save as Template**
3. Enter template name
4. Add description
5. Template now available for reuse

**Template Library:**

**Pre-built Templates:**
- Homework Assignment (Basic)
- Research Paper (with rubric)
- Programming Project (with test cases)
- Lab Report (structured sections)
- Group Presentation (with peer eval)
- Quiz (auto-graded)

**Custom Templates:**
- Create department-specific templates
- Share templates across instructors
- Import templates from other courses

---

## File Management

### Supported File Types

**Documents:**
- PDF, DOCX, DOC, TXT, RTF, ODT

**Code:**
- PY, JAVA, CPP, C, JS, HTML, CSS

**Archives:**
- ZIP, RAR, TAR, GZ

**Images:**
- JPG, PNG, GIF, SVG

**Other:**
- XLSX, PPTX, CSV

### File Preview

**In-Browser Preview:**
- PDF files: Full preview in browser
- Text files: Syntax-highlighted display
- Images: Full-size viewing
- Code: Syntax highlighting by language

**Download for Preview:**
- Archives: Must download to view contents
- Executable files: Download only (security)

### Plagiarism Detection

**How It Works:**

1. System analyzes submitted text
2. Compares against:
   - Other student submissions
   - Online databases
   - Previous year submissions
3. Generates similarity report

**Similarity Report:**
```
Overall Similarity: 15%

Sources:
- Student submission (2025): 8% match
- Online source (website.com): 5% match
- Common phrases: 2% match

Flagged Sections:
1. Introduction (lines 1-10): 25% similar
2. Methodology (lines 45-67): 18% similar
```

**Reviewing Results:**

1. Access similarity report
2. Review highlighted sections
3. Determine if plagiarism occurred:
   - **Properly cited**: No action
   - **Common knowledge**: No action
   - **Uncited copying**: Academic misconduct
4. Take appropriate action

### File Storage

**Storage Limits:**
- Per file: 50MB default (configurable)
- Per assignment: Unlimited files
- Per course: 10GB default (configurable)

**Retention Policy:**
- Submissions retained for academic year + 2 years
- Automatic archival of old submissions
- Restore from archive if needed

---

## Troubleshooting

### Common Issues

**"File too large" error**

**Solution:**
- Check file size (max 50MB default)
- Compress files into ZIP
- Split large projects into multiple files
- Contact instructor for increased limit

**"Invalid file type" error**

**Solution:**
- Check accepted file types in assignment
- Convert file to accepted format (e.g., DOCX to PDF)
- Contact instructor to add file type

**Submission not appearing**

**Solution:**
- Verify file uploaded successfully (check for confirmation)
- Refresh the page
- Check browser console for errors
- Try different browser
- Clear browser cache

**Grade not showing**

**Solution:**
- Instructor may not have released grades yet
- Check "Release Grades" setting
- Grades released after peer review completes
- Contact instructor if delayed

**Can't access assignment**

**Solution:**
- Check if you're enrolled in the course
- Verify assignment is published
- Check start date (assignment may not be available yet)
- Ensure you're logged in with correct account

### Error Messages

**"Assignment deadline has passed"**

- Late submissions not allowed for this assignment
- Contact instructor for deadline extension
- Check if resubmission deadline is still open

**"Maximum attempts reached"**

- You've used all allowed resubmissions
- Contact instructor if circumstances require additional attempt

**"Group not formed"**

- Group assignment requires group formation first
- Join a group or create one
- Instructor may need to assign you to a group

**"Peer review not available"**

- Must submit assignment before reviewing others
- Wait for submission deadline to pass
- Check peer review deadline

### Getting Help

**Student Support:**
- Email instructor through system messaging
- Visit office hours
- Contact student helpdesk: [View Helpdesk](../../modules/domain/student_affairs/gui/helpdesk_gui.py)

**Instructor Support:**
- Contact IT support for technical issues
- Consult assignment system documentation
- Email: support@university.edu

**Technical Issues:**
- Check system status page
- Clear browser cache and cookies
- Try incognito/private browsing
- Update browser to latest version

---

## Best Practices

### For Instructors

**Assignment Design:**
- Provide clear, detailed instructions
- Include examples and resources
- Set realistic deadlines
- Enable peer review for writing assignments
- Use rubrics for objective grading

**Grading:**
- Grade within 1 week of submission
- Provide constructive feedback
- Use rubrics consistently
- Release grades promptly

**Communication:**
- Announce assignments in advance
- Send reminders before deadlines
- Respond to student questions quickly
- Use analytics to identify struggling students

### For Students

**Submission:**
- Submit early (don't wait for deadline)
- Keep backup copies of your work
- Check file format requirements
- Read instructions completely
- Test file uploads before deadline

**Group Work:**
- Form groups early
- Communicate regularly with team
- Divide work fairly
- Submit well before deadline
- Use version control (Git) for code projects

---

## Additional Resources

- **Video Tutorials**: [Assignment System Walkthrough](../../docs/videos/)
- **FAQ**: [Common Questions](../../docs/FAQ.md)
- **API Documentation**: [Assignment API](../../docs/development/API.md#assignments)
- **Developer Guide**: [CLAUDE.md](../../../CLAUDE.md)

---

**Version**: 1.0
**Last Updated**: January 2026
**Maintained By**: University IT Department
