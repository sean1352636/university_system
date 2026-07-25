# Degree Audit System - User Guide

## Overview

The Degree Audit System helps students and advisors track academic progress toward degree completion. It automatically evaluates completed coursework against degree requirements and provides visual progress tracking, what-if scenarios, and graduation planning tools.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Understanding Your Audit](#understanding-your-audit)
3. [Viewing Progress](#viewing-progress)
4. [What-If Analysis](#what-if-analysis)
5. [Planning Tools](#planning-tools)
6. [Graduation Requirements](#graduation-requirements)
7. [Transfer Credit](#transfer-credit)
8. [Multiple Majors & Minors](#multiple-majors--minors)
9. [Troubleshooting](#troubleshooting)

---

## Getting Started

### Accessing Degree Audit

**For Students:**
1. Navigate to **Academics** → **Degree Audit**
2. View your current degree progress
3. No additional login required

**For Advisors:**
1. Navigate to **Advising** → **Student Audits**
2. Search for student by name or ID
3. View student's degree audit

### First-Time View

When you first access the degree audit:
1. System loads your official transcript
2. Applies your declared major(s) and minor(s)
3. Evaluates all completed courses
4. Calculates progress percentages
5. Identifies remaining requirements

**Processing Time:**
- Initial audit: Generated instantly
- Updates after grade posting: Within 24 hours
- After major change: Re-evaluated immediately

---

## Understanding Your Audit

### Audit Structure

Your degree audit is organized into sections:

#### 1. **Header Summary**
- Student name and ID
- Declared major(s), minor(s), concentration
- Expected graduation term
- Overall completion percentage
- Credits earned / Credits required

#### 2. **General Education Requirements**
Shows progress toward university-wide gen ed requirements:
- **Written Communication** (e.g., 2 writing courses)
- **Quantitative Reasoning** (e.g., 1 math course)
- **Natural Sciences** (e.g., 2 science courses with labs)
- **Social Sciences** (e.g., 2 courses from different depts)
- **Humanities** (e.g., 2 courses)
- **Arts** (e.g., 1 course)
- **Global Perspectives** (e.g., 1 course)
- **Diversity Requirement** (often embedded in other courses)

#### 3. **Major Requirements**
- **Core Courses**: Required courses for major
- **Electives**: Specified number of credits from approved list
- **Capstone/Thesis**: Senior project or culminating experience
- **GPA Requirement**: Minimum major GPA (typically 2.0 or 2.5)

#### 4. **Minor Requirements** (if applicable)
- Core courses for minor
- Elective credits
- Minimum grade requirements

#### 5. **Free Electives**
- Additional credits needed to reach degree total (typically 120-128 credits)
- Can be any courses not already counting toward requirements

#### 6. **Additional Requirements**
- **Residency**: Minimum credits at this institution (typically 30)
- **Upper-Level Credits**: 300/400-level courses (typically 40-60)
- **GPA**: Cumulative and major GPA minimums
- **Special Requirements**: Internships, portfolios, exams

### Requirement Status Indicators

**Visual Symbols:**
- ✓ **Green Checkmark**: Requirement completed
- ⚠ **Yellow Warning**: In progress (enrolled this term)
- ✗ **Red X**: Not yet completed
- ℹ **Blue Info**: Exception or substitution applied

**Completion Percentages:**
- Each section shows percentage complete
- Overall degree completion at top
- Progress bars for visual reference

---

## Viewing Progress

### Detailed View

**Expanding Requirements:**
1. Click any requirement section to expand
2. View specific courses that fulfill requirement
3. See which courses you've taken that apply
4. View remaining options

**Example: General Education - Natural Sciences**
```
Natural Sciences (2 courses required, 1 lab required)
✓ BIO101 - Intro to Biology (3 cr, Lab) - Fall 2023 - Grade: A
✗ [1 additional course needed]
   Remaining options: CHEM101, PHYS101, GEOL101...
```

### Course Details

**Click any completed course to view:**
- Course code, title, credits
- Term taken and grade earned
- How it applies (may fulfill multiple requirements)
- Instructor

**For future courses:**
- When course is typically offered (Fall/Spring/Summer)
- Prerequisites
- Add to plan (see Planning Tools)

### Substitutions & Exceptions

**Types of Exceptions:**
- **Transfer Credit**: Courses from other institutions
- **AP/IB Credit**: Advanced placement exam credit
- **Substitution**: Alternative course approved to fulfill requirement
- **Waiver**: Requirement waived (rare, requires approval)

**Viewing Exceptions:**
1. Exceptions highlighted in audit
2. Click to view approval details
3. See approving authority and date
4. Notes explaining reason

---

## What-If Analysis

### Purpose

What-If Analysis lets you explore "what would happen if..." scenarios:
- Changing your major or minor
- Adding a second major or minor
- Switching concentrations
- Different course selections

### Running a What-If Scenario

**Steps:**
1. Navigate to **Degree Audit** → **What-If Analysis**
2. Click **New Scenario**
3. Select changes to apply:
   - **Major**: Choose new major
   - **Minor**: Add or change minor
   - **Concentration**: Select different track
   - **Catalog Year**: Different degree requirements (if you were admitted different year)
4. Click **Run Analysis**
5. View modified audit showing:
   - Requirements for new program
   - Which completed courses still apply
   - New courses you'd need to take
   - New expected graduation date
   - Total credits required

### Comparing Scenarios

**Side-by-Side Comparison:**
1. Create multiple scenarios
2. Click **Compare**
3. View table showing:
   - Requirements different between scenarios
   - Credits required for each
   - Graduation timeline
   - Courses unique to each path

**Example Use Cases:**
- "What if I added a Computer Science minor?" → See 5 additional courses needed
- "What if I switched from Biology to Biochemistry major?" → See overlap and new requirements
- "What if I changed to the Data Science concentration?" → See different electives required

### Saving Scenarios

**Save for Future Reference:**
1. Name your scenario (e.g., "CS Minor Option")
2. Click **Save**
3. Access saved scenarios anytime
4. Share with advisor for discussion

**Making a Scenario Official:**
- If you decide to pursue a what-if scenario
- Work with advisor to officially change major/minor
- Audit will update to reflect official change

---

## Planning Tools

### Multi-Year Planner

**Creating Academic Plan:**
1. Navigate to **Planning** → **Course Planner**
2. View grid with future terms
3. Drag courses from audit into term slots
4. System validates:
   - Prerequisites met
   - Course typically offered that term
   - Credit load reasonable (12-18 credits)
   - No time conflicts (if times known)

**Visual Planning Interface:**
```
Fall 2026         Spring 2027       Fall 2027
-----------       -------------     -----------
CS201 (3 cr)      CS202 (3 cr)      CS301 (3 cr)
MATH201 (4 cr)    MATH202 (4 cr)    CS310 (3 cr)
ENG201 (3 cr)     HIST101 (3 cr)    PHIL201 (3 cr)
GEN101 (3 cr)     GEN102 (3 cr)     Elective (3 cr)
-----------       -------------     -----------
13 credits        13 credits        12 credits
```

**Planning Validation:**
- Red border: Prerequisite not met
- Yellow border: Course may not be offered that term
- Green border: Looks good!

### Graduation Planner

**Working Backward from Graduation:**
1. Set target graduation term
2. Click **Generate Plan**
3. System automatically schedules:
   - Remaining required courses
   - Considers prerequisites (courses in correct order)
   - Balances credit load across terms
   - Accounts for course offering patterns
4. Review and adjust as needed

**Graduation Timeline:**
- Shows semester-by-semester plan
- Highlights critical path courses (must take on schedule)
- Suggests summer sessions if needed to stay on track
- Updates if you change graduation target

### Course Recommendations

**Integrated Recommendations:**
- Based on audit, system suggests next courses to take
- Prioritizes major requirements and prerequisites
- Considers graduation timeline
- Suggests gen ed courses that fit schedule

---

## Graduation Requirements

### Overall Requirements Summary

**Typical Bachelor's Degree:**
- **Total Credits**: 120-128 (varies by major)
- **Residency**: Minimum 30 credits at this institution
- **Upper-Level**: Minimum 40-60 credits at 300/400-level
- **Major Credits**: Typically 36-48
- **General Education**: Typically 30-40 credits
- **Cumulative GPA**: Minimum 2.0
- **Major GPA**: Minimum 2.0-2.5 (varies)

### Checking Graduation Eligibility

**Graduation Eligibility Checker:**
1. Navigate to **Graduation** → **Eligibility**
2. System evaluates all requirements
3. View results:
   - ✓ **Eligible**: All requirements met/on track
   - ⚠ **On Track**: Expected to complete with current plan
   - ✗ **Not Eligible**: Deficiencies identified

**If Not Eligible:**
- Lists specific deficiencies
- Suggests courses to fulfill requirements
- Projects new graduation date
- Option to request advisor meeting

### Applying for Graduation

**When to Apply:**
- Typically 2 semesters before expected graduation
- Deadlines: October 15 (May graduation), March 15 (December graduation)

**Application Process:**
1. Navigate to **Graduation** → **Apply**
2. Verify all information correct
3. Confirm major(s), minor(s), honors
4. Submit application (may include fee)
5. Receive confirmation email

**Post-Application:**
- Registrar reviews audit
- Identifies any issues or missing requirements
- You receive final audit review
- Make corrections if needed
- Degree conferred at term end if all requirements met

---

## Transfer Credit

### Viewing Transfer Credit

**How Transfer Credit Appears:**
1. Transfer courses listed in "Transfer Credit" section
2. Shows:
   - Institution name
   - Course number and title (from sending institution)
   - Equivalent course here (if applicable)
   - Credits awarded
   - How it applies to degree

**Example:**
```
Transfer Credit from State Community College
TC: ENG101 → ENG101 (3 cr) - Applies to Gen Ed: Written Communication
TC: MATH151 → MATH101 (4 cr) - Applies to Gen Ed: Quantitative Reasoning
TC: HIST201 → Elective Credit (3 cr) - Free elective
```

### Transfer Credit Evaluation

**Evaluation Process:**
1. Submit official transcript from previous institution
2. Registrar evaluates courses (typically 2-4 weeks)
3. Determine equivalencies
4. Credit appears in audit

**If You Disagree with Evaluation:**
1. Navigate to **Transfer Credit** → **Appeal**
2. Provide course syllabus and materials
3. Explain why course should count differently
4. Department reviews appeal
5. Receive decision (typically 2 weeks)

---

## Multiple Majors & Minors

### Double Majors

**How Audits Handle Double Majors:**
- Separate section for each major
- Courses can count toward both majors (if allowed)
- System shows "shared courses" between majors
- Total credit requirement may be higher

**Viewing Double Major Audit:**
1. Both majors listed in header
2. Toggle between major views
3. View combined requirements
4. See total credits needed (not simply sum of both)

### Adding a Minor

**Impact on Audit:**
1. Navigate to **What-If** → Add minor
2. See additional requirements
3. Check if completed courses fulfill minor requirements
4. Plan remaining courses

**Officially Declaring Minor:**
1. Work with advisor
2. Submit declaration form
3. Audit updates within 24 hours
4. Minor requirements now tracked

---

## Troubleshooting

### Common Issues

**Issue: "Course not applying to requirement"**

**Possible Causes:**
- Course taken at another institution not yet evaluated
- Course doesn't actually fulfill requirement (check catalog)
- System error

**Solutions:**
- Check with advisor
- Verify course in catalog
- Submit exception request if course should count

**Issue: "Completion percentage doesn't look right"**

**Possible Causes:**
- Recent grade not yet posted
- Major change not processed
- Transfer credit not applied

**Solutions:**
- Wait 24 hours after grades post
- Verify major/minor in student profile
- Contact registrar about transfer credit

**Issue: "Can't run what-if analysis"**

**Solutions:**
- Ensure browser cookies enabled
- Try different browser
- Clear cache
- Contact IT support

### Getting Help

**Academic Advising:**
- Schedule appointment: `advising.university.edu`
- Email: advising@university.edu
- Phone: (555) 123-ADVISE

**Registrar's Office:**
- Email: registrar@university.edu
- Phone: (555) 123-4567
- Walk-in: Monday-Friday, 8:30 AM - 5 PM

**Technical Support:**
- Email: itsupport@university.edu
- Phone: (555) 123-HELP

---

## Best Practices

### For Students

1. **Check Regularly**: Review audit each term after grades post
2. **Plan Ahead**: Use planner to map out path to graduation
3. **Meet with Advisor**: At least once per year to review audit
4. **Understand Requirements**: Don't just look at percentages, understand what's needed
5. **Apply for Graduation Early**: Don't miss deadlines
6. **Explore Options**: Use what-if analysis to consider adding minor or changing major

### For Advisors

1. **Review with Students**: Walk through audit together
2. **Explain Exceptions**: Clarify any substitutions or transfer credit
3. **Use What-If**: Explore options collaboratively
4. **Print for Reference**: Provide paper copy of audit and plan
5. **Set Goals**: Help student set realistic graduation timeline
6. **Follow Up**: Check progress each term

---

## Additional Resources

- **Degree Requirements Catalog**: `catalog.university.edu`
- **Course Planner Tutorial**: `video.university.edu/degree-audit`
- **Transfer Credit Guide**: `docs/transfer_credit_guide.pdf`
- **Graduation Application**: `registrar.university.edu/graduation`

---

**Last Updated**: January 2026
**Module**: `university_system/modules/domain/academics/gui/degree_audit_gui.py`
**Support**: advising@university.edu | (555) 123-ADVISE
