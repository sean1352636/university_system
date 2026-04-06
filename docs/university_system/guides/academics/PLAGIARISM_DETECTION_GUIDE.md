# Plagiarism Detection System - User Guide

## Overview

The Plagiarism Detection system provides comprehensive tools for checking student submissions against a document repository and external sources. It uses N-gram similarity analysis, content hashing, and NLP-based text processing to identify potential plagiarism. The system supports document submission, batch processing, advanced search, document comparison, and detailed statistical reporting.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Submitting Documents](#submitting-documents)
3. [Running Plagiarism Checks](#running-plagiarism-checks)
4. [Understanding Results](#understanding-results)
5. [Document Repository](#document-repository)
6. [Batch Operations](#batch-operations)
7. [Document Comparison](#document-comparison)
8. [Search & Advanced Search](#search--advanced-search)
9. [Statistics & Reports](#statistics--reports)
10. [Administration](#administration)
11. [Best Practices](#best-practices)
12. [Troubleshooting](#troubleshooting)
13. [Contact Information](#contact-information)

---

## Getting Started

### Accessing the Plagiarism Checker

**For Faculty:**
1. Navigate to **Academics** → **Plagiarism Detection**
2. Login with faculty credentials
3. Access the plagiarism checking dashboard

**For Administrators:**
1. Navigate to **Administration** → **Academic Integrity** → **Plagiarism Detection**
2. Full access to all detection and repository features

### Plagiarism Checker Dashboard

**Dashboard Overview:**
- **Recent Checks**: Latest plagiarism analysis results
- **Document Repository**: Total documents in the comparison database
- **Flagged Submissions**: Documents exceeding similarity thresholds
- **Quick Check**: Direct access to run a new check

---

## Submitting Documents

### Adding a Document to the System

**Submit for Checking:**
1. Navigate to **Submission** → **Submit Document**
2. Upload or enter the document:
   - **Upload File**: PDF, DOCX, or TXT format
   - **Paste Text**: Copy and paste text directly
3. Enter document metadata:
   - **Title**: Document or assignment title
   - **Author**: Student name or ID
   - **Module Code**: Course/module identifier
   - **Submission Date**: Date of submission
4. Choose action:
   - **Check Only**: Run plagiarism check without adding to repository
   - **Check and Add**: Run check and add to repository for future comparisons
5. Submit

### Supported File Formats

| Format | Extension | Notes |
|--------|-----------|-------|
| **PDF** | .pdf | Text extracted automatically (not scanned images) |
| **Word** | .docx | Full text and formatting extracted |
| **Plain Text** | .txt | Direct text processing |

### File Conversion

**Converting Documents:**
1. Navigate to **Tools** → **File Converter**
2. Upload file in unsupported format
3. Select target format (PDF, DOCX, TXT)
4. Convert and download
5. Submit converted file for checking

---

## Running Plagiarism Checks

### Single Document Check

**Run a Check:**
1. Navigate to **Check** → **New Check**
2. Select or upload the document
3. Configure check settings:
   - **Similarity Threshold**: Default 30% (adjustable 10-90%)
   - **N-gram Size**: Default 3 (controls granularity of comparison)
   - **Check Against**: Repository, internet sources, or both
4. Click **Run Check**
5. View results when complete

### How Detection Works

**Detection Methods:**

1. **Content Hashing**: Generates a unique hash for the document; detects exact copies instantly
2. **N-gram Similarity**: Breaks text into overlapping word sequences (default size 3) and compares against the repository using cosine similarity
3. **Text Preprocessing**: Tokenization, stopword removal, and normalization using NLTK
4. **Cross-Reference**: Compares against all documents in the repository

### Check Configuration

| Setting | Default | Range | Description |
|---------|---------|-------|-------------|
| **Similarity Threshold** | 30% | 10-90% | Minimum similarity to flag |
| **N-gram Size** | 3 | 2-5 | Word sequence length for comparison |
| **Include Self-Citations** | No | Yes/No | Exclude student's own prior work |
| **Check Internet** | No | Yes/No | Search external sources |

---

## Understanding Results

### Plagiarism Report

**Report Sections:**

1. **Overall Similarity Score**: Percentage of content matching other sources
2. **Source Breakdown**: List of matching documents with individual similarity scores
3. **Highlighted Matches**: Text passages that match other sources, color-coded by source
4. **Match Details**: For each match:
   - Source document title and author
   - Module code and submission date
   - Percentage of matching text
   - Matched text passages side by side

### Score Interpretation

| Similarity Score | Risk Level | Recommendation |
|------------------|-----------|----------------|
| 0-15% | Low | Acceptable - common phrases and references |
| 16-30% | Moderate | Review flagged sections; may be properly cited |
| 31-50% | High | Investigation needed; significant overlap detected |
| 51-75% | Very High | Likely plagiarism; formal review required |
| 76-100% | Critical | Near-identical match; immediate action required |

### Review Actions

**After Reviewing Results:**
- **Clear**: Mark as reviewed, no plagiarism found
- **Flag**: Mark for further investigation
- **Refer**: Send to academic integrity office
- **Add Notes**: Document your findings
- **Download Report**: Save PDF report for records

---

## Document Repository

### About the Repository

The document repository stores all submitted documents for comparison. New submissions are checked against this growing collection to identify matches across courses, semesters, and years.

### Managing the Repository

**Repository Actions:**
1. Navigate to **Repository** → **Manage**
2. View repository contents:
   - Total document count
   - Documents by module/course
   - Documents by semester/year
3. Actions:
   - **Add Document**: Add to repository without running a check
   - **Remove Document**: Delete from repository (with tracking)
   - **Integrity Check**: Verify repository consistency
   - **Search**: Find documents by title, author, or module code

### Repository Search

**Finding Documents:**
1. Navigate to **Repository** → **Search**
2. Search by:
   - Keywords in title or content
   - Author name
   - Module code
   - Date range
3. View results with metadata
4. Open document details

---

## Batch Operations

### Batch Plagiarism Checking

**Process Multiple Documents:**
1. Navigate to **Batch** → **Batch Check**
2. Select documents:
   - Upload multiple files at once
   - Select from a course's submissions
   - Choose by date range
3. Configure batch settings:
   - Similarity threshold
   - Add to repository option
4. Start batch processing
5. Monitor progress
6. View consolidated results when complete

### Batch Results

**Batch Report:**
- Summary of all checked documents
- Number flagged vs. clean
- Sorted by similarity score (highest first)
- Export full batch report (PDF or CSV)
- Individual document reports accessible

---

## Document Comparison

### Comparing Two Documents

**Side-by-Side Comparison:**
1. Navigate to **Compare** → **Document Comparison**
2. Select or upload two documents
3. Click **Compare**
4. View results:
   - Similarity percentage between the two documents
   - Highlighted matching passages in both documents
   - Side-by-side view with color-coded matches
   - Summary of matching sections

### When to Use Comparison

- Suspected collaboration between students
- Checking revised submissions against originals
- Verifying proper paraphrasing
- Investigating specific plagiarism allegations

---

## Search & Advanced Search

### Basic Search

**Quick Document Search:**
1. Navigate to **Search**
2. Enter search term
3. View matching documents from the repository
4. Click to view document details and check history

### Advanced Search

**Detailed Search Options:**
1. Navigate to **Search** → **Advanced Search**
2. Filter by:
   - **Author**: Student name or ID
   - **Module Code**: Course identifier
   - **Date Range**: Submission period
   - **Similarity Score Range**: Only flagged documents
   - **Keywords**: Content search terms
   - **Status**: Checked, flagged, cleared, referred
3. Sort results by relevance, date, or score
4. Export search results

---

## Statistics & Reports

### Viewing Statistics

**Plagiarism Statistics:**
1. Navigate to **Statistics**
2. View aggregate data:
   - Total documents checked
   - Average similarity scores
   - Flagged submission rates
   - Detection trends over time
   - Top matching source documents

### Generating Reports

**Report Types:**
- **Course Report**: Plagiarism rates for a specific course
- **Department Report**: Aggregate statistics by department
- **Semester Report**: Trends across a semester
- **Individual Student Report**: Check history for a student
- **Repository Report**: Repository health and statistics

**Creating a Report:**
1. Navigate to **Reports** → **Generate**
2. Select report type
3. Set parameters (course, date range, etc.)
4. Choose format (PDF, CSV)
5. Generate and download

---

## Administration

### System Testing

**Validation Tools:**
1. Navigate to **Admin** → **System Testing**
2. Run diagnostic checks:
   - Repository integrity verification
   - Detection accuracy testing (with known samples)
   - Performance benchmarks
   - Text extraction validation

### Backup & Restore

**Data Protection:**
1. Navigate to **Admin** → **Backup/Restore**
2. **Backup**: Create snapshot of repository and results
3. **Restore**: Restore from previous backup
4. Schedule automatic backups

### Workflow Management

**Configure Workflows:**
- Define review process for flagged submissions
- Set up escalation paths
- Configure automatic notifications
- Manage reviewer assignments

### System Configuration

**Admin Settings:**
- Default similarity threshold
- Repository size limits
- Retention policies for old documents
- Integration with assignment system
- Email notification templates

---

## Best Practices

1. **Set clear expectations** - Inform students about plagiarism policies before assignments
2. **Use appropriate thresholds** - Technical subjects may have higher baseline similarity
3. **Review flagged sections** - Always manually review before concluding plagiarism
4. **Consider context** - Common phrases, technical terms, and quotes will appear as matches
5. **Add to repository** - Build the repository over time for more comprehensive detection
6. **Run batch checks** - Check all submissions for an assignment together for cross-comparison
7. **Document findings** - Keep records of all checks and outcomes for consistency

---

## Troubleshooting

### Common Issues

**Check returns no results:**
- Verify the document contains extractable text (not a scanned image)
- Check that the repository has documents to compare against
- Ensure the file was uploaded successfully
- Try pasting text directly instead of uploading

**Text extraction fails:**
- PDF may be image-based; use OCR first
- DOCX may be corrupted; try re-saving
- File may be password-protected; remove protection first
- Check that the file is within size limits

**Similarity score seems too high:**
- Review flagged sections to check for properly cited quotes
- Common phrases and technical terminology can inflate scores
- Student's own prior submissions may be in the repository (enable self-citation exclusion)
- Adjust the similarity threshold for the subject area

**Batch processing stalled:**
- Large batches may take time; check progress indicator
- Verify all files in the batch are valid formats
- Check available system resources
- Try smaller batch sizes

**Cannot add to repository:**
- Verify you have admin or faculty permissions
- Check that the document meets format requirements
- Ensure the repository is not at capacity
- Try removing and re-adding the document

---

## Contact Information

**Academic Integrity Office**
- **Phone**: (555) 123-INTG
- **Email**: integrity@university.edu
- **Location**: Academic Services Building, Room 402
- **Hours**: Monday-Friday 9 AM - 5 PM

**Plagiarism Detection Support**
- **Phone**: (555) 123-PLAG
- **Email**: plagiarism-support@university.edu

**IT Technical Support**
- **Phone**: (555) 123-TECH
- **Email**: techsupport@university.edu

---

**Last Updated**: February 2026
**Module**: `university_system/modules/domain/academics/services/plagiarism/plagiarism_main.py`
**Support**: integrity@university.edu | (555) 123-INTG
