# Budgeting Tool & Portfolio/ePortfolio Guide

This guide covers the student budgeting tools, expense tracking, meal plan management, textbook comparison, savings goals, and the digital portfolio (ePortfolio) system within the University Management System.

## Table of Contents

- [Overview](#overview)
- [Budgeting Tool](#budgeting-tool)
  - [Budget Management](#budget-management)
  - [Expense Tracking](#expense-tracking)
  - [Income Tracking](#income-tracking)
  - [Meal Plan Management](#meal-plan-management)
  - [Textbook Price Comparison](#textbook-price-comparison)
  - [Savings Goals](#savings-goals)
  - [Budget Alerts](#budget-alerts)
- [Portfolio / ePortfolio](#portfolio--eportfolio)
  - [Creating a Portfolio](#creating-a-portfolio)
  - [Portfolio Items](#portfolio-items)
  - [Skills & Endorsements](#skills--endorsements)
  - [Badges & Achievements](#badges--achievements)
  - [Resume Generation](#resume-generation)
  - [Public Profile](#public-profile)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)

## Overview

The system provides two complementary tools: a comprehensive Budgeting Tool for managing student finances, and a Portfolio/ePortfolio system for building and showcasing academic and professional accomplishments.

**Key files:**
- Budget Service: `modules/domain/budget/services/budget_service.py`
- Portfolio Service: `modules/domain/portfolio/services/portfolio_service.py`

---

## Budgeting Tool

### Budget Management

Create and manage budgets by period:

```python
from university_system.modules.domain.budget.services.budget_service import BudgetManager

manager = BudgetManager()

# Create a budget plan
manager.create_budget(
    student_id='S-12345',
    budget_type='monthly',       # monthly, weekly, semester, annual, custom
    amount=1500.00,
    start_date='2025-09-01',
    end_date='2025-09-30',
    description='September 2025 Budget'
)

# Get student budgets
budgets = manager.get_student_budgets(student_id='S-12345')

# Get detailed budget summary
summary = manager.get_budget_summary(student_id='S-12345', budget_id='bud_001')
# Returns: total budget, spent, remaining, category breakdown, projections
```

**Budget Types:**

| Type | Description |
|------|-------------|
| Monthly | Calendar month budget |
| Weekly | 7-day rolling budget |
| Semester | Full semester period |
| Annual | Academic year budget |
| Custom | User-defined date range |

### Expense Tracking

Log and categorize daily expenses:

```python
from university_system.modules.domain.budget.services.budget_service import ExpenseManager

expenses = ExpenseManager()

# Add an expense
expenses.add_expense(
    student_id='S-12345',
    amount=45.50,
    category='Food',
    description='Lunch at campus cafe',
    payment_method='meal-plan',
    tags='campus,lunch'
)

# Get expense history
history = expenses.get_student_expenses(
    student_id='S-12345',
    start_date='2025-09-01',
    end_date='2025-09-30'
)

# Category breakdown
by_category = expenses.get_spending_by_category(student_id='S-12345')

# 30-day spending trends
trends = expenses.get_spending_trends(student_id='S-12345')

# Update an expense
expenses.update_expense(
    expense_id='exp_001',
    amount=42.00,
    description='Updated: Lunch at campus cafe'
)

# Delete an expense
expenses.delete_expense(expense_id='exp_001')
```

**Payment Methods:**

| Method | Description |
|--------|-------------|
| Cash | Physical cash payment |
| Debit | Debit card transaction |
| Credit | Credit card transaction |
| Meal-plan | Campus meal plan deduction |
| Financial-aid | Financial aid funds |
| Other | Other payment method |

**Expense Categories:**

| Category Type | Examples |
|---------------|----------|
| Essential | Tuition, Rent, Textbooks, Insurance |
| Discretionary | Dining out, Entertainment, Shopping |
| Savings | Emergency fund, Travel savings |
| Debt | Student loan payments, Credit card |

### Income Tracking

```python
from university_system.modules.domain.budget.services.budget_service import IncomeManager

income = IncomeManager()

# Add an income source
income.add_income(
    student_id='S-12345',
    amount=500.00,
    source='work-study',
    description='Library assistant - September',
    date='2025-09-30'
)

# Get income history
records = income.get_student_income(student_id='S-12345')
```

**Income Sources:**

| Source | Description |
|--------|-------------|
| Work-study | Campus work-study program |
| Scholarship | Scholarship disbursement |
| Grant | Grant funding |
| Loan | Student loan disbursement |
| Family | Family financial support |
| Job | Part-time or full-time employment |
| Investment | Investment returns |
| Other | Other income source |

### Meal Plan Management

Track meal plan usage and project remaining balance:

```python
from university_system.modules.domain.budget.services.budget_service import MealPlanManager

meals = MealPlanManager()

# Initialize meal plan tracking
meals.create_meal_plan_tracking(
    student_id='S-12345',
    plan_name='Gold Plan',
    total_meals=200,
    total_flex_dollars=500.00,
    start_date='2025-09-01',
    end_date='2025-12-15'
)

# Log a meal transaction
meals.log_meal_transaction(
    student_id='S-12345',
    transaction_type='meal',  # meal or flex_dollar
    amount=1,                 # 1 meal swipe or dollar amount
    location='Main Dining Hall'
)

# Check plan status with projections
status = meals.get_meal_plan_status(student_id='S-12345')
# Returns: meals_used, meals_remaining, flex_used, flex_remaining,
#          pace (fast/on-track/slow), projected_end_date

# Get meal history
history = meals.get_meal_history(student_id='S-12345')
```

**Pace Analysis:**

| Pace | Meaning |
|------|---------|
| Fast | Using meals faster than sustainable |
| On-track | Usage aligned with plan duration |
| Slow | Under-utilizing the meal plan |

### Textbook Price Comparison

Compare textbook prices across vendors:

```python
from university_system.modules.domain.budget.services.budget_service import (
    TextbookComparisonManager
)

textbooks = TextbookComparisonManager()

# Add a textbook listing
textbooks.add_textbook_listing(
    isbn='978-0134685991',
    title='Effective Java',
    vendor='Campus Bookstore',
    price=54.99,
    condition='new',  # new, like-new, good, acceptable, digital
    is_rental=False
)

# Compare prices across vendors
comparison = textbooks.compare_textbook_prices(isbn='978-0134685991')
# Returns: all listings sorted by price, savings vs. new price

# Get best deals
deals = textbooks.get_best_textbook_deals(
    isbn='978-0134685991',
    condition_preference='used'
)

# Record a purchase
textbooks.record_textbook_purchase(
    student_id='S-12345',
    listing_id='list_001',
    purchase_price=32.50
)
```

**Textbook Conditions:**

| Condition | Description |
|-----------|-------------|
| New | Brand new, unused |
| Like-new | Minimal wear |
| Good | Normal wear, fully readable |
| Acceptable | Heavy wear but functional |
| Digital | eBook or digital format |

### Savings Goals

Set and track financial goals:

```python
from university_system.modules.domain.budget.services.budget_service import SavingsGoalManager

savings = SavingsGoalManager()

# Create a savings goal
savings.create_goal(
    student_id='S-12345',
    goal_name='Spring Break Trip',
    target_amount=800.00,
    deadline='2025-03-01',
    priority='high'
)

# Update progress
savings.update_goal_progress(
    goal_id='goal_001',
    amount=150.00
)

# Get all goals
goals = savings.get_student_goals(student_id='S-12345')
```

### Budget Alerts

The system generates alerts for financial events:

| Alert Type | Trigger |
|------------|---------|
| Overspending | Spending exceeds budget threshold |
| Goal milestone | Savings goal reaches percentage milestone |
| Meal plan pace | Meal plan usage pace changes significantly |
| Bill reminder | Upcoming payment due date |

---

## Portfolio / ePortfolio

### Creating a Portfolio

```python
from university_system.modules.domain.portfolio.services.portfolio_service import (
    PortfolioService
)

service = PortfolioService()

# Create a portfolio
service.create_portfolio(
    student_id='S-12345',
    title='John Doe - Computer Science Portfolio',
    bio='Senior CS student with interests in AI and distributed systems.',
    contact_email='john.doe@university.edu'
)

# Update portfolio
service.update_portfolio(
    portfolio_id='port_001',
    title='Updated Title',
    bio='Updated bio text...'
)

# Get full portfolio with all items
portfolio = service.get_portfolio(student_id='S-12345')
```

### Portfolio Items

Add projects, research, work experience, and more:

```python
service.add_portfolio_item(
    student_id='S-12345',
    category='Project',
    title='Distributed Chat Application',
    description='Built a real-time chat app using WebSockets and Redis.',
    date='2025-06-15',
    url='https://github.com/johndoe/chat-app',
    tags='python,websockets,redis,distributed-systems'
)
```

**Item Categories:**

| Category | Examples |
|----------|----------|
| Project | Software projects, design work, prototypes |
| Research | Papers, experiments, lab work |
| Leadership | Club president, event organizer, TA |
| Work Experience | Internships, co-ops, jobs |
| Award | Dean's List, competition wins |
| Certification | AWS Certified, Google Cloud, etc. |
| Publication | Journal articles, conference papers |
| Presentation | Conference talks, poster sessions |

```python
# Update an item
service.update_portfolio_item(
    item_id='item_001',
    title='Updated Project Title',
    description='Updated description...'
)

# Delete an item
service.delete_portfolio_item(item_id='item_001')
```

### Skills & Endorsements

Build a verified skills profile:

```python
# Add a skill
service.add_skill(
    student_id='S-12345',
    skill_name='Python',
    category='technical',         # technical, soft_skill, language, tool, domain
    proficiency='Advanced'        # Beginner, Intermediate, Advanced, Expert
)

# Get skills with endorsement counts
skills = service.get_student_skills(student_id='S-12345')

# Endorse a skill (faculty, peer, employer, mentor)
service.endorse_skill(
    skill_id='skill_001',
    endorser_id='F-001',
    endorser_type='faculty',
    comment='Excellent Python skills demonstrated in CS301.'
)

# View endorsements
endorsements = service.get_skill_endorsements(skill_id='skill_001')

# Update skill proficiency
service.update_skill(skill_id='skill_001', proficiency='Expert')

# Remove a skill
service.remove_skill(skill_id='skill_001')
```

**Skill Categories:**

| Category | Examples |
|----------|----------|
| Technical | Python, Java, SQL, Machine Learning |
| Soft Skill | Leadership, Communication, Teamwork |
| Language | English, Spanish, Mandarin |
| Tool | Git, Docker, Kubernetes, Figma |
| Domain | Data Science, Cybersecurity, Finance |

**Endorsement Types:**

| Endorser | Description |
|----------|-------------|
| Faculty | Professor or instructor endorsement |
| Peer | Fellow student endorsement |
| Employer | Workplace supervisor endorsement |
| Mentor | Academic or professional mentor |

### Badges & Achievements

#### Verified Badges

Badges represent verified accomplishments awarded by the system:

```python
# Award a badge
service.award_badge(
    student_id='S-12345',
    badge_type='Dean\'s List',
    title='Dean\'s List - Fall 2025',
    description='Achieved GPA of 3.8 or higher',
    issuer='Academic Affairs'
)

# Get student badges
badges = service.get_student_badges(student_id='S-12345')

# Verify a badge with verification code
is_valid = service.verify_badge(verification_code='BADGE-ABC123')
```

**Badge Types:**

| Badge | Criteria |
|-------|----------|
| Dean's List | GPA threshold achievement |
| Club Officer | Leadership position in student organization |
| Volunteer Hours | Community service milestone |
| Certification | External certification earned |
| Competition Winner | Academic or extracurricular competition |
| Scholarship | Scholarship recipient |
| Research Publication | Published research work |
| Leadership | Demonstrated leadership role |
| Academic Excellence | Outstanding academic performance |
| Community Service | Significant community contribution |
| Skill Mastery | Expert-level skill demonstration |
| Innovation | Innovative project or idea |

#### Achievements

Track accomplishments with points:

```python
service.add_achievement(
    student_id='S-12345',
    title='Hackathon Winner',
    description='First place at University Hackathon 2025',
    points=100,
    date='2025-10-15'
)

achievements = service.get_student_achievements(student_id='S-12345')
```

### Resume Generation

Build resumes directly from portfolio data:

```python
# Generate a resume from portfolio items
resume = service.generate_resume(
    student_id='S-12345',
    template='modern'  # traditional, modern, creative, technical, academic
)
```

**Resume Templates:**

| Template | Style |
|----------|-------|
| Traditional | Classic professional format |
| Modern | Contemporary clean design |
| Creative | Visually distinctive layout |
| Technical | Emphasis on technical skills and projects |
| Academic | Focus on research, publications, education |

**Output Formats:** PDF, DOCX, HTML

### Public Profile

Share your portfolio publicly:

```python
# Get public-facing portfolio
public = service.get_public_portfolio(student_id='S-12345')

# Portfolio stats and completeness scoring
stats = service.get_portfolio_stats(student_id='S-12345')
# Returns: completeness (0-100), items by category, badge count,
#          skill count, endorsement count, profile views, achievement points
```

**Privacy Controls:**

| Setting | Options |
|---------|---------|
| Visibility | Public, Private, Unlisted |
| Show contact | Yes/No |
| Show GPA | Yes/No |
| Show courses | Yes/No |
| Show projects | Yes/No |
| Show skills | Yes/No |
| Show endorsements | Yes/No |
| Custom sections | Configurable |
| Theme | Professional and other themes |

### Portfolio Database Schema

| Table | Purpose |
|-------|---------|
| `portfolios` | Main portfolio container |
| `portfolio_items` | Projects, research, work experience, etc. |
| `badges` | Verified achievement badges |
| `student_skills` | Skills with categories and proficiency |
| `skill_endorsements` | Endorsements from faculty, peers, employers |
| `achievements` | Tracked achievements with points |
| `public_profiles` | Public sharing and visibility settings |
| `resume_templates` | Available resume template definitions |
| `user_resumes` | Generated resume files (PDF, DOCX, HTML) |

---

## Configuration

### Database

Both services store data in the main `student_records.db` database. Tables are created on first initialization.

### Integration Points

| System | Usage |
|--------|-------|
| Authentication | User identity for portfolio ownership |
| Activity Logging | All budget and portfolio changes logged |
| Email | Notifications for budget alerts and endorsements |
| Database | Centralized data storage with connection pooling |

### Budget Alert Thresholds

Alerts can be configured as percentage-based or absolute amount thresholds. Default alert triggers:
- Budget 80% spent → warning
- Budget 100% spent → alert
- Savings goal 25%, 50%, 75% milestones → notification

## Troubleshooting

### Budget Calculations Incorrect

1. Verify all expenses have the correct dates and amounts
2. Check the budget period (start_date to end_date)
3. Ensure currency amounts are consistent (no mixing currencies)
4. Review deleted or updated expenses that may affect totals

### Meal Plan Pace Inaccurate

1. Verify the plan start and end dates are correct
2. Ensure all meal transactions are logged
3. Check that the total meals count matches your actual plan
4. Pace is calculated based on elapsed time vs. total duration

### Portfolio Items Not Showing

1. Verify the item was saved successfully (check return value)
2. Ensure the student_id matches the portfolio owner
3. Check the item category is valid
4. Review portfolio visibility settings

### Badge Verification Fails

1. Ensure the verification code is entered exactly as issued
2. Check if the badge has been revoked
3. Contact the issuing department for reissuance

### Resume Generation Errors

1. Ensure the portfolio has sufficient items to populate the template
2. Check that the requested template exists
3. Verify write permissions on the output directory
4. For PDF output, ensure required libraries are installed
