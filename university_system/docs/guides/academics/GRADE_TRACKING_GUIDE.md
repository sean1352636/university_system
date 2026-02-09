# Grade Tracking Guide

Complete guide for managing grades, GPA calculations, transcripts, and academic analytics in the University Management System.

---

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Grade Entry](#grade-entry)
- [Grading Schemes](#grading-schemes)
- [GPA Calculations](#gpa-calculations)
- [Grade Analytics](#grade-analytics)
- [Transcripts](#transcripts)
- [Grade Reports](#grade-reports)
- [Academic Standing](#academic-standing)
- [Troubleshooting](#troubleshooting)

---

## Overview

The Grade Tracking system provides comprehensive grade management with 24 specialized modules covering grade entry, GPA calculation, transcript generation, and academic analytics.

### Key Features

- **Flexible Grading**: Multiple grading schemes (letter, percentage, pass/fail, custom)
- **Weighted Components**: Assignments, exams, participation with custom weights
- **GPA Calculation**: Real-time GPA computation with credit hours
- **Grade Analytics**: Performance trends, grade distribution, predictions
- **Transcripts**: Official and unofficial transcript generation
- **What-If Analysis**: Simulate future grades and GPA impact
- **Academic Standing**: Dean's list, probation, honors tracking
- **Batch Operations**: Grade multiple students simultaneously

### Access Levels

- **Instructors**: Enter/modify grades for their courses
- **Students**: View own grades, GPA, and transcripts
- **Registrar**: Override grades, generate official transcripts
- **Advisors**: View advisee grades and academic standing

---

## Quick Start

### For Instructors

**Access Grade Entry:**

```bash
# GUI
Main Menu → Academics → Grade Tracking → Grade Entry

# CLI
python run.py --cli
> Select: Academic Management → Grades → Enter Grades
```

### For Students

**View Your Grades:**

```bash
# GUI
Main Menu → Student Portal → My Grades

# CLI
python run.py --cli
> Select: Student Portal → View Grades & GPA
```

---

## Grade Entry

### Single Student Grading

**Method 1: Direct Entry**

1. Navigate to **Grade Tracking → Enter Grades**
2. Select course from dropdown
3. Select student
4. Enter grade components:
   - Assignments: Individual or average
   - Midterm: Percentage or letter
   - Final: Percentage or letter
   - Participation: Points or percentage
5. System calculates final grade automatically
6. Click **Save Grade**

**Method 2: Grade Book View**

1. Open **Grade Book** for course
2. View spreadsheet-style interface
3. Enter grades directly in cells
4. Tab to move between cells
5. Auto-saves on change

### Batch Grade Entry

**Grade Multiple Students:**

1. Click **Batch Grade Entry**
2. Select assignment or component
3. View list of all students
4. Enter grades in rapid succession:
   ```
   Student Name           Grade    Comments
   ----------------       -----    ---------
   John Doe              92        Excellent work
   Jane Smith            85        Good effort
   Bob Johnson           78        Needs improvement
   ```
5. Click **Save All**

**Import from CSV:**

1. Download grade template CSV
2. Fill in Excel/Sheets:
   ```csv
   StudentID,Assignment1,Midterm,Final,Participation
   S001,92,88,90,100
   S002,85,82,88,95
   S003,78,75,80,90
   ```
3. Upload CSV file
4. Review and confirm
5. Click **Import Grades**

### Grade Components

**Define Course Components:**

1. Go to **Course Settings → Grade Components**
2. Add components:
   ```
   Component        Weight    Type
   ------------     ------    ---------
   Assignments      30%       Average
   Midterm Exam     25%       Single
   Final Exam       35%       Single
   Participation    10%       Points
   Total:          100%
   ```
3. Click **Save Weights**

**Component Types:**
- **Average**: Averages multiple items (assignments, quizzes)
- **Single**: One-time assessment (midterm, final)
- **Points**: Raw points (participation, attendance)
- **Bonus**: Extra credit (doesn't count toward 100%)

### Extra Credit

**Adding Extra Credit:**

1. Check **Allow Extra Credit**
2. Set maximum extra credit (e.g., 5%)
3. Enter extra credit points for students
4. System adds to final grade (capped at max)

**Example:**
```
Base Grade: 92%
Extra Credit: +3%
Final Grade: 95%

Base Grade: 98%
Extra Credit: +3% (capped at 5% max)
Final Grade: 100% (capped)
```

---

## Grading Schemes

### Letter Grades

**Standard Scale:**
```
A   = 90-100%  (4.0 GPA)
B   = 80-89%   (3.0 GPA)
C   = 70-79%   (2.0 GPA)
D   = 60-69%   (1.0 GPA)
F   = 0-59%    (0.0 GPA)
```

**Plus/Minus Scale:**
```
A   = 93-100%  (4.0 GPA)
A-  = 90-92%   (3.7 GPA)
B+  = 87-89%   (3.3 GPA)
B   = 83-86%   (3.0 GPA)
B-  = 80-82%   (2.7 GPA)
C+  = 77-79%   (2.3 GPA)
C   = 73-76%   (2.0 GPA)
C-  = 70-72%   (1.7 GPA)
D+  = 67-69%   (1.3 GPA)
D   = 63-66%   (1.0 GPA)
D-  = 60-62%   (0.7 GPA)
F   = 0-59%    (0.0 GPA)
```

### Custom Grading Schemes

**Create Custom Scale:**

1. Go to **Course Settings → Grading Scheme**
2. Click **Create Custom Scheme**
3. Define grade ranges:
   ```
   Grade    Min%    Max%    GPA Points
   -----    ----    ----    ----------
   A+       97      100     4.3
   A        93      96      4.0
   A-       90      92      3.7
   ...
   ```
4. Click **Save Scheme**

**Predefined Schemes:**
- **Pass/Fail**: P (pass) or F (fail)
- **Satisfactory/Unsatisfactory**: S/U
- **Honors**: High Honors, Honors, Pass, Fail
- **Numeric**: 0-100 scale only

### Pass/Fail Courses

**Enable P/F Grading:**

1. Set course grading scheme to **Pass/Fail**
2. Define passing threshold (e.g., 70%)
3. Grades above threshold = P
4. Grades below threshold = F

**Impact on GPA:**
- Pass (P): No impact on GPA
- Fail (F): Counts as 0.0 in GPA

---

## GPA Calculations

### How GPA is Calculated

**Formula:**
```
GPA = (Sum of Grade Points × Credit Hours) / Total Credit Hours

Grade Points = GPA Value × Credit Hours
```

**Example:**
```
Course         Grade  GPA Value  Credits  Grade Points
-----------    -----  ---------  -------  ------------
CS 101         A      4.0        3        12.0
MATH 201       B+     3.3        4        13.2
ENG 102        A-     3.7        3        11.1
HIST 101       B      3.0        3         9.0
                                  ---      ----
Total                            13        45.3

GPA = 45.3 / 13 = 3.48
```

### Semester vs Cumulative GPA

**Semester GPA:**
- Calculated for current semester only
- Based on courses in that semester
- Resets each semester

**Cumulative GPA:**
- Calculated across all semesters
- Includes all courses ever taken
- Updated after each semester

**View GPA:**

```bash
# GUI
Student Portal → My Grades → GPA Summary

# Shows:
- Current Semester GPA: 3.65
- Cumulative GPA: 3.48
- Credits Earned: 45
- Credits In Progress: 12
```

### GPA Calculator (What-If Analysis)

**Simulate Future Grades:**

1. Go to **GPA Calculator**
2. View current courses
3. Enter hypothetical grades:
   ```
   Current Course     Credits  Projected Grade
   --------------     -------  ---------------
   CS 301             3        A (4.0)
   MATH 302           4        B+ (3.3)
   ENG 201            3        A- (3.7)
   ```
4. System calculates projected GPA:
   ```
   Current Cumulative GPA: 3.48
   Projected Semester GPA: 3.67
   Projected Cumulative GPA: 3.52
   ```

**Required Grade Calculator:**

- Enter desired final GPA
- System calculates grades needed in current courses
- Example: "You need at least B+ in CS301 and A- in MATH302 to achieve 3.6 GPA"

---

## Grade Analytics

### Performance Dashboard

**Instructor Analytics:**

Access: **Grade Tracking → Course Analytics**

**Metrics:**
- **Class Average**: Mean grade for course
- **Median Grade**: Middle value
- **Grade Distribution**: Visual histogram
- **Pass Rate**: Percentage passing
- **Drop Rate**: Percentage who dropped

**Grade Distribution Chart:**
```
   A  ████████████      30%
   B  ████████████████  35%
   C  ██████████        25%
   D  ████              8%
   F  ██                2%
```

### Student Performance Tracking

**Individual Student Analytics:**

1. Select student
2. View performance metrics:
   - **Grade Trend**: Line graph over time
   - **Strengths**: Highest-performing areas
   - **Weaknesses**: Areas needing improvement
   - **Attendance Correlation**: Grade vs attendance
   - **Predicted Final Grade**: Based on current trajectory

**Example Trend:**
```
Grade Progression:
Week 1-4:   B  (83%)
Week 5-8:   B+ (87%)
Week 9-12:  A- (91%)
Trend: ↑ Improving
Prediction: A- final grade
```

### Comparative Analytics

**Compare Student to Class:**
- Student grade vs class average
- Percentile ranking
- Performance in each component

**Example:**
```
Your Performance:         Class Average:
Final Grade: B+ (87%)     83%
Assignment Avg: 90%       85%
Midterm: 85%              82%
Final Exam: 88%           84%

Your Rank: 12 / 45 (73rd percentile)
```

### Predictive Analytics

**Early Warning System:**

System identifies students at risk:
- Current grade below C (70%)
- Declining grade trend
- Poor assignment completion rate
- Low exam scores

**Alert Example:**
```
⚠️ Student Alert: Jane Smith (CS101)
Current Grade: D+ (67%)
Trend: Declining
Recommendation: Schedule advising session
```

---

## Transcripts

### Unofficial Transcripts

**Generate for Students:**

**GUI Method:**
1. Navigate to **Student Portal → My Transcripts**
2. Click **View Unofficial Transcript**
3. Choose format:
   - PDF (printable)
   - HTML (web view)
   - CSV (data export)
4. Click **Generate**

**CLI Method:**
```bash
> transcript generate

Options:
1. Current Semester Only
2. All Semesters
3. Specific Date Range

Select: 2

Format:
1. PDF
2. HTML
3. CSV

Select: 1

Generating unofficial transcript...
Saved to: transcripts/unofficial_20260128.pdf
```

### Official Transcripts

**Request Official Transcript:**

1. Go to **Registrar Services → Request Transcript**
2. Fill in request form:
   - Delivery method (email, mail, pickup)
   - Recipient (self, employer, graduate school)
   - Number of copies
3. Pay processing fee (if applicable)
4. Click **Submit Request**

**Processing Time:**
- Electronic: 1-2 business days
- Printed/Mailed: 3-5 business days
- Rush: Same day (+$15 fee)

**Official Transcript Includes:**
- University seal and watermark
- All courses and grades
- Cumulative GPA
- Degree(s) earned
- Academic honors
- Registrar signature

### Transcript Content

**Information Included:**
```
OFFICIAL TRANSCRIPT
University Name
Student: John Doe
ID: S123456
DOB: 01/15/2005

FALL 2025 SEMESTER
Course        Title              Cr  Grade  Points
-----------   ----------------   --  -----  ------
CS 101        Intro to CS        3   A      12.0
MATH 201      Calculus I         4   B+     13.2
ENG 102       Composition        3   A-     11.1

Semester GPA: 3.65  Credits: 10  Points: 36.3

CUMULATIVE SUMMARY
Total Credits: 45
Cumulative GPA: 3.52
Academic Standing: Good Standing
```

---

## Grade Reports

### Progress Reports

**Mid-Semester Reports:**

Instructors submit at midpoint:
1. Access **Grade Reports → Mid-Semester**
2. Enter current grades for each student
3. Add comments on performance
4. Mark students at risk
5. Click **Submit Reports**

Students receive:
- Current grade estimate
- Instructor comments
- Resources for improvement

### Final Grade Reports

**End of Semester:**

1. Enter all final grades
2. System calculates final course grades
3. Review grade distribution
4. Submit grades to registrar
5. Grades posted to student accounts

**Grade Submission Deadline:**
- Typically 72 hours after final exam
- Late submissions require approval

### Custom Reports

**Generate Custom Reports:**

1. Go to **Reports → Custom Report**
2. Select parameters:
   - Date range
   - Courses or departments
   - Student cohort
   - Grade components
3. Choose metrics:
   - Average grades
   - Pass/fail rates
   - GPA distribution
   - Honor students
4. Select format (PDF, Excel, CSV)
5. Click **Generate**

**Common Custom Reports:**
- Department GPA trends
- Course difficulty analysis
- Student success rates by demographic
- Grade inflation/deflation studies

---

## Academic Standing

### Classifications

**Good Standing:**
- Cumulative GPA ≥ 2.0
- No academic restrictions
- Eligible for all activities

**Academic Probation:**
- Cumulative GPA < 2.0
- Must meet with advisor
- Limited course load
- Restricted activities

**Dean's List:**
- Semester GPA ≥ 3.5
- Minimum 12 credit hours
- No grades below B
- Recognition on transcript

**Academic Suspension:**
- Two consecutive semesters on probation
- Cumulative GPA < 1.75
- Must appeal for readmission

**Academic Honors:**
- **Summa Cum Laude**: GPA ≥ 3.9
- **Magna Cum Laude**: GPA 3.7-3.89
- **Cum Laude**: GPA 3.5-3.69

### Viewing Academic Standing

**Check Your Status:**

```bash
# GUI
Student Portal → Academic Status

# Displays:
Current Standing: Good Standing
Cumulative GPA: 3.52
Credits Completed: 45
Dean's List: Fall 2025, Spring 2026
Honors: Magna Cum Laude (Projected)
```

### Improving Academic Standing

**If on Probation:**

1. Meet with academic advisor
2. Create improvement plan
3. Reduce course load if needed
4. Utilize tutoring services
5. Monitor progress regularly

**Resources:**
- Academic support center
- Tutoring services
- Study skills workshops
- Counseling services

---

## Troubleshooting

### Common Issues

**Grade not showing**

**Solution:**
- Instructor may not have submitted grade yet
- Check grade submission deadline
- Verify you're enrolled in the course
- Contact instructor after submission deadline

**GPA calculation seems wrong**

**Solution:**
- Verify all course credits are correct
- Check that all courses are included
- Ensure grade scheme is correct
- P/F courses don't count toward GPA
- Transferred courses may not count

**Can't access transcript**

**Solution:**
- Clear browser cache
- Try different browser
- Check if holds on account (unpaid fees)
- Contact registrar office

**Grade dispute**

**Process:**
1. Contact instructor within 10 days of grade posting
2. Review graded work and rubrics
3. If unresolved, file formal grade appeal
4. Department chair reviews appeal
5. Final decision made

### Error Messages

**"Grade entry locked"**

- Grade submission deadline has passed
- Contact department chair for override
- Provide justification for late entry

**"Invalid GPA value"**

- Check course grading scheme
- Ensure grade entered matches scheme
- Verify credit hours are correct

**"Transcript unavailable"**

- Account may have holds (financial, disciplinary)
- Resolve holds before requesting transcript
- Contact registrar if no holds exist

### Getting Help

**For Students:**
- Academic Advisor: Schedule via student portal
- Registrar Office: registrar@university.edu
- Grade Appeals: Submit via student portal

**For Instructors:**
- IT Support: support@university.edu
- Registrar: Grade submission questions
- Department Chair: Grade disputes

---

## Best Practices

### For Instructors

**Grade Entry:**
- Enter grades promptly after assignments
- Provide meaningful feedback
- Use consistent grading schemes
- Keep grade book updated regularly
- Submit final grades before deadline

**Communication:**
- Post grades within reasonable timeframe
- Respond to grade inquiries promptly
- Explain grading criteria clearly
- Provide mid-semester progress reports

**Fairness:**
- Apply rubrics consistently
- Avoid grade inflation
- Document grade calculations
- Be available for questions

### For Students

**Monitoring Grades:**
- Check grades regularly
- Calculate your own GPA
- Understand course grading schemes
- Keep track of assignment weights
- Use GPA calculator for planning

**Grade Concerns:**
- Review graded work carefully
- Ask questions early
- Understand appeal process
- Keep all graded assignments
- Document grade discrepancies

**Academic Success:**
- Attend class regularly
- Submit assignments on time
- Study consistently
- Seek help when needed
- Monitor your academic standing

---

## Additional Resources

- **GPA Calculator Tool**: [Online Calculator](../../tools/gpa-calculator)
- **Academic Policies**: [Student Handbook](../../docs/policies/ACADEMIC_POLICIES.md)
- **Grading Guidelines**: [Faculty Handbook](../../docs/faculty/GRADING_GUIDELINES.md)
- **API Documentation**: [Grade API](../../docs/development/API.md#grades)

---

**Version**: 1.0
**Last Updated**: January 2026
**Maintained By**: Office of the Registrar
