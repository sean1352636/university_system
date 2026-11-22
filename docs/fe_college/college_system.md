# College System

The FE College system: learners, courses, enrolments, attendance and the Email centre.

## Idle logout

The GUI and CLI log out after 30 minutes of inactivity and return to the login
screen. `EDU_IDLE_TIMEOUT_MINUTES` changes the period and `0` turns it off. The
CLI timer needs `SIGALRM`, so it does nothing on Windows.

## Adding a learner

**Learners → + New learner** (GUI) and **Learners → Add a learner** (CLI) ask for
the same details as the other systems' add-learner forms, in sections:

- **Identity:** legal first, middle and last name, preferred name, date of birth, gender, ULN.
- **Contact** and **home address:** address line 1 and 2, town, and postcode. A UK postcode is
  checked and stored as `HU1 2AA`.
- **Emergency contact:** name, relationship and phone. Name and phone go together; the phone
  must have 7 to 15 digits.
- **Study:** learner type, mode, status, tutor group, personal tutor, start date, prior
  attainment.
- **Needs and medical:** LLDD, EHC Plan, medical notes (up to 2000
  characters), notes.

Before saving, the form checks for a possible duplicate: the same name and date of birth, or
the same e-mail. Staff can still save (twins match). The check is off by default in
`student_service.create(..., check_duplicate=False)`, so cross-system handovers are never
blocked.

**Logins.** A tick box on the form, the **Create login** button, or the CLI's **Create a
learner login** creates the learner's shared login (`services/learner_accounts.py`):

- The username is the student ID, which FE sign-in pairs with the learner record.
- The role is `student` on `fe_college`, with a random 12-character temporary password.
- The password is shown once and e-mailed with the `learner_login` template.
- An existing login is never changed.

**Editing** keeps fields the edit form doesn't show (end date, and so on). It used to rebuild
the record from the form alone and blank them.
