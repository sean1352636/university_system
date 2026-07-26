# Blockchain Credentials - User Guide

## Overview

The Blockchain Credentials system provides tamper-proof, verifiable academic credentials using blockchain technology. Degrees, certificates, diplomas, and transcripts are issued with unique blockchain hashes, enabling instant verification by employers, graduate schools, and other institutions. The system also supports digital badges, credential wallets, and IPFS-based distributed storage.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Credential Types](#credential-types)
3. [Viewing Your Credentials](#viewing-your-credentials)
4. [Credential Verification](#credential-verification)
5. [Digital Badges](#digital-badges)
6. [Credential Wallet](#credential-wallet)
7. [Sharing Credentials](#sharing-credentials)
8. [For Employers & Verifiers](#for-employers--verifiers)
9. [Administration](#administration)
10. [Technical Details](#technical-details)
11. [Best Practices](#best-practices)
12. [Troubleshooting](#troubleshooting)
13. [Contact Information](#contact-information)

---

## Getting Started

### Accessing Blockchain Credentials

**For Students/Alumni:**
1. Navigate to **Academics** → **Blockchain Credentials**
2. Login with university credentials
3. View your issued credentials

**For Employers/Verifiers:**
1. Navigate to the university's **Credential Verification Portal**
2. Enter the credential hash or verification code
3. View verified credential details

**For Administrators:**
1. Navigate to **Administration** → **Blockchain Credentials**
2. Issue, manage, and revoke credentials

### Understanding Blockchain Credentials

**What Makes Them Different:**
- **Tamper-Proof**: Once issued, credentials cannot be altered
- **Instantly Verifiable**: Anyone with the hash can verify authenticity
- **Permanent**: Credentials persist on the blockchain indefinitely
- **Decentralized**: No single point of failure
- **Self-Sovereign**: Students control their own credentials

---

## Credential Types

### Available Credential Types

| Type | Description | When Issued |
|------|-------------|-------------|
| **Degree** | Bachelor's, Master's, Doctoral degrees | Upon graduation |
| **Certificate** | Program completion certificates | Upon program completion |
| **Diploma** | Professional and academic diplomas | Upon program completion |
| **Transcript** | Official academic transcript | Upon request |

### Credential Information

**Each Credential Contains:**
- Student name and ID
- Credential type
- Program/degree name
- Date of issue
- Issuing institution
- Unique blockchain hash (SHA-256)
- Blockchain address
- IPFS hash (for distributed storage)
- Metadata (honors, GPA, specialization)
- Revocation status

---

## Viewing Your Credentials

### My Credentials

**View Issued Credentials:**
1. Navigate to **Credentials** → **My Credentials**
2. View list of all issued credentials:
   - Credential type and title
   - Issue date
   - Blockchain hash (shortened)
   - Status (active or revoked)
3. Click on any credential for full details

### Credential Details

**Full Credential View:**
- Complete credential information
- Blockchain hash (full SHA-256 hash)
- Blockchain address
- IPFS hash for distributed storage
- Metadata (JSON format with additional details)
- Issue timestamp
- Verification QR code
- Revocation status

---

## Credential Verification

### Verifying a Credential

**Self-Verification:**
1. Navigate to **Credentials** → **Verify**
2. Enter the blockchain hash
3. System checks the hash against the blockchain
4. View verification result:
   - **Verified**: Credential is authentic and active
   - **Revoked**: Credential has been revoked (with date and reason)
   - **Not Found**: Hash does not match any issued credential

### Verification Information Displayed

**Upon Successful Verification:**
- Student name
- Credential type
- Program/degree name
- Date of issue
- Issuing institution
- Current status (active/revoked)
- Timestamp of verification

### QR Code Verification

**Quick Verify:**
- Each credential includes a QR code
- Scan with any QR reader
- Redirects to verification portal
- Instant verification result

---

## Digital Badges

### What Are Digital Badges?

Digital badges are visual representations of achievements, skills, or credentials that can be shared online and verified digitally.

### Viewing Your Badges

**My Badges:**
1. Navigate to **Credentials** → **Digital Badges**
2. View all earned badges:
   - Badge name and image
   - Description of achievement
   - Issue date
   - Issuing authority
   - Verification link

### Badge Types

| Badge Category | Examples |
|---------------|----------|
| **Academic** | Dean's List, Honor Roll, Cum Laude |
| **Skills** | Certified in Python, Data Analytics |
| **Completion** | Course completion, Workshop attendance |
| **Achievement** | Research excellence, Community service |
| **Professional** | Industry certification, Internship completion |

### Sharing Badges

**Display Your Badges:**
- Add to LinkedIn profile
- Embed in email signature
- Share on social media
- Include in digital resume/portfolio
- Each badge includes a verification URL

---

## Credential Wallet

### What is the Credential Wallet?

The credential wallet is your personal digital repository for storing and managing all blockchain credentials and digital badges in one place.

### Wallet Features

**Wallet Management:**
1. Navigate to **Credentials** → **My Wallet**
2. View wallet contents:
   - All credentials and badges
   - Wallet balance (if applicable)
   - Transaction history
3. Actions:
   - **Share**: Send credential to verifier
   - **Download**: Save credential certificate
   - **Print**: Generate printable certificate
   - **Archive**: Move to archive

### Wallet Transactions

**Transaction Types:**
- Credential issuance (credential added to wallet)
- Credential verification (verification request processed)
- Badge issuance (badge added to wallet)
- Credential sharing (sent to third party)

---

## Sharing Credentials

### Sharing with Employers

**Send Credentials:**
1. Navigate to **Credentials** → Select credential
2. Click **Share**
3. Choose sharing method:
   - **Email**: Send verification link via email
   - **Direct Link**: Generate shareable URL
   - **QR Code**: Generate scannable QR code
   - **Download PDF**: Printable certificate with hash
4. Enter recipient details (if emailing)
5. Share

### Sharing with Graduate Schools

**Academic Verification:**
1. Select the credential (transcript or degree)
2. Click **Share for Academic Purposes**
3. Enter the institution's verification email
4. Include a verification message
5. Send credential with full verification details

---

## For Employers & Verifiers

### Verifying Candidate Credentials

**Verification Process:**
1. Receive credential hash or verification link from candidate
2. Visit the university's **Credential Verification Portal**
3. Enter the blockchain hash or click the verification link
4. View verified credential details:
   - Student name and credential type
   - Program and graduation date
   - Verification status (authentic/revoked)
   - Issuing institution confirmation

### Bulk Verification

**For HR Departments:**
- Upload CSV of credential hashes
- Receive batch verification results
- API available for integration with HR systems

---

## Administration

### Issuing Credentials

**Create a Blockchain Credential:**
1. Navigate to **Admin** → **Issue Credential**
2. Select student
3. Choose credential type (degree, certificate, diploma, transcript)
4. Enter credential details:
   - Program name
   - Honors or distinctions
   - Additional metadata
5. System generates:
   - SHA-256 blockchain hash (with timestamp and salt)
   - Blockchain address
   - IPFS hash
6. Credential issued and added to student's wallet
7. Activity logged for audit compliance

### Revoking Credentials

**Revoke a Credential:**
1. Navigate to **Admin** → **Manage Credentials**
2. Search for the credential
3. Click **Revoke**
4. Enter revocation reason
5. Confirm revocation
6. Credential marked as revoked on the blockchain
7. Future verifications will show revoked status

### Badge Management

**Issuing Digital Badges:**
1. Navigate to **Admin** → **Digital Badges**
2. Create badge template (name, image, criteria)
3. Issue badge to student(s)
4. Badge appears in student's wallet

### Reporting

**Available Reports:**
- Credentials issued by type and period
- Verification requests and trends
- Revocation history
- Badge issuance statistics
- System usage metrics

---

## Technical Details

### Blockchain Hash Generation

**How Hashes Are Created:**
- Algorithm: SHA-256
- Input: Credential data + timestamp + random salt
- Output: 64-character hexadecimal hash
- Hash is unique and irreversible

### IPFS Storage

**Distributed Storage:**
- Credential data stored on IPFS (InterPlanetary File System)
- Ensures availability even if centralized systems are offline
- IPFS hash provides content-addressable retrieval
- Redundant storage across the network

### Data Security

- All credential data encrypted at rest
- Transport Layer Security (TLS) for all communications
- Private keys managed securely
- Regular security audits
- Full audit trail for all operations

---

## Best Practices

### For Students

1. **Keep your wallet secure** - Protect your login credentials
2. **Share selectively** - Only share credentials with trusted parties
3. **Verify before sharing** - Confirm your credential is active before sharing
4. **Save backup copies** - Download PDF certificates for personal records
5. **Update your profile** - Keep contact information current for credential delivery

### For Employers

1. **Always verify** - Use the official verification portal, not just the certificate
2. **Check revocation status** - Ensure credentials have not been revoked
3. **Use the hash** - The blockchain hash is the definitive verification method
4. **Contact the university** - For any verification concerns

### For Administrators

1. **Verify student eligibility** - Confirm degree completion before issuing
2. **Document revocations** - Always provide clear reasons for revocation
3. **Regular audits** - Review issued credentials periodically
4. **Keep systems updated** - Maintain blockchain and IPFS connections

---

## Troubleshooting

### Common Issues

**Credential not showing in wallet:**
- Credential may still be processing (allow up to 24 hours)
- Check if the degree/program has been officially conferred
- Contact the Registrar to confirm credential issuance
- Clear browser cache and refresh

**Verification fails:**
- Ensure the full blockchain hash is entered (64 characters)
- Check for copy/paste errors (extra spaces)
- Credential may have been revoked (check status)
- Contact the issuing institution if hash doesn't match

**Cannot share credential:**
- Verify the credential is in active status
- Ensure recipient email address is valid
- Check your internet connection
- Try generating a direct link instead of emailing

**QR code not scanning:**
- Ensure QR code is displayed clearly (not blurry)
- Use a standard QR code reader app
- Try scanning from a printed copy
- Use the direct verification link as an alternative

**Badge not appearing:**
- Badges may take up to 48 hours to appear
- Check with the issuing department
- Verify the badge criteria have been met
- Contact administration if the badge was promised

---

## Contact Information

**Office of the Registrar**
- **Phone**: (555) 123-RGST
- **Email**: registrar@university.edu
- **Location**: Administration Building, Room 110
- **Hours**: Monday-Friday 8:30 AM - 5 PM

**Blockchain Credentials Support**
- **Phone**: (555) 123-BLKC
- **Email**: credentials@university.edu

**Employer Verification Line**
- **Phone**: (555) 123-VRFY
- **Email**: verify@university.edu

---

**Last Updated**: February 2026
**Module**: `university_system/modules/domain/blockchain/gui/blockchain_credentials_gui.py`
**Support**: credentials@university.edu | (555) 123-BLKC
