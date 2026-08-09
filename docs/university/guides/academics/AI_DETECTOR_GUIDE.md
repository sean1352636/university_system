# AI Detector & Academic Integrity - User Guide

## Overview

The AI Detector and Academic Integrity system provides advanced tools for detecting AI-generated content in student submissions. It combines multiple detection methods including text analysis, model fingerprinting, citation verification, and blockchain-based verification. The system supports batch processing, real-time analysis, course-level alerts, student analytics, and comprehensive compliance reporting for faculty and administrators.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Submission Analysis](#submission-analysis)
3. [Batch Processing](#batch-processing)
4. [Detection Methods](#detection-methods)
5. [Course Alerts & Monitoring](#course-alerts--monitoring)
6. [Student Analytics](#student-analytics)
7. [History & Statistics](#history--statistics)
8. [Advanced Features](#advanced-features)
9. [Export & Import](#export--import)
10. [Settings & Configuration](#settings--configuration)
11. [Administration](#administration)
12. [Best Practices](#best-practices)
13. [Troubleshooting](#troubleshooting)
14. [Contact Information](#contact-information)

---

## Getting Started

### Accessing the AI Detector

**For Faculty:**
1. Navigate to **Academics** → **AI Detector**
2. Login with faculty credentials
3. Access the detection dashboard

**For Administrators:**
1. Navigate to **Administration** → **Academic Integrity** → **AI Detector**
2. Full access to all detection features and institutional reports

**For Academic Integrity Officers:**
1. Navigate to **Academic Integrity** → **AI Detection Suite**
2. Access investigation tools and compliance reports

### AI Detector Dashboard

**Dashboard Widgets:**
- **Recent Analyses**: Latest detection results
- **Alert Summary**: Active course-level alerts
- **Detection Statistics**: Aggregate detection rates
- **Pending Reviews**: Submissions flagged for review
- **System Health**: Model performance metrics

---

## Submission Analysis

### Analyzing a Single Submission

**Run Detection Analysis:**
1. Navigate to **Analysis** → **New Analysis**
2. Submit content for analysis:
   - **Paste Text**: Copy and paste submission text directly
   - **Upload File**: Upload document (PDF, DOCX, TXT)
   - **From Assignment**: Link to assignment system submission
3. Select analysis options:
   - Detection sensitivity (low, medium, high)
   - Analysis depth (quick scan, standard, comprehensive)
   - Include citation verification
4. Click **Analyze**
5. View results

### Understanding Results

**Detection Report:**
- **AI Probability Score**: Percentage likelihood of AI generation (0-100%)
- **Confidence Level**: Low, medium, or high confidence in detection
- **Flagged Sections**: Specific passages identified as potentially AI-generated
- **Writing Pattern Analysis**: Consistency with student's prior work
- **Citation Integrity**: Verification of cited sources

**Score Interpretation:**

| Score Range | Interpretation | Recommended Action |
|-------------|---------------|-------------------|
| 0-20% | Likely human-written | No action needed |
| 21-40% | Mostly human, minor flags | Optional review |
| 41-60% | Mixed signals | Closer review recommended |
| 61-80% | Likely AI-assisted | Investigation recommended |
| 81-100% | Highly likely AI-generated | Formal review required |

### Reviewing Flagged Content

**Detailed View:**
1. Click on a flagged section
2. View:
   - Highlighted text passage
   - Specific detection indicators
   - Comparison with student's writing style
   - Suggested questions for follow-up
3. Mark as:
   - **Confirmed AI**: Evidence supports AI generation
   - **False Positive**: Not AI-generated
   - **Inconclusive**: Requires further investigation

---

## Batch Processing

### Processing Multiple Submissions

**Batch Analysis:**
1. Navigate to **Batch Processing**
2. Select submissions:
   - **By Course**: All submissions for a course/assignment
   - **Upload Multiple**: Upload multiple documents at once
   - **Date Range**: Submissions within a period
3. Configure batch settings:
   - Detection sensitivity
   - Analysis depth
   - Priority level
4. Click **Start Batch**
5. Monitor progress in real-time

### Batch Results

**Viewing Batch Results:**
- Summary dashboard with aggregate statistics
- Individual results for each submission
- Sort by AI probability score (highest first)
- Filter by flagged/clean status
- Export full batch report

---

## Detection Methods

### Text Analysis

**Linguistic Patterns:**
- Sentence structure uniformity
- Vocabulary complexity distribution
- Paragraph coherence patterns
- Writing style consistency
- Grammar and punctuation patterns

### Model Fingerprinting

**AI Model Detection:**
- Identifies patterns characteristic of specific AI models
- Detects ChatGPT, Claude, Gemini, and other LLM outputs
- Analyzes token distribution patterns
- Identifies repetitive phrasing patterns

### Citation Verification

**Source Checking:**
- Verifies cited sources actually exist
- Checks that citations match claimed content
- Identifies fabricated or hallucinated references
- Cross-references with academic databases

### Multimodal Analysis

**Beyond Text:**
- Image analysis for AI-generated visuals
- Code analysis for AI-generated programming assignments
- Presentation slide analysis
- Cross-modal consistency checking

### Blockchain Verification

**Integrity Chain:**
- Submission fingerprinting with blockchain hashes
- Tamper-proof submission records
- Verification of original submission timestamps
- Chain-of-custody for academic documents

---

## Course Alerts & Monitoring

### Setting Up Course Alerts

**Configure Alerts:**
1. Navigate to **Alerts** → **Course Monitoring**
2. Select course(s) to monitor
3. Set alert thresholds:
   - **Warning**: AI score above X% (e.g., 50%)
   - **Critical**: AI score above Y% (e.g., 80%)
4. Choose notification method:
   - Email notification
   - Dashboard alert
   - Both
5. Enable automatic scanning for new submissions
6. Save alert configuration

### Managing Alerts

**Alert Actions:**
- **View Details**: See the full analysis for the flagged submission
- **Investigate**: Open formal investigation workflow
- **Dismiss**: Mark as reviewed, no action needed
- **Escalate**: Forward to academic integrity office
- **Add Notes**: Document review findings

---

## Student Analytics

### Writing Profile

**Student Writing Analysis:**
1. Navigate to **Student Analytics** → Select Student
2. View writing profile:
   - Historical writing style patterns
   - Average AI detection scores over time
   - Submission frequency and patterns
   - Comparative analysis across courses

### Trend Detection

**Monitoring Patterns:**
- Sudden changes in writing quality or style
- Increasing AI detection scores over time
- Inconsistencies between in-class and take-home work
- Cross-course pattern comparison

---

## History & Statistics

### Detection History

**View Past Analyses:**
1. Navigate to **History**
2. Browse all past detection analyses
3. Filter by:
   - Date range
   - Course
   - Student
   - Detection score range
   - Result status (flagged, clean, reviewed)
4. Sort by date, score, or course

### Statistical Reports

**Available Statistics:**
- Overall detection rates by period
- Detection rates by course, department, or assignment type
- False positive/negative rates
- Trend analysis over semesters
- Comparative benchmarks

---

## Advanced Features

### Adversarial Testing

**Test Detection Robustness:**
- Submit known AI-generated content to test sensitivity
- Evaluate detection of paraphrased AI content
- Test with mixed human/AI content
- Calibrate detection thresholds

### Model Security

**System Protection:**
- Monitor for detection bypass attempts
- Track adversarial attack patterns
- Update detection models
- Security audit logging

### Compliance & Bias Detection

**Fairness Monitoring:**
- Analyze detection rates across demographics
- Check for bias in flagging patterns
- Generate compliance reports
- Document due process adherence
- FERPA compliance verification

### API Integration

**Visual API Interface:**
- Connect with external plagiarism services
- Integrate with LMS platforms
- Automated submission pipeline
- Custom webhook configurations

### Federated Learning

**Collaborative Detection:**
- Participate in federated model training
- Share detection patterns (anonymized)
- Benefit from cross-institutional learning
- Privacy-preserving model updates

---

## Export & Import

### Exporting Results

**Export Options:**
1. Navigate to **Export/Import** → **Export**
2. Select data to export:
   - Individual analysis results
   - Batch processing reports
   - Course-level summaries
   - Student analytics
3. Choose format:
   - PDF (formatted report)
   - CSV (raw data)
   - JSON (structured data)
4. Generate and download

### Importing Data

**Import Options:**
- Upload previous analysis results
- Import student submissions in bulk
- Load configuration settings
- Import writing samples for baseline

---

## Settings & Configuration

### Detection Settings

**Configure Detection Parameters:**
1. Navigate to **Settings** → **Detection**
2. Adjust settings:
   - Default sensitivity level
   - Analysis depth preference
   - Auto-scan toggle for new submissions
   - Score thresholds for alerts
   - Citation verification sources

### Notification Settings

**Alert Preferences:**
- Email notification frequency (immediate, daily digest, weekly)
- Dashboard alert display duration
- Escalation rules
- Auto-dismiss rules for low scores

### Advanced Settings

**System Configuration:**
- Model update schedule
- Batch processing limits
- Data retention policies
- API key management
- Integration configurations

---

## Administration

### Institutional Reporting

**Administrative Reports:**
1. Navigate to **Admin** → **Reports**
2. Generate institutional reports:
   - Academic integrity case summary
   - Detection rates by department
   - Faculty usage statistics
   - System performance metrics
   - Compliance documentation

### Policy Configuration

**Manage Policies:**
- Define AI usage policies per department
- Set allowable AI assistance levels
- Configure violation workflows
- Define escalation procedures
- Set sanction guidelines

### User Management

**Managing Access:**
- Assign faculty access to courses
- Grant investigator privileges
- Set up department administrators
- Audit user activity logs

---

## Best Practices

1. **Use as one tool among many** - AI detection should supplement, not replace, academic judgment
2. **Follow up on flags** - Always discuss flagged submissions with students before concluding
3. **Maintain fairness** - Apply detection consistently across all students
4. **Calibrate thresholds** - Set appropriate sensitivity for the assignment type
5. **Document everything** - Keep records of all detection results and follow-up actions
6. **Stay current** - AI detection models evolve; keep settings and models updated
7. **Communicate policies** - Ensure students understand AI usage policies before assignments

---

## Troubleshooting

### Common Issues

**Analysis takes too long:**
- Large documents take longer; check file size
- Comprehensive analysis is slower than quick scan
- Batch processing runs in the background; check progress later
- Contact support if processing exceeds 10 minutes for a single document

**Detection score seems inaccurate:**
- Review flagged sections manually
- Consider the student's writing history
- Check if content is highly technical (may trigger false positives)
- Adjust sensitivity settings if needed
- Use multiple analysis methods for confirmation

**Cannot access course submissions:**
- Verify you are assigned as instructor for the course
- Check that the assignment submission period has started
- Ensure students have submitted work
- Contact admin if permissions seem incorrect

**Export not generating:**
- Large exports may take time; check download queue
- Verify your browser allows file downloads
- Try a different export format
- Reduce date range or scope

**Alerts not triggering:**
- Verify alert thresholds are set correctly
- Check that auto-scanning is enabled for the course
- Ensure notification email is correct
- Verify the alert is not in dismissed status

---

## Contact Information

**Academic Integrity Office**
- **Phone**: (555) 123-INTG
- **Email**: integrity@university.edu
- **Location**: Academic Services Building, Room 402
- **Hours**: Monday-Friday 9 AM - 5 PM

**AI Detection Support**
- **Phone**: (555) 123-AIDE
- **Email**: aidetector@university.edu

**Faculty Support**
- **Phone**: (555) 123-FCLT
- **Email**: facultysupport@university.edu

---

**Last Updated**: February 2026
**Module**: `university_system/modules/domain/academics/gui/ai_detector/main.py`
**Support**: integrity@university.edu | (555) 123-INTG
