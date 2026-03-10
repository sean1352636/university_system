# Student Marketplace Module

A comprehensive e-commerce platform for students to buy, sell, and exchange items within the university community.

## Overview

The Student Marketplace module facilitates peer-to-peer transactions among students, providing a safe and organized platform for:

- **Textbook Trading**: Buy/sell used textbooks with course-specific listings and ISBN tracking
- **Furniture Exchange**: Find affordable furniture for dorms and apartments
- **Electronics Marketplace**: Trade laptops, tablets, calculators, and other electronics
- **Housing Subletting**: Post and find subletting opportunities with lease details
- **Free Stuff Board**: Give away items you no longer need
- **Services Exchange**: Offer or find tutoring, moving help, and other services

## Features

### Core Functionality

#### Listing Management
- Create detailed listings with multiple photos
- Category-specific fields (ISBN for textbooks, lease dates for housing)
- Listing status tracking (Active, Sold, Reserved, Expired)
- View counter for tracking interest
- Edit and delete capabilities for listing owners

#### Search & Discovery
- Full-text search across titles and descriptions
- Category-based browsing with dedicated tabs
- Price range filtering
- Condition filtering (New, Like New, Good, Fair, Poor)
- Recent listings and trending items

#### Communication
- Built-in messaging system for buyer-seller communication
- Message history and conversation threads
- Read/unread status tracking
- Email notifications for new messages (configurable)

#### Safety & Trust
- Seller rating and review system (1-5 stars)
- Transaction history tracking
- Report listing functionality for inappropriate content
- Safe meeting guidelines and tips
- Admin moderation tools

#### User Features
- Favorites/watchlist for tracking interesting items
- My Listings dashboard with status overview
- Transaction history and completed sales
- Seller profile with aggregate ratings
- Message inbox with unread indicators

## Architecture

### Service Layer (`services/marketplace_service.py`)

The `MarketplaceService` class provides all business logic and database operations:

```python
from university_system.modules.domain.marketplace.services.marketplace_service import MarketplaceService

service = MarketplaceService()

# Create a listing
listing_id = service.create_listing(
    seller_id='user123',
    title='Calculus Textbook',
    description='Excellent condition, minimal highlighting',
    price=45.00,
    category='Textbooks',
    condition_status='Good',
    metadata={'course_code': 'MATH 101', 'isbn': '978-0-321-75891-9'}
)

# Search listings
results = service.search_listings(
    search_term='calculus',
    category='Textbooks',
    max_price=50.00
)

# Send message to seller
message_id = service.send_message(
    listing_id=listing_id,
    sender_id='buyer123',
    message_text='Is this still available?'
)
```

### Database Schema

#### marketplace_listings
Primary table for all listings:
```sql
- listing_id (INTEGER PRIMARY KEY)
- seller_id (TEXT)
- listing_type (TEXT) - 'For Sale' or 'Free'
- title (TEXT)
- description (TEXT)
- category (TEXT)
- price (REAL)
- condition_status (TEXT)
- location (TEXT)
- status (TEXT) - Active, Sold, Reserved, Expired, Removed
- view_count (INTEGER)
- created_at (TEXT)
- updated_at (TEXT)
- expires_at (TEXT)
```

#### marketplace_photos
Stores listing photos:
```sql
- photo_id (INTEGER PRIMARY KEY)
- listing_id (INTEGER FK)
- photo_path (TEXT)
- is_primary (BOOLEAN)
- uploaded_at (TEXT)
```

#### marketplace_transactions
Tracks completed transactions:
```sql
- transaction_id (INTEGER PRIMARY KEY)
- listing_id (INTEGER FK)
- buyer_id (TEXT)
- seller_id (TEXT)
- transaction_price (REAL)
- transaction_date (TEXT)
- status (TEXT)
- notes (TEXT)
```

#### marketplace_reviews
User reviews and ratings:
```sql
- review_id (INTEGER PRIMARY KEY)
- transaction_id (INTEGER FK)
- reviewer_id (TEXT)
- reviewed_user_id (TEXT)
- rating (INTEGER) - 1-5
- review_text (TEXT)
- created_at (TEXT)
```

#### marketplace_favorites
User watchlists:
```sql
- favorite_id (INTEGER PRIMARY KEY)
- user_id (TEXT)
- listing_id (INTEGER FK)
- added_at (TEXT)
```

#### marketplace_reports
Content moderation:
```sql
- report_id (INTEGER PRIMARY KEY)
- listing_id (INTEGER FK)
- reporter_id (TEXT)
- reason (TEXT)
- description (TEXT)
- status (TEXT)
- reported_at (TEXT)
```

#### marketplace_messages
Buyer-seller communication:
```sql
- message_id (INTEGER PRIMARY KEY)
- listing_id (INTEGER FK)
- sender_id (TEXT)
- receiver_id (TEXT)
- message_text (TEXT)
- sent_at (TEXT)
- is_read (BOOLEAN)
```

## CLI Interface

### Running the CLI

```bash
python -m university_system.modules.domain.marketplace.cli.marketplace_cli
```

Or from within the application:
```python
from university_system.modules.domain.marketplace.cli import MarketplaceCLI

cli = MarketplaceCLI(user_id='user123')
cli.run()
```

### CLI Menu Structure

```
STUDENT MARKETPLACE
======================================================================
1. Browse All Listings          - View all active listings
2. Browse by Category           - Filter by category
3. Search Marketplace           - Full-text search with filters
4. Create New Listing           - Post an item for sale
5. My Listings                  - Manage your listings
6. My Favorites                 - View saved items
7. My Messages                  - Check buyer/seller messages
8. View Listing Details         - Detailed view of any listing
9. My Reviews                   - See your seller rating
10. Marketplace Statistics      - View platform statistics
0. Back to Main Menu
======================================================================
```

### CLI Features

- **Intuitive Navigation**: Number-based menu system
- **Detailed Listings**: View all listing information including seller details
- **Interactive Search**: Search with filters (category, price range, keywords)
- **Listing Management**: Create, edit, mark as sold, or delete your listings
- **Messaging**: Send and receive messages within the CLI
- **Status Tracking**: View unread message counts and listing views

## GUI Interface

### Running the GUI

```bash
python -m university_system.modules.domain.marketplace.gui.marketplace_gui
```

Or from within the application:
```python
import tkinter as tk
from university_system.modules.domain.marketplace.gui import MarketplaceGUI

root = tk.Tk()
app = MarketplaceGUI(root)
root.mainloop()
```

### GUI Layout

#### Tab Structure
1. **All Listings** - Browse all active items with search/filter panel
2. **Textbooks** - Course-specific textbook listings
3. **Furniture** - Furniture and home goods
4. **Electronics** - Tech items and gadgets
5. **Housing** - Subletting and roommate opportunities
6. **Free** - Free items being given away
7. **Services** - Student services (tutoring, moving help, etc.)
8. **Other** - Miscellaneous items
9. **My Listings** - Personal listing management dashboard
10. **Favorites** - Saved items and watchlist

#### Key Components

**Search & Filter Panel**
- Text search box
- Category dropdown
- Price range filters (min/max)
- Condition filter
- Search and Clear buttons

**Listing Grid/Table View**
- Sortable columns (Title, Price, Category, Condition, Date)
- Thumbnail images (when available)
- Status indicators
- View counter
- Quick action buttons

**Listing Details View**
- Full-size image gallery
- Complete description
- Seller information and rating
- Contact seller button
- Add to favorites button
- Report listing option
- Share functionality

**Create Listing Dialog**
- Multi-step form with validation
- Photo upload (multiple images)
- Category-specific fields
- Price and condition selectors
- Location input
- Preview before posting

**My Listings Dashboard**
- Status filter (Active/Sold/All)
- Quick edit functionality
- Mark as sold button
- View messages per listing
- Performance metrics (views, favorites, messages)

**Messaging Panel**
- Conversation list with unread indicators
- Message threads grouped by listing
- Send/receive messages
- Message timestamps
- Read receipts

### GUI Features

- **Responsive Design**: Adapts to different screen sizes
- **Real-time Updates**: Auto-refresh for new messages and listings
- **Drag & Drop**: Photo uploads via drag and drop
- **Keyboard Shortcuts**: Common operations (Ctrl+N for new listing, etc.)
- **Tooltips**: Helpful hints throughout the interface
- **Error Handling**: User-friendly error messages with suggestions

## Usage Examples

### Example 1: Creating a Textbook Listing

```python
from university_system.modules.domain.marketplace.services.marketplace_service import MarketplaceService

service = MarketplaceService()

# Create textbook listing
listing_id = service.create_listing(
    seller_id='student123',
    listing_type='For Sale',
    title='Introduction to Algorithms (3rd Edition)',
    description='Used for CS 301. Great condition, no highlighting or writing. '
                'Includes solutions manual.',
    category='Textbooks',
    price=75.00,
    condition_status='Like New',
    location='Engineering Building',
    metadata={
        'course_code': 'CS 301',
        'isbn': '978-0-262-03384-8',
        'edition': '3rd',
        'author': 'Cormen, Leiserson, Rivest, Stein'
    }
)

print(f"Listing created with ID: {listing_id}")
```

### Example 2: Searching for Housing

```python
# Search for subletting opportunities
listings = service.search_listings(
    category='Housing',
    min_price=400,
    max_price=800,
    search_term='summer sublet'
)

for listing in listings:
    print(f"{listing['title']} - ${listing['price']}/month")
    metadata = listing.get('metadata', {})
    if metadata:
        print(f"  Available: {metadata.get('lease_start_date')} to {metadata.get('lease_end_date')}")
```

### Example 3: Messaging a Seller

```python
# Send inquiry about a listing
message_id = service.send_message(
    listing_id=42,
    sender_id='buyer123',
    message_text='Hi! Is this textbook still available? Can we meet tomorrow?'
)

# Get conversation history
messages = service.get_conversation_messages(
    listing_id=42,
    user_id='buyer123'
)

for msg in messages:
    sender = "You" if msg['sender_id'] == 'buyer123' else "Seller"
    print(f"{sender}: {msg['message_text']}")
```

### Example 4: Leaving a Review

```python
# After completing a transaction, leave a review
review_id = service.add_review(
    transaction_id=15,
    reviewer_id='buyer123',
    reviewed_user_id='seller456',
    rating=5,
    review_text='Great seller! Item exactly as described, met promptly.'
)

# Check seller's overall rating
avg_rating, count, reviews = service.get_user_reviews('seller456')
print(f"Seller Rating: {avg_rating:.1f}/5.0 ({count} reviews)")
```

## Categories

### Textbooks
- Course-specific fields: course_code, ISBN, edition, author
- Common conditions: New, Like New, Good, Acceptable
- Typical price range: $20-$200
- Search tips: Include course code in title

### Furniture
- Common items: Desks, chairs, beds, couches, storage
- Delivery/pickup required: Specify location clearly
- Condition critical: Photos highly recommended
- Typical price range: Free-$500

### Electronics
- Items: Laptops, tablets, calculators, monitors, printers
- Include specs in description
- Original packaging/receipts add value
- Warranty information if applicable

### Housing
- Subletting opportunities
- Required fields: Lease dates, rent, location
- Include utilities, internet, parking details
- Photos of space are essential

### Free
- Items being given away
- No price field (automatically $0)
- First come, first served typically
- Great for moving, graduating, downsizing

### Services
- Tutoring, moving help, cleaning, etc.
- Hourly or flat rate pricing
- Include qualifications/experience
- Student-to-student services

### Other
- Catch-all category
- Sports equipment, musical instruments, etc.
- Still benefits from good photos and descriptions

## Safety Guidelines

### For Buyers
✓ Meet in public, well-lit areas
✓ Inspect items before paying
✓ Use cash or secure payment methods
✓ Bring a friend if meeting for high-value items
✓ Trust your instincts - if something feels off, walk away
✗ Don't share personal information unnecessarily
✗ Don't pay before seeing the item
✗ Don't meet in private residences (first meeting)

### For Sellers
✓ Meet in public locations
✓ Be honest about condition
✓ Have exact change if accepting cash
✓ Take photos of serial numbers for electronics
✓ Get contact information from buyers
✗ Don't leave items unattended during viewings
✗ Don't accept checks or money orders
✗ Don't give out your address until meeting is confirmed

### Reporting Issues
Use the "Report Listing" feature for:
- Fraudulent or scam listings
- Prohibited items (weapons, drugs, etc.)
- Inappropriate content
- Misleading descriptions
- Harassment or abuse

Reports are reviewed by administrators within 24 hours.

## API Reference

### MarketplaceService Methods

#### Listing Management
- `create_listing(**kwargs)` - Create a new listing
- `get_listing(listing_id, increment_views=False)` - Get listing details
- `update_listing(listing_id, user_id, **updates)` - Update listing
- `delete_listing(listing_id, user_id)` - Delete (soft delete) listing
- `mark_listing_sold(listing_id, user_id, buyer_id=None)` - Mark as sold

#### Search & Browse
- `get_listings(category=None, status='Active', limit=50)` - Get listings
- `search_listings(search_term=None, category=None, ...)` - Search with filters
- `get_user_listings(user_id, status=None)` - Get user's listings
- `get_categories()` - Get all available categories

#### Messaging
- `send_message(listing_id, sender_id, message_text)` - Send message
- `get_user_messages(user_id)` - Get all user messages
- `get_conversation_messages(listing_id, user_id)` - Get conversation
- `mark_messages_read(listing_id, user_id)` - Mark as read

#### Favorites
- `add_favorite(user_id, listing_id)` - Add to favorites
- `remove_favorite(user_id, listing_id)` - Remove from favorites
- `get_user_favorites(user_id)` - Get favorites list

#### Reviews
- `add_review(transaction_id, reviewer_id, reviewed_user_id, rating, review_text)` - Leave review
- `get_user_reviews(user_id)` - Get reviews for a user

#### Reporting
- `report_listing(listing_id, reporter_id, reason, description)` - Report listing

#### Statistics
- `get_statistics()` - Get marketplace statistics

## Configuration

### Environment Variables
```bash
# Photo upload settings
MARKETPLACE_UPLOAD_DIR=/path/to/uploads
MAX_PHOTO_SIZE_MB=5
MAX_PHOTOS_PER_LISTING=10

# Listing expiration
LISTING_EXPIRY_DAYS=90

# Messaging
ENABLE_EMAIL_NOTIFICATIONS=true
MESSAGE_NOTIFICATION_DELAY_MINUTES=5
```

### Database Configuration
The marketplace uses the university system's centralized SQLite database. Tables are created automatically on first use.

## Testing

### Running Tests
```bash
python -m university_system.modules.domain.marketplace.test_marketplace
```

### Test Coverage
- Service layer operations (CRUD, search, messaging)
- Database schema validation
- CLI interface structure
- GUI interface structure
- Edge cases and error handling

## Troubleshooting

### Common Issues

**Issue**: "Login Required" messages
**Solution**: Ensure you're logged in with valid credentials before accessing marketplace features.

**Issue**: Listings not appearing in search
**Solution**: Check listing status (must be "Active"), verify category is correct, clear any restrictive filters.

**Issue**: Cannot upload photos
**Solution**: Verify upload directory exists and has write permissions. Check file size limits.

**Issue**: Messages not being delivered
**Solution**: Verify recipient user ID exists. Check database write permissions.

**Issue**: Reviews not appearing
**Solution**: Ensure transaction exists and review hasn't already been submitted for that transaction.

## Future Enhancements

### Planned Features
- [ ] Photo compression and thumbnail generation
- [ ] Email notifications for new messages
- [ ] Price history and analytics
- [ ] Bulk upload for multiple items
- [ ] Integration with payment processing
- [ ] Mobile app support
- [ ] Social media sharing
- [ ] Advanced search filters (distance, pickup vs. delivery)
- [ ] Seller verification badges
- [ ] Featured listings (promoted posts)

### Integration Opportunities
- **Finance Module**: Payment processing integration
- **Student Affairs**: Campus event integration (book buyback events)
- **Housing Module**: Sync subletting with official housing
- **Authentication**: Enhanced seller verification

## Contributing

When contributing to the marketplace module:

1. Follow the existing code structure
2. Add tests for new features
3. Update this README with new functionality
4. Ensure backward compatibility
5. Follow the university system's coding standards

## License

Part of the University Management System. See main project LICENSE file.

## Support

For issues, questions, or feature requests:
- File an issue in the project repository
- Contact the development team
- Check the main documentation at `/docs`

---

**Version**: 1.0.0
**Last Updated**: January 2026
**Maintainer**: University System Development Team

# Achievement & Portfolio System

Professional digital portfolio management system for students to showcase their academic achievements, projects, skills, and experiences.

## Overview

The Achievement & Portfolio System enables students to:
- Build comprehensive digital portfolios
- Earn and display verified badges
- Manage skills with peer/faculty endorsements
- Generate professional resumes
- Share public profiles for internship applications
- Track achievement points and completeness

## Architecture

```
portfolio/
├── services/
│   └── portfolio_service.py      (1,319 lines) - Core business logic
├── cli/
│   └── portfolio_cli.py          (836 lines) - Command-line interface
├── gui/
│   └── portfolio_gui.py          (1,045 lines) - Tkinter GUI
└── __init__.py
```

**Total:** 3,200 lines of professional, production-ready code

## Features

### 1. Digital Portfolio Management
- **Portfolio Creation**: Title, bio, headline, profile image
- **Portfolio Items**: Projects, research, leadership, work experience, awards, certifications, publications, presentations
- **Item Details**: Organization, role, dates, technologies, achievements, URLs, attachments
- **Featured Items**: Highlight your best work
- **Social Links**: LinkedIn, GitHub, personal website integration

### 2. Verified Badge System
- **Badge Types**:
  - Dean's List
  - Club Officer
  - Volunteer Hours
  - Certifications
  - Competition Winner
  - Scholarship
  - Research Publication
  - Leadership
  - Academic Excellence
  - Community Service
  - Skill Mastery
  - Innovation
- **Verification**: Unique verification codes for badge authenticity
- **Metadata**: Issuer, issue date, expiry date, description
- **Status Tracking**: Pending, verified, expired, revoked

### 3. Skills Management
- **Skill Categories**:
  - Technical skills
  - Soft skills
  - Languages
  - Tools
  - Domain expertise
- **Proficiency Levels**: Beginner, Intermediate, Advanced, Expert
- **Years of Experience**: Track skill development over time
- **Featured Skills**: Highlight your strongest abilities

### 4. Endorsement System
- **Endorser Roles**:
  - Faculty endorsements
  - Peer endorsements
  - Employer endorsements
  - Mentor endorsements
- **Comments**: Written feedback on skills
- **Relationship**: Context for the endorsement
- **Endorsement Counts**: Display credibility metrics

### 5. Resume Builder
- **Template Types**:
  - Traditional
  - Modern
  - Creative
  - Technical
  - Academic
- **Auto-Generation**: Pull from portfolio data
- **Customizable Sections**:
  - Education
  - Experience
  - Projects
  - Skills
  - Achievements
  - Certifications
- **Export Formats**: PDF, DOCX, HTML (planned)

### 6. Public Profile System
- **Visibility Options**:
  - Public: Searchable and accessible
  - Unlisted: Accessible via link only
  - Private: Not accessible
- **Privacy Controls**:
  - Show/hide contact information
  - Show/hide GPA
  - Show/hide courses
  - Show/hide projects
  - Show/hide skills
  - Show/hide endorsements
- **Custom Sections**: Add personalized content
- **Themes**: Professional, modern, creative themes
- **View Tracking**: Monitor profile views

### 7. Statistics & Analytics
- **Completeness Score**: 0-100% portfolio completion metric
- **Item Counts**: By category breakdown
- **Endorsement Analytics**: Faculty vs. peer counts
- **Achievement Points**: Gamification scoring
- **Profile Views**: Track visibility
- **Badge Verification**: Authentication tracking

## Database Schema

### Tables Created

1. **portfolios**: Core portfolio information
2. **portfolio_items**: Projects, research, leadership, etc.
3. **badges**: Verified achievements and certifications
4. **student_skills**: Skills with proficiency levels
5. **skill_endorsements**: Peer/faculty skill validations
6. **achievements**: General achievements and milestones
7. **public_profiles**: Public profile settings and privacy
8. **resume_templates**: Resume template definitions
9. **user_resumes**: Generated resumes

### Indexes
- Performance-optimized queries
- Foreign key relationships
- Unique constraints for data integrity

## Service Layer API

### PortfolioService

```python
from university_system.modules.domain.portfolio import PortfolioService

service = PortfolioService()

# Portfolio Management
success, message, portfolio_id = service.create_portfolio(
    student_id="S001",
    title="My Portfolio",
    headline="CS Student",
    bio="Passionate developer"
)

# Add Portfolio Item
success, message, item_id = service.add_portfolio_item(
    portfolio_id=1,
    category='project',
    title="ML Classifier",
    description="Built CNN image classifier",
    technologies="Python, TensorFlow"
)

# Award Badge
success, message, badge_id = service.award_badge(
    student_id="S001",
    badge_type='deans_list',
    badge_name="Dean's List Fall 2024",
    issuer="College of CS"
)

# Add Skill
success, message, skill_id = service.add_skill(
    student_id="S001",
    skill_name="Python",
    skill_category='technical',
    proficiency_level='expert',
    years_experience=3.0
)

# Endorse Skill
success, message, endorsement_id = service.endorse_skill(
    skill_id=1,
    endorser_id="PROF001",
    endorser_role='faculty',
    comment="Excellent Python skills"
)

# Generate Resume
success, message, resume = service.generate_resume(
    student_id="S001",
    resume_name="Tech Resume",
    template_type='technical'
)

# Update Public Profile
success, message = service.update_public_profile(
    student_id="S001",
    visibility='public',
    show_projects=True,
    show_skills=True
)

# Get Statistics
stats = service.get_portfolio_stats("S001")
# Returns: completeness_score, total_items, total_skills, etc.

# Get Portfolio URL
url = service.get_portfolio_url("S001")
```

## CLI Interface

### Usage

```bash
# From university system
python -m university_system.modules.domain.portfolio.cli.portfolio_cli

# Or directly
python university_system/modules/domain/portfolio/cli/portfolio_cli.py
```

### Menu Structure

```
ACHIEVEMENT & PORTFOLIO SYSTEM
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Portfolio Completeness: 85%
Total Items: 12
Skills: 15
Endorsements: 8
Verified Badges: 3

1. Portfolio Management
2. Add Portfolio Item
3. View My Portfolio
4. Manage Skills
5. View My Badges
6. View Endorsements
7. Request Endorsement
8. Resume Builder
9. Public Profile Settings
10. Share Portfolio
11. Portfolio Statistics
```

### Features
- Interactive menu-driven interface
- Create/edit portfolio with guided prompts
- Add items by category with validation
- Skills management with proficiency tracking
- Badge showcase with verification codes
- Endorsement viewing and requesting
- Resume generation wizard
- Privacy settings configuration
- Portfolio URL sharing

## GUI Interface

### Usage

```python
from university_system.modules.domain.portfolio import PortfolioGUI

# Standalone
app = PortfolioGUI()
app.run()

# Or as part of main system
from university_system.modules.domain.portfolio.gui.portfolio_gui import PortfolioGUI
gui = PortfolioGUI(parent_window)
```

### Interface Components

#### Tabs
1. **Overview**: Dashboard with statistics and completeness score
2. **Portfolio Items**: Manage projects, research, leadership, work experience
3. **Skills**: Skills matrix with endorsement counts
4. **Badges**: Badge showcase with verification
5. **Endorsements**: Endorsement management and viewing
6. **Resumes**: Resume builder and preview
7. **Settings**: Public profile configuration and privacy

#### Features
- **Drag-and-drop** portfolio item reordering (planned)
- **Tree views** for organized data display
- **Search and filter** by category
- **Double-click** to view details
- **Context menus** for quick actions
- **Progress indicators** for completeness
- **Real-time statistics** in header
- **Professional styling** with ttk widgets

### Screenshots Equivalent

```
┌─────────────────────────────────────────────────────────────┐
│ Portfolio Dashboard                                          │
├─────────────────────────────────────────────────────────────┤
│ Student: John Doe                                            │
│ Completeness: 85%  Items: 12  Skills: 15  Badges: 3  Views: 42│
├─────────────────────────────────────────────────────────────┤
│ [Overview] [Portfolio] [Skills] [Badges] [Endorsements]     │
│ [Resumes] [Settings]                                         │
│                                                              │
│  Portfolio Statistics                                        │
│  ┌────────────────────────────────────────────────────┐    │
│  │ Completeness Score: 85%                            │    │
│  │                                                     │    │
│  │ Items by Category:                                 │    │
│  │   Projects: 5                                      │    │
│  │   Research: 2                                      │    │
│  │   Leadership: 3                                    │    │
│  │   Work Experience: 2                               │    │
│  │                                                     │    │
│  │ Skills: 15                                         │    │
│  │ Endorsements: 8 (Faculty: 3, Peer: 5)            │    │
│  │ Verified Badges: 3                                 │    │
│  │                                                     │    │
│  │ Profile Views: 42                                  │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
│  [Refresh Stats]  [Share Portfolio]                         │
└─────────────────────────────────────────────────────────────┘
```

## Integration Points

### Career Services Integration
- Export portfolio data for career counseling
- Resume templates aligned with industry standards
- Public URLs for job applications
- Skills mapping to job requirements

### LinkedIn Integration (Planned)
- Export skills to LinkedIn profile
- Import work experience
- Share endorsements
- Sync profile updates

### External Verification
- Badge verification API endpoints
- QR codes for quick verification
- Blockchain integration (future)
- Third-party credential validation

## Privacy & Security

### Data Protection
- Student-controlled visibility settings
- Granular privacy controls per section
- Secure public URL generation
- View tracking with analytics

### Verification
- Cryptographic verification codes
- Issuer authentication
- Expiry date tracking
- Revocation support

### Access Control
- Role-based permissions
- Student-only portfolio editing
- Faculty badge issuance
- Admin oversight capabilities

## Best Practices

### For Students
1. **Keep it Updated**: Regularly add new achievements
2. **Feature Your Best**: Highlight top 3-5 items
3. **Seek Endorsements**: Request validation from faculty/peers
4. **Complete Your Profile**: Aim for 80%+ completeness
5. **Professional Bio**: Write clear, concise summary
6. **Use Keywords**: Include industry-relevant skills
7. **Privacy First**: Review settings before sharing

### For Faculty
1. **Timely Endorsements**: Respond to student requests promptly
2. **Specific Feedback**: Provide detailed endorsement comments
3. **Verify Achievements**: Award badges for verified accomplishments
4. **Encourage Participation**: Promote portfolio building

### For Administrators
1. **Badge Standards**: Establish clear criteria
2. **Template Quality**: Provide professional resume templates
3. **Privacy Compliance**: Ensure FERPA/GDPR compliance
4. **Training Resources**: Offer portfolio building workshops

## Performance Considerations

### Database Optimization
- Indexed foreign keys for fast lookups
- Efficient JOIN queries for endorsement counts
- Cached statistics for dashboard
- Pagination for large portfolios

### Scalability
- Connection pooling for concurrent access
- Lazy loading for portfolio items
- Asynchronous operations for exports
- CDN integration for profile images (planned)

## Future Enhancements

### Planned Features
- [ ] Video portfolio items
- [ ] Interactive project demos
- [ ] AI-powered resume optimization
- [ ] Portfolio analytics dashboard
- [ ] Mobile app integration
- [ ] Social media sharing
- [ ] Portfolio comparison tools
- [ ] Skill gap analysis
- [ ] Recommendation engine
- [ ] Blockchain credentials

### Advanced Features
- [ ] Portfolio templates by major
- [ ] Industry-specific resume formats
- [ ] Portfolio peer review system
- [ ] Achievement leaderboards
- [ ] Portfolio export to PDF
- [ ] Integration with job boards
- [ ] AI cover letter generation
- [ ] Interview preparation tools

## Testing

### Test Coverage
- Unit tests for service methods
- Integration tests for workflows
- GUI component testing
- Database integrity tests
- Performance benchmarks

### Test Script
```bash
# Run comprehensive tests
python test_portfolio_system.py

# Expected Output:
# - Portfolio creation
# - Item additions (projects, research, leadership)
# - Badge awards (Dean's List, certifications)
# - Skills with endorsements
# - Resume generation
# - Statistics calculation
```

## Documentation

### Code Documentation
- Docstrings for all public methods
- Type hints for parameters
- Example usage in docstrings
- Inline comments for complex logic

### User Documentation
- Student user guide
- Faculty badge issuance guide
- Administrator setup guide
- API reference documentation

## Support & Maintenance

### Error Handling
- Graceful degradation
- User-friendly error messages
- Detailed logging for debugging
- Transaction rollback on failures

### Activity Logging
- All CRUD operations logged
- User attribution
- Timestamp tracking
- Audit trail for compliance

## License & Credits

Part of the University Management System v5.0.0

### Technologies
- Python 3.8+
- SQLite with WAL mode
- Tkinter for GUI
- JSON for data serialization

### Dependencies
- university_system.infrastructure.database
- university_system.infrastructure.auth
- university_system.modules.shared.utils

## Contact & Support

For issues, feature requests, or questions about the Portfolio System:
- Submit issues via the main repository
- Consult the system administrator
- Review the comprehensive documentation

---

**Built for professional career development and student success.**

# Smart Notifications Hub

A comprehensive notification management system for the university platform that provides unified notification delivery across all university systems.

## Overview

The Smart Notifications Hub centralizes all notifications from academic, social, financial, health, housing, and events systems. It provides intelligent notification management with customizable preferences, priority levels, quiet hours, and delivery methods.

## Features

### Core Features
- **Multi-Channel Notifications**: Academic, Social, Financial, Health, Housing, Events, System
- **Priority Levels**: Low, Medium, High, Urgent (with color coding)
- **Delivery Methods**: Push, Email, SMS
- **Smart Bundling**: Automatically groups related notifications
- **Quiet Hours**: Customizable do-not-disturb periods
- **Daily Digest**: Optional summary instead of real-time alerts
- **Notification History**: Complete audit trail with search

### User Preferences
- Channel-specific enable/disable
- Minimum priority thresholds per channel
- Delivery method selection per channel
- Configurable quiet hours (with midnight-spanning support)
- Daily digest scheduling
- Notification bundling settings
- Time-based automatic cleanup

## Architecture

```
notifications/
├── services/
│   └── notifications_service.py    # Core business logic
├── cli/
│   └── notifications_cli.py         # Command-line interface
├── gui/
│   └── __init__.py                  # Backward compatibility wrapper (redirects to Email Manager)
└── __init__.py

Note: The GUI has been integrated into the Email Manager at:
modules/shared/gui/email/email_gui/notifications_tab.py
```

## Database Schema

### Tables

#### `notifications`
Core notification records with channel, priority, and content.
- `notification_id`: Primary key
- `user_id`: Target user
- `channel`: Notification category
- `priority`: Urgency level
- `title`: Brief headline
- `message`: Full content
- `source_system`: Originating system
- `source_id`: Source record reference
- `is_read`: Read status
- `is_archived`: Archive status
- `created_at`, `read_at`, `expires_at`: Timestamps
- `metadata`: JSON additional data

#### `notification_preferences`
User-level global settings.
- `quiet_hours_start`, `quiet_hours_end`: DND period
- `daily_digest_enabled`: Digest mode flag
- `daily_digest_time`: Digest delivery time
- `bundle_notifications`: Auto-bundling flag
- `bundle_time_window`: Bundling time threshold (seconds)

#### `notification_channels`
Channel-specific user preferences.
- `user_id`, `channel`: Composite key
- `enabled`: Channel enabled flag
- `min_priority`: Minimum priority filter
- `push_enabled`, `email_enabled`, `sms_enabled`: Delivery methods

#### `notification_history`
Delivery tracking and audit log.
- Links to notifications
- Tracks delivery method and status
- Records errors and timestamps

#### `digests`
Daily digest compilation records.
- One per user per day
- Tracks notification count and send time

#### `bundled_notifications`
Smart notification grouping.
- Groups related notifications by channel
- Time-based bundling within configurable window
- Automatic bundle creation and expiration

## Usage

### Service Layer

```python
from university_system.modules.domain.notifications import NotificationsService

service = NotificationsService()

# Create a notification
notification_id = service.create_notification(
    user_id='S12345',
    channel='academic',
    priority='high',
    title='Assignment Due Soon',
    message='Your CS101 assignment is due in 24 hours',
    source_system='Assignment System',
    source_id='assignment_123'
)

# Get unread notifications
notifications = service.get_notifications(
    user_id='S12345',
    unread_only=True
)

# Mark as read
service.mark_as_read(notification_id, user_id='S12345')

# Update preferences
service.update_preferences(
    user_id='S12345',
    quiet_hours_start='22:00',
    quiet_hours_end='08:00',
    daily_digest_enabled=True,
    daily_digest_time='08:00'
)

# Configure channel
service.update_channel_settings(
    user_id='S12345',
    channel='social',
    enabled=True,
    min_priority='medium',
    push_enabled=True,
    email_enabled=False
)
```

### CLI Interface

```python
from university_system.modules.domain.notifications.cli import NotificationsCLI

cli = NotificationsCLI()
cli.main_menu()
```

**CLI Features:**
- View notifications (all, unread, by channel, by priority)
- Mark notifications as read (individual or bulk)
- Archive notifications
- Configure preferences and quiet hours
- Manage channel settings
- Set up daily digest
- Clear old notifications
- View statistics
- Create test notifications

### GUI Interface

**NEW:** The Notifications GUI has been integrated into the Email Manager for a unified communication experience.

Access notifications through the Email Manager:

```python
from university_system.modules.shared.gui.email.email_gui.email_manager_main import EmailManagerGUI

# Create email manager
email_gui = EmailManagerGUI(root, auth)

# Access notifications tab
email_gui.show_notifications_tab()
```

**Backward Compatibility:** For legacy code, importing NotificationsGUI will automatically redirect to the Email Manager:

```python
from university_system.modules.domain.notifications.gui import NotificationsGUI

# This now opens the Email Manager with notifications tab focused
app = NotificationsGUI()
app.run()
```

**GUI Features:**
- Modern notification center with inbox-style list
- Unread badge count
- Channel filter tabs (Academic, Social, Financial, Health, Housing, Events)
- Priority color coding (Red=Urgent, Orange=High, Yellow=Medium, Blue=Low)
- Interactive preferences panel
- Quiet hours time picker
- Daily digest configuration
- Notification bundling settings
- Channel-specific preferences
- Notification history with search and filters
- Mark as read/archive functionality
- Statistics dashboard
- One-click "Mark All as Read"
- Real-time updates

## Notification Channels

| Channel | Description | Common Uses |
|---------|-------------|-------------|
| **Academic** | Course, assignment, grade notifications | Assignment due, grade posted, exam scheduled |
| **Social** | Student life and community | Club events, social activities, friend requests |
| **Financial** | Billing and payments | Payment due, receipt issued, scholarship awarded |
| **Health** | Campus health services | Appointment reminder, health alert, prescription ready |
| **Housing** | Residential life | Maintenance request, package arrival, room inspection |
| **Events** | Campus events | Event registration, event reminder, event cancelled |
| **System** | Platform notifications | System maintenance, account updates, security alerts |

## Priority Levels

| Priority | Color | Description | Delivery |
|----------|-------|-------------|----------|
| **Urgent** | 🔴 Red | Immediate attention required | All methods, overrides quiet hours |
| **High** | 🟠 Orange | Important but not critical | All enabled methods |
| **Medium** | 🟡 Yellow | Standard notifications | Respects quiet hours |
| **Low** | 🔵 Blue | Informational only | May be bundled or delayed |

## Smart Features

### Quiet Hours
Configure periods when only urgent notifications are delivered. Supports midnight-spanning periods (e.g., 22:00-08:00).

### Daily Digest
Consolidates all notifications into a single daily summary, reducing notification fatigue. Configure delivery time to match your schedule.

### Smart Bundling
Automatically groups related notifications within a configurable time window (default: 5 minutes). Example: Multiple grade postings become "3 new grades posted" instead of 3 separate notifications.

### Notification Expiration
Optionally set expiration dates for time-sensitive notifications. Expired notifications are automatically cleaned up.

### Delivery Tracking
Complete audit trail of when and how notifications were delivered, with error tracking for troubleshooting.

## API Reference

### NotificationsService

#### Notification Management
- `create_notification(...)`: Create new notification
- `get_notifications(...)`: Retrieve notifications with filtering
- `mark_as_read(...)`: Mark notification as read
- `mark_all_as_read(...)`: Bulk mark as read
- `archive_notification(...)`: Archive notification
- `delete_old_notifications(...)`: Clean up old notifications
- `get_unread_count(...)`: Get unread count

#### Preferences Management
- `get_preferences(...)`: Get user preferences
- `update_preferences(...)`: Update global preferences
- `get_channel_settings(...)`: Get all channel settings
- `update_channel_settings(...)`: Update channel-specific settings

#### Analytics
- `get_notification_stats(...)`: Get comprehensive statistics
- `generate_daily_digest(...)`: Create daily digest

### Enums

```python
NotificationPriority:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

NotificationChannel:
    ACADEMIC = "academic"
    SOCIAL = "social"
    FINANCIAL = "financial"
    HEALTH = "health"
    HOUSING = "housing"
    EVENTS = "events"
    SYSTEM = "system"

DeliveryMethod:
    PUSH = "push"
    EMAIL = "email"
    SMS = "sms"
```

## Integration Examples

### From Assignment System
```python
from university_system.modules.domain.notifications import NotificationsService

service = NotificationsService()

# Notify about new assignment
service.create_notification(
    user_id=student_id,
    channel='academic',
    priority='medium',
    title=f'New Assignment: {assignment_title}',
    message=f'A new assignment has been posted for {course_code}. Due: {due_date}',
    source_system='Assignment System',
    source_id=f'assignment_{assignment_id}'
)
```

### From Financial System
```python
# Payment due reminder
service.create_notification(
    user_id=student_id,
    channel='financial',
    priority='high',
    title='Tuition Payment Due Soon',
    message=f'Your tuition payment of ${amount} is due on {due_date}',
    source_system='Financial Services',
    source_id=f'payment_{payment_id}',
    expires_at=due_date
)
```

### From Health Services
```python
# Appointment reminder
service.create_notification(
    user_id=student_id,
    channel='health',
    priority='high',
    title='Health Appointment Tomorrow',
    message=f'Your appointment at {time} with {doctor}. Location: {location}',
    source_system='Health Services',
    source_id=f'appointment_{appointment_id}'
)
```

## Configuration

### Default Settings
- **Quiet Hours**: 22:00 - 08:00
- **Daily Digest**: Disabled (08:00 when enabled)
- **Bundling**: Enabled (5-minute window)
- **All Channels**: Enabled with minimum priority "low"
- **Delivery Methods**: Push and Email enabled, SMS disabled

### Customization
Users can customize all settings through:
1. GUI Preferences panel
2. CLI Settings menu
3. Direct service API calls

## Performance

### Indexes
Optimized database indexes for common queries:
- User + read status + created date (notification list)
- User + channel + created date (channel filter)
- Priority + created date (priority filter)

### Scalability
- Connection pooling for concurrent access
- Efficient batch operations (mark all as read)
- Automatic cleanup of old notifications
- Bundle aggregation reduces notification volume

## Testing

### Manual Testing

**CLI Testing:**
```bash
python -m university_system.modules.domain.notifications.cli.notifications_cli
```

**GUI Testing:**
The Notifications GUI is now integrated into the Email Manager. To test:
```bash
# Run the email manager
python -m university_system.modules.shared.gui.email.email_gui.email_manager_main

# Then navigate to the Notifications tab, or use the menu:
# Communication > Notifications Hub
```

For backward compatibility testing:
```bash
# This will open the Email Manager with notifications focused
python -c "from university_system.modules.domain.notifications.gui import NotificationsGUI; app = NotificationsGUI(); app.run()"
```

### Test Scenarios
1. Create notifications across different channels
2. Filter by channel and priority
3. Configure quiet hours spanning midnight
4. Enable daily digest and verify bundling
5. Test notification expiration
6. Verify delivery tracking
7. Check statistics accuracy

## Maintenance

### Database Cleanup
```python
# Delete read notifications older than 30 days
count = service.delete_old_notifications(user_id, days=30)
```

### Monitoring
Check notification statistics to monitor:
- Unread notification accumulation
- Channel distribution
- Priority distribution
- Daily notification volume

## Troubleshooting

### Notifications Not Appearing
1. Check channel is enabled: `get_channel_settings()`
2. Verify priority meets minimum threshold
3. Check quiet hours configuration
4. Review daily digest settings

### Quiet Hours Not Working
- Ensure time format is HH:MM (24-hour)
- Verify midnight-spanning logic (22:00-08:00)
- Check urgent notifications override quiet hours

### Performance Issues
- Run database cleanup for old notifications
- Check notification volume per user
- Review bundle settings
- Monitor database indexes

## Future Enhancements

Potential future improvements:
- Real-time push notification delivery
- Mobile app integration
- Notification templates
- Advanced filtering (date ranges, search)
- Notification forwarding rules
- Integration with external notification services (Twilio, SendGrid)
- Analytics dashboard
- A/B testing for notification effectiveness

## Dependencies

- `sqlite3`: Database operations
- `datetime`: Timestamp handling
- `enum`: Enumeration types
- `tkinter`: GUI interface
- University infrastructure:
  - `database.db`: Connection management
  - `shared_context`: Authentication
  - `activity_logger`: Audit logging

## License

Part of the University Management System v5.0.0

## Support

For issues or questions about the Smart Notifications Hub:
1. Check this README
2. Review code documentation
3. Check activity logs for errors
4. Contact system administrator

# Campus Navigation Module

A comprehensive campus navigation and wayfinding system that provides interactive maps, accessible route planning, and location finding services for students, staff, and visitors.

## Features

### Core Functionality
- **Building Directory**: Searchable directory of all campus buildings with detailed information
- **Interactive Campus Map**: Visual representation of campus with building locations
- **Route Planning**: Calculate walking routes between any two campus locations
- **Accessible Routes**: Specialized routing for users requiring accessible paths
- **Find Nearest**: Quick search for nearby amenities (restrooms, study spaces, food, etc.)
- **Points of Interest**: Database of important locations within buildings
- **User Favorites**: Save frequently visited locations for quick access
- **Navigation History**: Track and analyze navigation patterns

### Accessibility Features
- Elevator availability indicators
- Wheelchair ramp locations
- Automatic door indicators
- Accessible route calculation
- Accessibility issue reporting

## Module Structure

```
campus_navigation/
├── __init__.py                 # Module exports
├── services/
│   ├── __init__.py
│   └── navigation_service.py  # Core navigation service layer
├── cli/
│   ├── __init__.py
│   └── navigation_cli.py      # Command-line interface
└── gui/
    ├── __init__.py
    └── navigation_gui.py      # Graphical user interface
```

## Database Schema

### Tables

#### campus_buildings
Stores information about campus buildings.

| Column | Type | Description |
|--------|------|-------------|
| building_id | INTEGER | Primary key |
| building_code | TEXT | Unique building code (e.g., "LIB", "GYM") |
| building_name | TEXT | Full building name |
| building_type | TEXT | Type (Academic, Housing, Athletic, etc.) |
| description | TEXT | Building description |
| latitude | REAL | GPS latitude coordinate |
| longitude | REAL | GPS longitude coordinate |
| address | TEXT | Physical address |
| floors | INTEGER | Number of floors |
| is_accessible | BOOLEAN | Wheelchair accessible |
| has_elevator | BOOLEAN | Elevator available |
| has_ramp | BOOLEAN | Wheelchair ramp available |
| has_automatic_doors | BOOLEAN | Automatic doors installed |
| operating_hours | TEXT | Hours of operation |
| amenities | TEXT | Available amenities (comma-separated) |
| image_url | TEXT | Building image URL |
| created_at | TEXT | Creation timestamp |
| updated_at | TEXT | Last update timestamp |

#### points_of_interest
Stores specific locations within buildings.

| Column | Type | Description |
|--------|------|-------------|
| poi_id | INTEGER | Primary key |
| building_id | INTEGER | Foreign key to campus_buildings |
| poi_name | TEXT | Point of interest name |
| poi_type | TEXT | Type (Service, Study Space, Dining, etc.) |
| floor_number | INTEGER | Floor location |
| room_number | TEXT | Room number |
| description | TEXT | POI description |
| latitude | REAL | GPS latitude (if different from building) |
| longitude | REAL | GPS longitude (if different from building) |
| is_accessible | BOOLEAN | Wheelchair accessible |
| operating_hours | TEXT | Hours of operation |
| contact_info | TEXT | Contact information |
| tags | TEXT | Searchable tags (comma-separated) |
| created_at | TEXT | Creation timestamp |

#### campus_routes
Stores calculated routes between locations.

| Column | Type | Description |
|--------|------|-------------|
| route_id | INTEGER | Primary key |
| route_name | TEXT | Route name |
| start_location_id | INTEGER | Foreign key to start building |
| end_location_id | INTEGER | Foreign key to end building |
| route_type | TEXT | Route type (Walking, Accessible, etc.) |
| is_accessible | BOOLEAN | Accessible route flag |
| distance_meters | REAL | Route distance in meters |
| estimated_time_minutes | INTEGER | Estimated walking time |
| waypoints | TEXT | JSON array of waypoints |
| description | TEXT | Route description |
| elevation_change | REAL | Total elevation change |
| created_at | TEXT | Creation timestamp |

#### navigation_history
Tracks user navigation history for analytics.

| Column | Type | Description |
|--------|------|-------------|
| history_id | INTEGER | Primary key |
| user_id | TEXT | User identifier |
| start_location | TEXT | Starting location name |
| end_location | TEXT | Destination name |
| route_taken | TEXT | Route identifier |
| duration_minutes | INTEGER | Actual duration |
| accessibility_required | BOOLEAN | Accessible route used |
| navigation_date | TEXT | Navigation timestamp |
| rating | INTEGER | User rating (1-5) |
| feedback | TEXT | User feedback |

#### navigation_favorites
Stores user favorite locations.

| Column | Type | Description |
|--------|------|-------------|
| favorite_id | INTEGER | Primary key |
| user_id | TEXT | User identifier |
| location_type | TEXT | Type (building or poi) |
| location_id | INTEGER | Building or POI ID |
| nickname | TEXT | User-defined nickname |
| created_at | TEXT | Creation timestamp |

## Usage Examples

### Service Layer

```python
from university_system.modules.domain.campus_navigation import NavigationService

# Initialize service
service = NavigationService()

# Get all buildings
buildings = service.get_all_buildings()

# Search for buildings
results = service.search_buildings("Library")

# Get specific building
library = service.get_building(building_code="LIB")

# Calculate route
route = service.calculate_route(
    start_location_id=1,
    end_location_id=5,
    require_accessible=True
)

# Find nearest amenities
nearest = service.find_nearest(
    location_type="Study",
    latitude=40.7128,
    longitude=-74.0060,
    limit=5
)

# Get points of interest
pois = service.get_points_of_interest(building_id=2)

# Manage favorites (requires authentication)
favorite_id = service.add_favorite(
    user_id="student123",
    location_type="building",
    location_id=1,
    nickname="My Dorm"
)

favorites = service.get_favorites(user_id="student123")
```

### CLI Interface

```python
from university_system.modules.domain.campus_navigation import NavigationCLI

# Run CLI
cli = NavigationCLI()
cli.display_menu()
```

Or run directly:
```bash
python -m university_system.modules.domain.campus_navigation.cli.navigation_cli
```

### GUI Interface

```python
from university_system.modules.domain.campus_navigation import NavigationGUI

# Standalone window
app = NavigationGUI()
app.run()

# Or embedded in parent window
import tkinter as tk
root = tk.Tk()
app = NavigationGUI(parent=root)
root.mainloop()
```

## API Reference

### NavigationService

#### Building Management

- **`get_all_buildings(building_type: Optional[str] = None) -> List[Dict]`**
  - Get all campus buildings, optionally filtered by type
  - Returns: List of building dictionaries

- **`get_building(building_id: int = None, building_code: str = None) -> Optional[Dict]`**
  - Get specific building by ID or code
  - Returns: Building dictionary or None

- **`search_buildings(search_term: str) -> List[Dict]`**
  - Search buildings by name, code, type, or description
  - Returns: List of matching buildings

#### Points of Interest

- **`get_points_of_interest(building_id: Optional[int] = None, poi_type: Optional[str] = None) -> List[Dict]`**
  - Get POIs, optionally filtered by building or type
  - Returns: List of POI dictionaries

- **`search_points_of_interest(search_term: str, tags: Optional[List[str]] = None) -> List[Dict]`**
  - Search POIs by name, type, description, or tags
  - Returns: List of matching POIs

#### Route Planning

- **`calculate_route(start_location_id: int, end_location_id: int, require_accessible: bool = False) -> Dict`**
  - Calculate route between two buildings
  - Returns: Route dictionary with distance, time, waypoints, and directions
  - Raises: ValueError if buildings not found or route not possible

- **`find_nearest(location_type: str, latitude: float, longitude: float, limit: int = 5) -> List[Dict]`**
  - Find nearest locations of a specific type
  - Returns: List of locations sorted by distance

#### Favorites

- **`add_favorite(user_id: str, location_type: str, location_id: int, nickname: str = "") -> int`**
  - Add location to user's favorites
  - Returns: Favorite ID

- **`get_favorites(user_id: str) -> List[Dict]`**
  - Get all favorites for a user
  - Returns: List of favorite dictionaries

- **`remove_favorite(favorite_id: int) -> bool`**
  - Remove a favorite location
  - Returns: Success status

#### History & Analytics

- **`save_navigation_history(user_id: str, start_location: str, end_location: str, route_taken: str, duration_minutes: int, accessibility_required: bool = False) -> int`**
  - Save navigation history entry
  - Returns: History ID

- **`rate_navigation(history_id: int, rating: int, feedback: str = "") -> bool`**
  - Rate a navigation experience (1-5 stars)
  - Returns: Success status

- **`get_popular_routes(limit: int = 10) -> List[Dict]`**
  - Get most popular navigation routes
  - Returns: List of routes with usage statistics

- **`get_building_stats(building_id: int) -> Dict`**
  - Get statistics for a building
  - Returns: Dictionary with navigation and POI stats

## Sample Data

The module initializes with 10 sample campus buildings:

1. **MAIN** - Main Administration Building
2. **LIB** - University Library (5 floors, 24/7 access)
3. **SCI** - Science Building (Labs and classrooms)
4. **ENG** - Engineering Hall (Maker spaces)
5. **GYM** - Recreation Center (Gym, pool, courts)
6. **DORM1** - North Residence Hall (6 floors)
7. **DORM2** - South Residence Hall (8 floors)
8. **UNION** - Student Union (Food court, bookstore)
9. **MED** - Health Center (Medical and counseling)
10. **ART** - Arts Building (Studios, gallery, performance hall)

And 11 sample points of interest including study spaces, dining options, services, and athletic facilities.

## CLI Features

The CLI provides an interactive menu with the following options:

1. **Building Directory** - Browse, search, and filter buildings
2. **Search Locations** - Search both buildings and POIs
3. **Get Directions** - Calculate routes between locations
4. **Find Nearest Amenity** - Quick search for nearby facilities
5. **View Points of Interest** - Browse POIs by type or building
6. **My Favorites** - Manage favorite locations (requires login)
7. **Report Accessibility Issue** - Report accessibility problems
8. **View Campus Map** - Text-based campus map visualization

## GUI Features

The GUI provides a rich graphical interface with:

### Left Panel (Tabbed Interface)
- **Directory Tab**: Search and filter buildings
- **Get Directions Tab**: Route planning with accessible option
- **Find Nearest Tab**: Quick searches for common amenities
- **Favorites Tab**: Manage saved locations (requires login)

### Right Panel
- **Campus Map**: Interactive canvas showing all buildings
  - Color-coded by building type
  - Click to view building details
  - Shows calculated routes with arrows
  - Hover for quick information
- **Location Details**: Displays detailed information about selected buildings

### Map Features
- Color-coded buildings by type
- Interactive building selection
- Route visualization with directional arrows
- Building legend
- Scalable coordinates based on actual GPS data

## Configuration

No additional configuration required. The module uses:
- Centralized database via `university_system.infrastructure.database.db`
- Activity logging via `university_system.modules.shared.utils.activity_logger`
- Authentication via `university_system.infrastructure.shared_context`

## Testing

Run the test script:
```bash
python test_navigation.py
```

Test the CLI:
```bash
python test_navigation_cli.py
```

## Dependencies

- Python 3.8+
- tkinter (for GUI)
- sqlite3 (built-in)
- math (built-in)
- json (built-in)

Project-specific dependencies:
- university_system.infrastructure.database
- university_system.modules.shared.utils.activity_logger
- university_system.infrastructure.shared_context

## Future Enhancements

Potential improvements for future versions:

1. **Real-time GPS tracking** - Track user location on campus
2. **Indoor navigation** - Floor-by-floor navigation within buildings
3. **Live updates** - Real-time building hours and closures
4. **Multi-modal routing** - Include bus routes, bike paths
5. **Crowd-sourced updates** - User-submitted POIs and reviews
6. **AR navigation** - Augmented reality wayfinding
7. **Voice navigation** - Turn-by-turn audio directions
8. **Parking integration** - Find and navigate to parking spots
9. **Event integration** - Navigate to scheduled events
10. **Weather routing** - Indoor routes during bad weather

## Accessibility Commitment

This module is designed with accessibility as a core principle:
- All routes can be calculated with accessibility requirements
- Clear indicators for wheelchair access, elevators, and ramps
- High-contrast GUI colors
- Keyboard navigation support in GUI
- Screen reader compatible (CLI mode)
- Accessibility issue reporting system

## Support

For issues or feature requests, please contact:
- Campus IT Support: it-support@university.edu
- Accessibility Services: accessibility@university.edu
- Facilities Management: facilities@university.edu

## License

Part of the University Management System v5.0.0

# Interest-Based Social Matching Module

A comprehensive social connection platform that helps students find like-minded peers based on shared interests, hobbies, and activities.

## Overview

The Social Matching module provides an intelligent matching system that connects students through:

- **Interest-Based Matching**: Find students with similar hobbies, music taste, career goals, and more
- **Study Abroad Buddy Finder**: Connect with students going to the same destination
- **Intramural Sports Team Formation**: Create and join sports teams
- **Club Recommendations**: Get personalized club suggestions based on your interests
- **Social Activity Discovery**: Find and join activities that match your interests
- **Personality-Based Matching**: Match based on personality types and social preferences
- **Privacy Controls**: Fine-grained control over profile visibility and matching

## Features

### Core Matching Algorithm

The system uses a sophisticated compatibility scoring algorithm that:

1. **Analyzes shared interests** across 10 categories:
   - Sports
   - Music
   - Arts
   - Gaming
   - Outdoor
   - Technology
   - Academic
   - Career
   - Travel
   - Other

2. **Calculates compatibility scores** (0-100%) based on:
   - Number of shared interests
   - Interest levels (1-10 scale)
   - Level similarity between users
   - Personality compatibility

3. **Respects privacy settings**:
   - Public/private interest visibility
   - Search visibility controls
   - Message permissions
   - Profile visibility options

### Interest Management

- **Add interests** with customizable levels (1-10)
- **Categorize interests** for better organization
- **Public/private visibility** per interest
- **Tag cloud visualization** in GUI
- **Interest level tracking** for compatibility scoring

### Buddy Requests

- **Send/receive buddy requests** with custom messages
- **Request types**: General, Study Abroad, Sports, Academic, Other
- **Study abroad destination matching**
- **Request status tracking**: Pending, Accepted, Declined
- **Message history** for all requests

### Study Abroad Buddy Finder

- **Destination-based matching**: Find students going to the same location
- **Compatibility scoring** with shared interests
- **Semester filtering** (optional)
- **Direct buddy request** integration

### Team Formation

- **Create intramural sports teams**:
  - Team name and description
  - Sport type
  - Target team size
  - Skill level (Beginner, Intermediate, Advanced, Mixed)

- **Join existing teams**:
  - Browse available teams
  - Filter by sport and skill level
  - View team details and member count
  - Automatic capacity management

- **Team roles**:
  - Captain (team creator)
  - Member (regular team member)

### Club Recommendations

- **Personalized recommendations** based on user interests
- **Match scoring** calculated from:
  - Interest category alignment
  - Interest tag matching
  - Interest level weighting

- **Sample clubs** across all categories:
  - Sports (Basketball League, Running Club)
  - Music (Acapella Group, DJ Club)
  - Arts (Photography Society, Drama Club)
  - Gaming (eSports Team, Board Game Society)
  - Technology (Coding Club, Robotics Team)
  - Academic (Debate Society, Research Symposium)
  - Career (Entrepreneurship Club, Professional Network)
  - Travel (Study Abroad Alumni)
  - Outdoor (Adventure Club)

### Social Activities

- **Create activities**:
  - Name, type, and description
  - Location and date/time
  - Maximum participant capacity
  - Related interests

- **Discover suggested activities**:
  - Interest-based filtering
  - Match score calculation
  - Date range filtering (default 30 days)

- **RSVP options**:
  - Going
  - Interested
  - Maybe

- **Activity management**:
  - View upcoming activities
  - Track participant count
  - Automatic capacity enforcement

### Personality Profile

Track personality traits for better matching:

- **Personality types**:
  - Introvert
  - Extrovert
  - Ambivert

- **Personality scores** (1-10):
  - Extroversion level
  - Openness to new experiences

- **Social preferences**:
  - Preferred group size (One-on-One, Small, Medium, Large)
  - Activity level (Low, Moderate, High, Very High)
  - Custom social preference description

### Privacy & Security

Comprehensive privacy controls:

- **Allow Matching**: Enable/disable matching system
- **Show Profile**: Control profile visibility
- **Allow Messages**: Accept/reject buddy requests
- **Show Interests**: Make interests visible to others
- **Show in Search**: Appear in match searches
- **Match Same Major**: Restrict matches to same major
- **Match Same Year**: Restrict matches to same year

All settings default to permissive (enabled) except major/year filters.

## Database Schema

### Tables

1. **user_interests**: User interest profiles
   - Interest categories and names
   - Interest levels (1-10)
   - Public/private visibility

2. **interest_matches**: Calculated compatibility matches
   - User pairs
   - Compatibility scores
   - Shared interests list
   - Match status

3. **buddy_requests**: Social buddy requests
   - Sender/receiver
   - Request type
   - Destination (for study abroad)
   - Message and status

4. **team_formations**: Intramural sports teams
   - Team details
   - Sport type and skill level
   - Member count tracking

5. **team_members**: Team membership
   - Team-user associations
   - Member roles

6. **club_suggestions**: Personalized club recommendations
   - Club details
   - Match scores and reasons

7. **social_activities**: Social events and activities
   - Activity details
   - Date, time, location
   - Participant capacity

8. **activity_participants**: Activity attendance
   - User-activity associations
   - RSVP status

9. **user_personality**: Personality profiles
   - Personality type and scores
   - Social preferences

10. **user_privacy_settings**: Privacy controls
    - Visibility settings
    - Matching restrictions

## Usage

### Service Layer

```python
from university_system.modules.domain.social_matching import SocialMatchingService

service = SocialMatchingService()

# Add interests
service.add_user_interest(
    user_id="student123",
    category="Sports",
    interest_name="Basketball",
    interest_level=8,
    is_public=True
)

# Find matches
matches = service.find_interest_matches(
    user_id="student123",
    min_score=30.0,
    max_results=20
)

# Send buddy request
request_id = service.send_buddy_request(
    sender_id="student123",
    receiver_id="student456",
    request_type="study_abroad",
    destination="Spain",
    message="Hey! I see we're both going to Spain. Want to connect?"
)

# Create team
team_id = service.create_team(
    creator_id="student123",
    team_name="Court Kings",
    sport_type="Basketball",
    team_size=5,
    skill_level="Intermediate",
    description="Looking for serious but fun players"
)

# Get club recommendations
recommendations = service.generate_club_recommendations(
    user_id="student123"
)

# Create social activity
activity_id = service.create_social_activity(
    creator_id="student123",
    activity_name="Weekend Hike",
    activity_type="Outdoor",
    description="Easy 5-mile trail hike",
    location="Mountain Trail Park",
    activity_date="2026-01-20",
    activity_time="09:00",
    max_participants=15,
    interests_matched=["Hiking", "Outdoor", "Nature"]
)
```

### CLI Interface

```bash
# Run the CLI
python -m university_system.modules.domain.social_matching.cli.social_matching_cli

# Or from within the application
from university_system.modules.domain.social_matching.cli import SocialMatchingCLI

cli = SocialMatchingCLI()
cli.run()
```

**CLI Features:**

- Manage interests (add, view, update, remove)
- Find and view matches with compatibility scores
- Send and respond to buddy requests
- Create and join teams
- View club recommendations
- Browse and join social activities
- Manage personality profile
- Configure privacy settings
- View statistics

### GUI Interface

```python
import tkinter as tk
from university_system.modules.domain.social_matching.gui import SocialMatchingGUI

root = tk.Tk()
app = SocialMatchingGUI(root)
root.mainloop()
```

**GUI Features:**

- **Interests Tab**: Visual interest management with tag display
- **Matches Tab**: Match results with compatibility scores and shared interests
- **Buddy Requests Tab**: Sent/received request management with details
- **Teams Tab**: Team creation and browsing with filters
- **Clubs Tab**: Personalized club recommendations grid
- **Activities Tab**: Activity discovery and RSVP management
- **Profile Tab**: Personality profile and privacy settings with statistics

## Architecture

```
social_matching/
├── database/
│   ├── __init__.py
│   └── db_init.py              # Database schema and initialization
├── services/
│   ├── __init__.py
│   └── social_matching_service.py  # Core business logic
├── cli/
│   ├── __init__.py
│   └── social_matching_cli.py  # Command-line interface
├── gui/
│   ├── __init__.py
│   └── social_matching_gui.py  # Tkinter GUI interface
├── __init__.py
└── README.md
```

## Compatibility Scoring Algorithm

The system calculates compatibility scores using the following formula:

1. **Find Shared Interests**:
   - Intersect interest sets between two users
   - Only consider public interests

2. **Calculate Raw Score**:
   ```
   For each shared interest:
     avg_level = (user1_level + user2_level) / 2
     similarity = 1 - |user1_level - user2_level| / 10
     score += avg_level * similarity
   ```

3. **Normalize Score**:
   ```
   max_possible = shared_count * 10
   normalized_score = (score / max_possible) * 100
   ```

4. **Return**:
   - Score (0-100%)
   - List of shared interests

**Example:**

- User A: Basketball (8), Soccer (6), Gaming (7)
- User B: Basketball (9), Soccer (5), Music (8)

Shared: Basketball, Soccer

```
Basketball:
  avg = (8 + 9) / 2 = 8.5
  sim = 1 - |8 - 9| / 10 = 0.9
  score = 8.5 * 0.9 = 7.65

Soccer:
  avg = (6 + 5) / 2 = 5.5
  sim = 1 - |6 - 5| / 10 = 0.9
  score = 5.5 * 0.9 = 4.95

Total: 7.65 + 4.95 = 12.6
Max: 2 interests * 10 = 20
Normalized: (12.6 / 20) * 100 = 63%
```

## Privacy & Data Protection

- **Opt-in matching**: Users must enable matching to appear in searches
- **Interest visibility**: Individual interests can be marked private
- **Message control**: Users can disable buddy requests
- **Search visibility**: Users can hide from search results
- **Profile visibility**: Separate control for profile viewing
- **Filtering options**: Match same major/year only

All privacy settings are checked before:
- Displaying user in search results
- Calculating matches
- Sending buddy requests
- Showing profile information

## Statistics & Analytics

Track user engagement with:

- Total interests added
- Total matches found (score ≥ 30%)
- Buddy requests sent/received
- Teams joined
- Activities joined

Accessible via:
- `service.get_user_statistics(user_id)`
- CLI menu option "My Statistics"
- GUI "Profile & Settings" tab

## Constants

### Interest Categories
```python
INTEREST_CATEGORIES = [
    'Sports', 'Music', 'Arts', 'Gaming', 'Outdoor',
    'Technology', 'Academic', 'Career', 'Travel', 'Other'
]
```

### Personality Types
```python
PERSONALITY_TYPES = [
    'Introvert', 'Extrovert', 'Ambivert'
]
```

### Group Size Preferences
```python
GROUP_SIZE_PREFERENCES = [
    'One-on-One',
    'Small Group (3-5)',
    'Medium Group (6-10)',
    'Large Group (10+)'
]
```

### Activity Levels
```python
ACTIVITY_LEVELS = [
    'Low', 'Moderate', 'High', 'Very High'
]
```

## Integration

### With Authentication System

The module integrates with the university's authentication system:

```python
from university_system.infrastructure.shared_context import get_auth

auth = get_auth()
if auth.is_logged_in():
    user_id = auth.get_current_user()['username']
```

### With Activity Logger

All significant actions are logged:

```python
from university_system.modules.shared.utils.activity_logger import log_activity

log_activity('create', 'user_interest', user_id=user_id,
            details={'category': category, 'interest': interest_name})
```

### With Database Layer

Uses the centralized database connection pool:

```python
from university_system.infrastructure.database.db import get_connection, transaction

with transaction() as conn:
    # Database operations with automatic commit/rollback
    pass
```

## Future Enhancements

Potential additions:

1. **Event Attendance Tracking**: Check-in system for activities
2. **Rating System**: Rate matches and activities
3. **Messaging System**: Direct chat with matched students
4. **Notification System**: Push notifications for new matches/requests
5. **Advanced Filtering**: Location-based, schedule compatibility
6. **Machine Learning**: Improve match recommendations over time
7. **Social Graph**: Visualize connection networks
8. **Group Matching**: Find groups instead of individuals
9. **Interest Discovery**: Suggest new interests based on profile
10. **Integration**: Connect with external social platforms

## Testing

Initialize the database:

```bash
python -m university_system.modules.domain.social_matching.database.db_init
```

Run the CLI interface:

```bash
python -m university_system.modules.domain.social_matching.cli.social_matching_cli
```

Run the GUI interface:

```bash
python -m university_system.modules.domain.social_matching.gui.social_matching_gui
```

## Dependencies

- Python 3.8+
- tkinter (for GUI)
- sqlite3 (built-in)
- University system infrastructure:
  - Authentication system
  - Database layer
  - Activity logger

## License

Part of the University Management System v5.0.0

## Author

Social Matching Module v1.0.0
January 2026

# Car Rental Refund System Documentation

## Overview

The Car Rental GUI includes a comprehensive refund management system that allows users to process refunds for rental transactions through multiple payment methods, with automated email confirmations and finance system integration.

## Features Implemented

### ✅ 1. Refunds Tab
Located in the main Car Rental GUI notebook, accessible via the "Refunds" tab.

**Features:**
- **Transaction List**: Displays all car rental transactions with searchable filtering
- **Status Tracking**: Shows whether transactions are active or refunded
- **Search Functionality**: Real-time search across transaction details
- **Color-Coded Display**: Visual indication of refund status

### ✅ 2. Multiple Refund Methods

Users can choose from three refund methods:

#### 💵 Cash Refund
- Processes refund as cash payment
- Creates refund record in database
- Updates transaction status to "refunded"
- Sends email confirmation to customer

#### 💳 Card Refund
- Processes refund to customer's card
- Creates refund record in database
- Updates transaction status to "refunded"
- Sends email confirmation to customer

#### 🏦 Student Account Refund
- Credits amount to student's finance account
- Updates student account balance in real-time
- Logs transaction in `student_finance_transactions` table
- Shows current and new balance before processing
- Sends email confirmation with new balance
- **Most Popular Option**: Instant credit to student account

### ✅ 3. Email Confirmation System

**Automated Email Receipts Include:**
- Customer name and contact information
- Refund amount (£XX.XX format)
- Refund method used
- Unique reference number (e.g., `CARRENTAL-REFUND-20260127095500`)
- Processing timestamp
- New student account balance (for student account refunds)
- Professional email formatting

**Email Template:**
```
Dear [Customer Name],

This is to confirm that your car rental refund has been processed successfully.

Refund Details:
- Refund Amount: £XX.XX
- Refund Method: [Cash/Card/Student Finance Account]
- Reference Number: CARRENTAL-REFUND-XXXXXXXXXXXX
- Date: YYYY-MM-DD HH:MM

[If student account refund:]
Your new student account balance is: £XXX.XX

If you have any questions about this refund, please contact the car rental service.

Best regards,
University Car Rental Service
```

### ✅ 4. Finance System Integration

**Finance GUI Database Integration:**
- Creates `finance_refunds` table for centralized refund tracking
- Records each refund with:
  - Unique refund reference number
  - Department identifier: "Car Rental"
  - Original transaction ID
  - Refund amount
  - Refund method used
  - Processing user/admin
  - Processing timestamp
  - Additional notes

**Student Account Integration:**
- Updates `student_finance_accounts` table
- Logs in `student_finance_transactions` table
- Maintains accurate balance tracking
- Provides audit trail for all financial operations

### ✅ 5. Database Schema

**carrental_refunds Table:**
```sql
CREATE TABLE carrental_refunds (
    refund_id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id INTEGER,
    customer_id TEXT,
    amount DECIMAL(10,2),
    refund_method TEXT,
    refund_reference TEXT,
    refunded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_by TEXT,
    FOREIGN KEY (transaction_id) REFERENCES carrental_transactions(transaction_id)
)
```

**finance_refunds Table:**
```sql
CREATE TABLE finance_refunds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    refund_reference TEXT UNIQUE,
    department TEXT,
    transaction_id TEXT,
    amount DECIMAL(10,2),
    refund_method TEXT,
    refund_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_by TEXT,
    notes TEXT
)
```

### ✅ 6. User Interface

**Refunds Tab Components:**
1. **Search Bar**: Real-time filtering of transactions
2. **Transaction Table**: Shows all rental transactions with columns:
   - Transaction ID
   - Date
   - Customer
   - Amount
   - Transaction Type
   - Payment Method
   - Status (active/refunded)
3. **Action Buttons**:
   - **Process Refund**: Initiates refund workflow
   - **View Details**: Shows complete transaction information
   - **Refresh**: Reloads transaction list
   - **Export to CSV**: Exports refund data

**Refund Method Dialog:**
- Clean, centered dialog window
- Shows refund amount prominently
- Displays current student account balance (if applicable)
- Shows projected new balance after refund
- Large, clear buttons for each refund method
- Cancel option to abort process

### ✅ 7. Transaction Details View

**Comprehensive Information Display:**
- Transaction ID and reference number
- Customer information (ID, name, email)
- Financial details (amount, payment method, status)
- Processing information (date, processed by)
- Rental information:
  - Vehicle details (make, model, registration)
  - Rental dates (start and end)
  - Rental duration
- Scrollable interface for long details

### ✅ 8. Export Functionality

**CSV Export Features:**
- Export all transactions to CSV format
- Customizable filename with timestamp
- Includes all transaction fields:
  - Transaction Number
  - Date
  - Customer
  - Amount
  - Transaction Type
  - Payment Method
  - Status
- Compatible with Excel and other spreadsheet software

## Recent Bug Fixes (2026-01-27)

### Issue #1: Database Column Error - `full_name`
**Problem**: Code was querying `full_name` column which doesn't exist in students table.

**Fixed Locations:**
- `send_carrental_refund_receipt()` method (line 1499)
- `view_carrental_transaction_details()` method (line 1614)

### Issue #1b: Database Column Error - `email`
**Problem**: Code was querying `email` column which doesn't exist in students table. The correct column name is `email_address`.

**Error Message:**
```
no such column: email
```

**Fixed Locations:**
- `send_carrental_refund_receipt()` method (line 1600)
- `view_carrental_transaction_details()` method (line 1716)

**Solution:**
```python
# Before (incorrect):
cursor.execute("SELECT email, full_name FROM students WHERE student_id = ?", (customer_id,))

# After (correct):
cursor.execute("SELECT email, first_name, last_name FROM students WHERE student_id = ?", (customer_id,))
result = cursor.fetchone()
customer_email = result[0]
first_name = result[1] or ''
last_name = result[2] or ''
customer_name = f"{first_name} {last_name}".strip() or customer_id
```

For JOIN queries:
```sql
-- Correct approach using SQL concatenation
SELECT
    TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, '')) as customer_name
FROM students s
```

### Issue #2: Email Parameter Error
**Problem**: Using incorrect parameter name `to_email` instead of `recipient_email`.

**Fixed Location:**
- `send_carrental_refund_receipt()` method (line 1541)

**Solution:**
```python
# Before (incorrect):
send_email(
    to_email=customer_email,
    subject=f"Car Rental Refund Receipt - {refund_ref}",
    body=email_body
)

# After (correct):
send_email(
    recipient_email=customer_email,
    subject=f"Car Rental Refund Receipt - {refund_ref}",
    body=email_body
)
```

## Usage Instructions

### For Students/Customers

**To Request a Refund:**
1. Open Car Rental GUI from main menu
2. Navigate to "Refunds" tab
3. Find your transaction in the list (use search if needed)
4. Select the transaction
5. Click "Process Refund" button
6. Choose refund method:
   - **Student Account** (recommended): Instant credit to your account
   - **Card**: Refund to original payment card
   - **Cash**: Receive cash refund
7. Confirm the refund
8. Check your email for confirmation receipt

### For Administrators

**To Process a Refund:**
1. Access Car Rental GUI with admin credentials
2. Go to "Refunds" tab
3. Search for the transaction (by ID, customer name, etc.)
4. Select the transaction
5. Click "Process Refund"
6. Verify transaction details
7. Choose appropriate refund method
8. Confirm refund processing
9. System automatically:
   - Updates transaction status
   - Creates refund record
   - Sends email to customer
   - Notifies finance system
   - Updates student account (if applicable)

**To View Transaction Details:**
1. Select transaction from list
2. Click "View Details"
3. Review comprehensive transaction information
4. Check rental details, payment info, and status

**To Export Refund Data:**
1. Click "Export to CSV" button
2. Choose save location
3. Open in spreadsheet software for analysis

## Security Features

- **Authentication Required**: Must be logged in to access refund system
- **Audit Trail**: All refunds logged with user who processed them
- **Status Tracking**: Prevents duplicate refunds (checks status before processing)
- **Confirmation Dialogs**: Requires explicit confirmation before processing
- **Transaction Integrity**: Uses database transactions to ensure data consistency

## Error Handling

The system includes comprehensive error handling:
- **Invalid Transaction**: Shows error if transaction not found
- **Already Refunded**: Prevents duplicate refunds with warning message
- **Missing Email**: Logs warning if customer email not available
- **Database Errors**: Gracefully handles database connection issues
- **Finance Integration Errors**: Continues operation even if finance notification fails

## Testing Recommendations

### Test Scenarios

1. **Cash Refund Flow**:
   - Select active transaction
   - Choose cash refund
   - Verify status updates to "refunded"
   - Check email sent to customer
   - Confirm finance_refunds entry created

2. **Card Refund Flow**:
   - Select active transaction
   - Choose card refund
   - Verify status updates to "refunded"
   - Check email sent to customer
   - Confirm finance_refunds entry created

3. **Student Account Refund Flow**:
   - Select active transaction
   - Choose student account refund
   - Verify balance updates correctly
   - Check student_finance_transactions entry
   - Verify email includes new balance
   - Confirm finance_refunds entry created

4. **Duplicate Refund Prevention**:
   - Try to refund already refunded transaction
   - Verify warning message appears
   - Confirm no changes made to database

5. **Email Delivery**:
   - Process refunds for students with valid emails
   - Check email inbox for confirmation
   - Verify all details are correct

6. **Search Functionality**:
   - Search by transaction ID
   - Search by customer name
   - Search by status
   - Verify results filter correctly

7. **Export Functionality**:
   - Export refunds to CSV
   - Open in Excel
   - Verify all columns present
   - Check data accuracy

## Integration Points

### Email Service
- **Module**: `university_system.infrastructure.email.email_service`
- **Function**: `send_email(recipient_email, subject, body)`
- **Purpose**: Send refund confirmation receipts

### Finance Integration
- **Module**: `university_system.modules.shared.utils.finance_integration`
- **Functions**:
  - `ensure_student_finance_account_exists(student_id)`
  - `get_student_finance_account_balance(student_id)`
- **Purpose**: Manage student account balances and transactions

### Database
- **Module**: `university_system.infrastructure.database.db`
- **Functions**:
  - `get_db_connection()`: Get database connection
  - `transaction()`: Transaction context manager
- **Purpose**: Ensure data integrity and ACID compliance

## File Locations

- **Main GUI**: `/home/seancatchpole989/university_system/modules/domain/carrental/gui/carrental_gui.py`
- **Core Services**: `/home/seancatchpole989/university_system/modules/domain/carrental/services/carrental_core.py`
- **Database**: `/home/seancatchpole989/university_system/data/db_files/student_records.db`

## Key Methods

| Method | Purpose | Line |
|--------|---------|------|
| `create_refunds_tab()` | Creates refunds management UI | 1079 |
| `process_carrental_refund()` | Initiates refund workflow | 1223 |
| `show_carrental_refund_method_dialog()` | Shows refund method selection | 1277 |
| `_complete_carrental_refund()` | Processes cash/card refunds | 1342 |
| `add_carrental_refund_to_student_account()` | Processes student account refunds | 1401 |
| `send_carrental_refund_receipt()` | Sends email confirmation | 1491 |
| `notify_carrental_finance_gui()` | Updates finance system | 1551 |
| `view_carrental_transaction_details()` | Shows transaction details | 1590 |
| `export_refunds_to_csv()` | Exports data to CSV | 1711 |
| `refresh_refunds_list()` | Refreshes transaction list | 1154 |

## Future Enhancements (Potential)

- [ ] Partial refunds (refund only a portion of the amount)
- [ ] Refund approval workflow for large amounts
- [ ] Automated refund processing for cancellations
- [ ] Integration with accounting software
- [ ] SMS notifications in addition to email
- [ ] Refund analytics dashboard
- [ ] Batch refund processing
- [ ] Refund reason tracking
- [ ] Customer refund history view

## Summary

The Car Rental Refund System provides a complete, production-ready solution for managing refunds with:
- ✅ Multiple refund methods
- ✅ Automated email confirmations
- ✅ Finance system integration
- ✅ Comprehensive audit trail
- ✅ User-friendly interface
- ✅ Robust error handling
- ✅ Export capabilities
- ✅ Real-time balance updates

All requested features have been implemented and tested!

# Mental Health & Wellness Hub

The Mental Health & Wellness Hub is a comprehensive module for tracking student wellness, mental health, and overall wellbeing. It provides discrete, confidential support services with prominent crisis resources.

## Features

### Service Layer (`services/wellness_service.py`)

#### Wellness Tracking
- **Wellness Check-ins**: Regular mood, stress, sleep, energy, and anxiety assessments (1-10 scale)
- **Mood Logging**: Track specific moods with intensity levels (1-5), triggers, and activities
- **Pattern Recognition**: Automatic analysis of mood trends and concerning patterns
- **Personalized Insights**: AI-driven recommendations based on wellness data

#### Sleep Management
- **Sleep Tracking**: Log bedtime, wake time, hours slept, quality, and interruptions
- **Sleep Analytics**: 30-day sleep pattern analysis with recommendations
- **Sleep Goals**: Set and track sleep hour targets
- **Quality Bonuses**: Extra wellness points for achieving 7+ hours with 4+ quality

#### Activity Tracking
- **Exercise Logging**: Track type, duration, intensity, and calories burned
- **Hydration Tracking**: Daily water intake with goal tracking (default: 8 glasses)
- **Activity Points**: Gamified rewards for healthy activities
- **Progress Visualization**: Real-time tracking of daily goals

#### Wellness Goals
- **Goal Types**: Sleep, exercise, hydration, meditation, stress reduction, weight, steps, custom
- **Progress Tracking**: Monitor current vs. target values
- **Achievement Bonuses**: 50 points for completing goals
- **Flexible Deadlines**: Optional end dates for goals

#### Counseling Services
- **Appointment Booking**: Schedule confidential counseling sessions
- **Appointment Types**: Individual, group, crisis, academic stress, relationships, anxiety/depression
- **Privacy First**: All appointments and notes are completely confidential
- **Appointment History**: View past and upcoming appointments

#### Crisis Resources
- **24/7 Hotlines**: National Suicide Prevention Lifeline (988), Crisis Text Line
- **Campus Resources**: Counseling Center, Campus Security
- **Always Visible**: Crisis resources prominently displayed in all interfaces
- **No Login Required**: Access crisis resources without authentication

#### Gamification
- **Wellness Points**: Earn points for all wellness activities
  - Check-in: 10 points
  - Mood log: 5 points
  - Sleep log: 5 points (+ 10 bonus for quality sleep)
  - Exercise: Up to 30 points based on duration
  - Hydration: 1 point per glass (max 10/day)
  - Goal achievement: 50 points
- **Achievement Levels**:
  - 🌱 Wellness Beginner (0-49 points)
  - ✨ Wellness Enthusiast (50-99 points)
  - 🎖️ Wellness Warrior (100-249 points)
  - 💎 Wellness Expert (250-499 points)
  - ⭐ Wellness Master (500-999 points)
  - 🏆 Wellness Champion (1000+ points)
- **Leaderboard**: Top wellness point earners

### CLI Interface (`cli/wellness_cli.py`)

#### Main Features
- **Interactive Menu**: Easy-to-navigate command-line interface
- **Crisis Resources Banner**: Always visible at the top of every screen
- **Real-time Points Display**: See your wellness points and level
- **Comprehensive Analytics**: Detailed reports and insights

#### Menu Options
1. Log Mood Entry
2. Complete Wellness Check-in
3. View Mood Trends & Insights
4. Track Sleep
5. View Sleep Analytics
6. Log Exercise Activity
7. Log Hydration
8. Set Wellness Goal
9. View Active Goals
10. Book Counseling Appointment
11. View My Appointments
12. View All Crisis Resources
13. View Wellness Points & Achievements
14. View Comprehensive Wellness Report

#### Features
- **Emoji Indicators**: Visual mood, stress, and quality indicators
- **Trend Analysis**: 30-day pattern recognition with concerns highlighted
- **Smart Recommendations**: Context-aware suggestions based on data
- **Privacy Notices**: Confidentiality reminders for counseling features

### GUI Interface (`gui/wellness_gui.py`)

#### Dashboard Tab
- **Wellness Summary Card**: Average scores for past 30 days
- **Mood Trend Chart**: Interactive matplotlib chart showing mood and stress over time
- **Recent Activities**: Last mood entries and active goals
- **Quick Actions**: Fast access to common tasks
- **Crisis Resources Panel**: Always visible at the top

#### Mood Tracking Tab
- **Emoji Mood Picker**: 10 mood types with emoji buttons
  - 😊 Happy, 😢 Sad, 😰 Anxious, 😤 Stressed, 😌 Calm
  - 😃 Excited, 😠 Angry, 😊 Content, 😵 Overwhelmed, ☮ Peaceful
- **Intensity Slider**: 1 (Mild) to 5 (Intense)
- **Trigger Input**: Record what caused the mood
- **Activity Notes**: Log helpful/harmful activities
- **Mood History**: Scrollable list of past entries

#### Sleep Tracking Tab
- **Sleep Log Form**: Date, bedtime, wake time, hours, quality, interruptions
- **Quality Slider**: 1 (Poor) to 5 (Excellent)
- **Sleep Analytics Display**: 30-day summary with recommendations
- **Goal Achievements**: Bonus point notifications

#### Activities Tab
- **Exercise Logging**:
  - Type selection (Running, Walking, Cycling, Swimming, Gym, Yoga, Sports, Dancing, Hiking, Other)
  - Duration, intensity, calories burned
  - Points calculation display
- **Hydration Tracking**:
  - Real-time progress bar
  - Daily goal visualization (X/8 glasses)
  - Completion percentage
  - Goal achievement celebration

#### Goals Tab
- **Goal Creation Form**:
  - Type selection (Sleep, Exercise, Hydration, Meditation, Stress, Weight, Steps, Custom)
  - Description and target value
  - Optional end date
- **Active Goals Display**:
  - Progress bars for each goal
  - Completion percentage
  - Start and end dates

#### Counseling Tab
- **Privacy Notice**: 🔒 Confidentiality reminder at top
- **Appointment Booking**:
  - Date and time selection
  - 7 appointment types
  - Confidential notes field
- **Appointment History**: Past and upcoming appointments with status

#### Resources Tab
- **Crisis Resources**: Full details for all 24/7 resources
  - Resource name and type
  - Contact information (bold, prominent)
  - Description and availability
- **Emergency Notice**: Red warning for immediate danger situations

## Database Schema

### Tables

#### `wellness_checkins`
- `checkin_id`: Primary key
- `student_id`: Foreign key to students
- `checkin_date`: Date of check-in
- `overall_mood`: 1-10 scale
- `stress_level`: 1-10 scale
- `sleep_quality`: 1-10 scale
- `energy_level`: 1-10 scale
- `anxiety_level`: 1-10 scale
- `notes`: Optional text
- `created_at`: Timestamp

#### `mood_tracking`
- `mood_id`: Primary key
- `student_id`: Foreign key to students
- `mood_date`: Date of mood entry
- `mood_type`: Mood category
- `intensity`: 1-5 scale
- `triggers`: What caused the mood
- `activities`: Related activities
- `notes`: Additional notes
- `created_at`: Timestamp

#### `sleep_tracking`
- `sleep_id`: Primary key
- `student_id`: Foreign key to students
- `sleep_date`: Date of sleep
- `bedtime`: Time went to bed
- `wake_time`: Time woke up
- `hours_slept`: Total hours
- `sleep_quality`: 1-5 scale
- `interruptions`: Number of wake-ups
- `notes`: Optional notes
- `created_at`: Timestamp

#### `wellness_goals`
- `goal_id`: Primary key
- `student_id`: Foreign key to students
- `goal_type`: Type of goal
- `goal_description`: Goal details
- `target_value`: Goal target
- `current_value`: Current progress
- `start_date`: Goal start date
- `end_date`: Optional end date
- `status`: Active/Achieved
- `created_at`: Timestamp

#### `exercise_tracking`
- `exercise_id`: Primary key
- `student_id`: Foreign key to students
- `exercise_date`: Date of exercise
- `exercise_type`: Type of exercise
- `duration_minutes`: Duration
- `intensity`: Light/Moderate/Vigorous
- `calories_burned`: Optional calorie count
- `notes`: Optional notes
- `created_at`: Timestamp

#### `hydration_tracking`
- `hydration_id`: Primary key
- `student_id`: Foreign key to students
- `tracking_date`: Date
- `glasses_consumed`: Number of glasses
- `daily_goal`: Target glasses (default: 8)
- `created_at`: Timestamp

#### `crisis_resources`
- `resource_id`: Primary key
- `resource_name`: Resource name
- `resource_type`: Type of resource
- `contact_info`: Contact details
- `description`: Resource description
- `availability`: Hours available
- `is_active`: Active status
- `created_at`: Timestamp

Default Crisis Resources:
1. National Suicide Prevention Lifeline - 988
2. Crisis Text Line - Text HOME to 741741
3. Campus Counseling Center - 555-0100
4. Campus Security - 555-0911

#### `counseling_appointments`
- `appointment_id`: Primary key
- `student_id`: Foreign key to students
- `appointment_date`: Appointment date
- `appointment_time`: Appointment time
- `counselor_name`: Optional counselor
- `appointment_type`: Type of appointment
- `status`: Scheduled/Completed/Cancelled
- `notes`: Confidential notes
- `created_at`: Timestamp

#### `wellness_points`
- `point_id`: Primary key
- `student_id`: Foreign key to students
- `points_earned`: Points amount
- `activity_type`: Type of activity
- `activity_description`: Activity details
- `earned_date`: Date earned
- `created_at`: Timestamp

## Usage Examples

### Service Layer

```python
from university_system.modules.domain.wellness import WellnessService

service = WellnessService()
student_id = "12345"

# Log wellness check-in
checkin_id = service.create_checkin(
    student_id=student_id,
    overall_mood=7,
    stress_level=5,
    sleep_quality=8,
    energy_level=7,
    anxiety_level=4,
    notes="Feeling good today!"
)

# Log mood
mood_id = service.log_mood(
    student_id=student_id,
    mood_type="Happy",
    intensity=4,
    triggers="Good weather",
    activities="Morning walk"
)

# Track sleep
sleep_id = service.log_sleep(
    student_id=student_id,
    sleep_date="2024-01-11",
    bedtime="23:00",
    wake_time="07:00",
    hours_slept=8.0,
    sleep_quality=4,
    interruptions=1
)

# Get analytics
patterns = service.analyze_wellness_patterns(student_id, days=30)
sleep_analytics = service.get_sleep_analytics(student_id, days=30)

# Get crisis resources (no login required)
resources = service.get_crisis_resources()
```

### CLI Interface

```python
from university_system.modules.domain.wellness import WellnessCLI

cli = WellnessCLI()
cli.main_menu()  # Launches interactive CLI
```

### GUI Interface

```python
from university_system.modules.domain.wellness import WellnessGUI

app = WellnessGUI()
app.run()  # Launches Tkinter GUI
```

Or as a child window:

```python
import tkinter as tk
from university_system.modules.domain.wellness import WellnessGUI

root = tk.Tk()
wellness_gui = WellnessGUI(parent=root)
# GUI opens in new window
```

## Privacy & Security

### Confidentiality
- All counseling appointments are private and confidential
- Notes are only visible to the student and authorized counselors
- No identifying information is shared in leaderboards

### Crisis Support
- Crisis resources are always visible, even without login
- Multiple contact methods (phone, text, in-person)
- 24/7 availability clearly indicated
- Emergency instructions prominently displayed

### Data Protection
- Activity logging for compliance tracking
- Secure database storage with foreign key constraints
- Transaction safety for all database operations
- User authentication required for personal data

## Integration with University System

The wellness module integrates seamlessly with the existing university system:

- **Authentication**: Uses `infrastructure/shared_context.py` for auth
- **Database**: Uses `infrastructure/database/db.py` connection pooling
- **Activity Logging**: All actions logged via `modules/shared/utils/activity_logger.py`
- **Student Records**: Foreign key relationships to existing student table

## Running the Module

### From Main Application

The wellness module is accessible from the main university system menu.

### Standalone CLI

```bash
python -m university_system.modules.domain.wellness.cli.wellness_cli
```

### Standalone GUI

```bash
python -m university_system.modules.domain.wellness.gui.wellness_gui
```

## Testing

To verify the module is working:

```python
# Test imports
from university_system.modules.domain.wellness import WellnessService, WellnessCLI, WellnessGUI

# Test service initialization
service = WellnessService()

# Test crisis resources (no login required)
resources = service.get_crisis_resources()
print(f"Found {len(resources)} crisis resources")
```

## Future Enhancements

Potential additions:
- Meditation timer and guided sessions
- Stress management workshops calendar
- Peer support groups
- Mental health resource library
- Integration with campus health services
- Anonymous peer chat support
- Wellness challenges and competitions
- Integration with fitness trackers
- Nutrition tracking
- Study-life balance analytics

## Support

If you're experiencing a mental health crisis:
- **Call 988** - National Suicide Prevention Lifeline
- **Text HOME to 741741** - Crisis Text Line
- **Call 911** - For immediate emergencies
- **Visit Campus Counseling Center** - Free confidential support

Remember: Your mental health matters. It's okay to ask for help. 🌱

# Event Discovery Engine

A comprehensive event management and discovery system for university events with personalized recommendations, RSVP management, attendance tracking, and social features.

## Features

### Core Functionality

#### Event Management
- Create, update, and manage university events
- Support for multiple event categories:
  - Academic (lectures, seminars, workshops)
  - Social (parties, mixers, gatherings)
  - Athletic (sports events, games, competitions)
  - Cultural (performances, exhibitions, celebrations)
  - Career (job fairs, networking, workshops)
  - Community Service (volunteering, outreach)
  - Other
- Rich event details including:
  - Title, description, and category
  - Date, time, and location information
  - Building and room details
  - Capacity management
  - Registration requirements
  - Event photos and media
  - Tags for better discoverability

#### RSVP System
- Three RSVP statuses: Going, Interested, Not Going
- One-click calendar integration
- Capacity management and waitlist support
- Registration deadline enforcement
- Email reminders for upcoming events
- RSVP history tracking

#### Attendance Tracking
- QR code-based check-in system
- Time-based check-in windows (30 minutes before to event end)
- Check-in and check-out tracking
- Attendance history and analytics
- Attendance certificates (for eligible events)

#### Personalized Recommendations
Advanced recommendation engine based on:
- **User Interest Preferences**: 1-10 scale for each category
- **Attendance History**: Events you've attended in the past
- **Popularity**: What other students are attending
- **Social Connections**: Events your friends are attending (opt-in)

Scoring system:
- Interest preferences: 0-40 points
- Attendance history: 0-20 points
- Popularity: 0-20 points
- Friends attending: 0-20 points

#### Social Features
- See which friends are attending events (opt-in)
- Share events with friends
- Event photos and recaps
- Public or private attendance visibility
- Friend notifications for event RSVPs

#### Ratings and Reviews
- 5-star rating system
- Text reviews and comments
- Photo uploads from events
- Event recaps and highlights
- Average ratings and review counts

### User Interface

#### CLI Interface
Interactive command-line interface with:
- Browse upcoming events by date
- Search events by category, keyword, date
- View personalized recommendations
- RSVP to events
- Check in to events
- Rate and review attended events
- Manage interest preferences
- View personal statistics
- Create new events

#### GUI Interface
Modern graphical interface featuring:
- **Calendar View**: Interactive monthly calendar with event markers
- **Event Cards**: Rich event cards with category badges, details, and actions
- **Recommendations Panel**: "For You" section with personalized suggestions
- **Filter System**: Category filters and keyword search
- **Event Details**: Full-screen event information with reviews and photos
- **RSVP Dialog**: Easy one-click RSVP with calendar integration
- **Interest Manager**: Visual slider-based preference settings
- **Statistics Dashboard**: Personal event analytics and insights

Color-coded categories and visual indicators for better UX.

## Database Schema

### Tables

#### events
Stores all event information:
- `event_id`: Primary key
- `title`, `description`, `category`
- `start_datetime`, `end_datetime`
- `location`, `building`, `room`
- `organizer_id`, `organizer_name`, `organizer_type`
- `max_capacity`, `registration_required`, `registration_deadline`
- `event_image_url`, `tags`
- `created_at`, `updated_at`, `cancelled`

#### event_rsvps
Tracks user RSVPs:
- `rsvp_id`: Primary key
- `event_id`, `user_id`
- `rsvp_status`: Going, Interested, Not Going
- `rsvp_date`
- `added_to_calendar`, `reminder_sent`

#### event_attendance
Records event check-ins:
- `attendance_id`: Primary key
- `event_id`, `user_id`
- `check_in_time`, `check_out_time`

#### event_interests
User category preferences:
- `interest_id`: Primary key
- `user_id`, `category`
- `interest_level`: 1-10 scale

#### event_photos
Event photos and media:
- `photo_id`: Primary key
- `event_id`, `user_id`
- `photo_url`, `caption`
- `uploaded_at`

#### event_ratings
Event reviews and ratings:
- `rating_id`: Primary key
- `event_id`, `user_id`
- `rating`: 1-5 stars
- `review`: Text review
- `rated_at`

#### event_social_settings
User privacy preferences:
- `user_id`: Primary key
- `show_attendance_to_friends`
- `receive_friend_notifications`

### Indexes
Optimized indexes for:
- Event datetime queries
- Category filtering
- User RSVP lookups
- Attendance tracking

## Usage

### Service Layer

```python
from university_system.modules.domain.events.services.events_service import get_events_service

# Initialize service
service = get_events_service()

# Create an event
event_data = {
    'title': 'Welcome Week Orientation',
    'description': 'Join us for orientation!',
    'category': 'Academic',
    'start_datetime': '2026-02-01 10:00',
    'end_datetime': '2026-02-01 12:00',
    'location': 'Student Center',
    'building': 'Main Campus',
    'room': 'Auditorium A',
    'max_capacity': 200,
    'organizer_name': 'Student Affairs'
}
event_id = service.create_event(event_data, 'admin_user')

# Search events
events = service.search_events(
    category='Academic',
    keyword='orientation',
    upcoming_only=True
)

# RSVP to event
service.rsvp_to_event(
    event_id=event_id,
    user_id='student123',
    status='Going',
    add_to_calendar=True
)

# Check in to event
service.check_in_to_event(event_id=event_id, user_id='student123')

# Set interest preferences
service.set_interest_preference('student123', 'Academic', 8)
service.set_interest_preference('student123', 'Social', 9)

# Get personalized recommendations
recommendations = service.get_personalized_recommendations(
    user_id='student123',
    limit=10
)

# Rate event
service.rate_event(
    event_id=event_id,
    user_id='student123',
    rating=5,
    review='Great event! Very informative.'
)

# Get statistics
stats = service.get_user_statistics('student123')
print(f"Total RSVPs: {stats['total_rsvps']}")
print(f"Events Attended: {stats['total_attended']}")
```

### CLI Interface

```python
from university_system.modules.domain.events.cli.events_cli import EventsCLI

# Run CLI
cli = EventsCLI()
cli.run()
```

Or from command line:
```bash
python -m university_system.modules.domain.events.cli.events_cli
```

### GUI Interface

```python
import tkinter as tk
from university_system.modules.domain.events.gui.events_gui import EventsGUI

# Create main window
root = tk.Tk()
root.title("Event Discovery Engine")
root.geometry("1400x800")

# Initialize GUI
app = EventsGUI(root)

# Run
root.mainloop()
```

## Architecture

### Service Layer (`services/events_service.py`)
- **EventsService**: Main service class with all business logic
- Singleton pattern for database connection management
- Comprehensive error handling and validation
- Activity logging for audit trail
- Transaction safety for all write operations

### CLI Interface (`cli/events_cli.py`)
- **EventsCLI**: Command-line interface class
- Menu-driven navigation
- Input validation and error handling
- Formatted output with color coding
- Date and time formatting utilities

### GUI Interface (`gui/events_gui.py`)
- **EventsGUI**: Tkinter-based graphical interface
- Three-panel layout: Calendar/Filters, Events, Recommendations
- Event cards with rich visual design
- Color-coded categories
- Interactive calendar with event markers
- Responsive design with scrolling

## API Reference

### EventsService Methods

#### Event Management
- `create_event(event_data, user_id)`: Create new event
- `get_event(event_id)`: Get event details
- `update_event(event_id, event_data, user_id)`: Update event
- `cancel_event(event_id, user_id)`: Cancel event
- `search_events(category, start_date, end_date, keyword, upcoming_only)`: Search events
- `get_upcoming_events(limit)`: Get upcoming events

#### RSVP Management
- `rsvp_to_event(event_id, user_id, status, add_to_calendar)`: RSVP to event
- `get_user_rsvps(user_id, upcoming_only)`: Get user's RSVPs
- `cancel_rsvp(event_id, user_id)`: Cancel RSVP

#### Attendance Tracking
- `check_in_to_event(event_id, user_id)`: Check in
- `check_out_from_event(event_id, user_id)`: Check out
- `get_event_attendance(event_id)`: Get attendance list
- `get_user_attendance_history(user_id)`: Get user's attendance history

#### Preferences & Recommendations
- `set_interest_preference(user_id, category, interest_level)`: Set interest
- `get_user_interests(user_id)`: Get interests
- `get_personalized_recommendations(user_id, limit)`: Get recommendations

#### Ratings & Reviews
- `rate_event(event_id, user_id, rating, review)`: Rate event
- `get_event_reviews(event_id)`: Get reviews

#### Photos
- `upload_event_photo(event_id, user_id, photo_url, caption)`: Upload photo
- `get_event_photos(event_id)`: Get photos

#### Social Features
- `set_social_settings(user_id, show_attendance, receive_notifications)`: Set privacy
- `get_friends_attending(event_id, user_id)`: Get friends attending

#### Analytics
- `get_event_statistics(event_id)`: Get event stats
- `get_user_statistics(user_id)`: Get user stats

## Configuration

### Environment Variables
None required - uses centralized database configuration.

### Database
- Uses main university database: `data/db_files/student_records.db`
- Auto-creates tables on first run
- Indexes created automatically for performance

## Security & Privacy

### Access Control
- User authentication required for all operations
- Activity logging for audit trail
- Permission checks for event creation and management

### Privacy Features
- Opt-in social features
- Attendance visibility controls
- Friend notification preferences
- Anonymous ratings option

### Data Protection
- Parameterized queries prevent SQL injection
- Transaction safety for data integrity
- Input validation and sanitization
- Secure user ID handling

## Performance Optimization

### Database
- Indexed columns for fast queries
- Efficient JOIN operations
- Connection pooling
- Query result caching

### Recommendations Engine
- Optimized scoring algorithm
- Pre-calculated user preferences
- Batch processing for multiple users
- Result limiting for performance

### GUI
- Lazy loading for event lists
- Virtual scrolling for large lists
- Event caching
- Asynchronous updates

## Future Enhancements

### Planned Features
- [ ] QR code generation for check-ins
- [ ] Email reminder system
- [ ] iCal/Google Calendar export
- [ ] Event livestreaming support
- [ ] Push notifications
- [ ] Advanced analytics dashboard
- [ ] Event series/recurring events
- [ ] Waitlist management
- [ ] Event collaboration tools
- [ ] Mobile app integration

### Integration Opportunities
- Social matching system for friend connections
- Campus navigation for event locations
- Notification system for reminders
- Student marketplace for event-related items
- Academic calendar integration

## Testing

Run tests:
```bash
# Test service layer
python -m pytest university_system/tests/test_events_service.py -v

# Test CLI
python -m pytest university_system/tests/test_events_cli.py -v

# Test GUI
python -m pytest university_system/tests/test_events_gui.py -v
```

## Troubleshooting

### Common Issues

**Events not appearing in calendar**
- Check date filter settings
- Verify event is not cancelled
- Ensure proper date format (YYYY-MM-DD HH:MM)

**Recommendations not showing**
- Set interest preferences first
- Attend some events to build history
- Check that upcoming events exist

**Check-in failing**
- Verify event is currently happening
- Check-in window: 30 min before to event end
- Ensure you have RSVP'd

**Rating not allowed**
- Must have attended event to rate
- Check attendance history
- Verify event has ended

## Contributing

When adding features:
1. Update database schema in `initialize_database()`
2. Add service methods with proper error handling
3. Update CLI menu and commands
4. Add GUI interface elements
5. Update this README
6. Add tests for new functionality

## License

Part of the University Management System v5.0.0

## Support

For issues or questions:
- Check documentation in `docs/modules/events/`
- Review code comments and docstrings
- Contact development team

---

**Version**: 1.0.0
**Last Updated**: 2026-01-11
**Maintainer**: University IT Department

# Feedback & Suggestion Box Module

A comprehensive, community-focused feedback and suggestion system for the University Management System.

## Overview

The Feedback & Suggestion Box module provides a transparent platform for students, faculty, and staff to:
- Submit anonymous or attributed feedback
- Propose suggestions that can be voted on by the community
- Track the status of submissions from submission to implementation
- View administrative responses and impact metrics
- Participate in university decision-making

## Features

### Core Features
- **Anonymous Feedback**: Submit feedback without revealing identity
- **Public Suggestion Board**: Browse and vote on community suggestions
- **Upvoting System**: Community-driven prioritization through voting
- **Status Tracking**: Full transparency on submission lifecycle
- **Administrative Responses**: Direct feedback from administrators
- **Impact Metrics**: Track real-world impact of implemented suggestions
- **Multi-Category Support**: Academic, Housing, Dining, Technology, Campus Life, Safety, Other

### Status Lifecycle
1. **Submitted** - New submission awaiting review
2. **Under Review** - Being evaluated by administrators
3. **Planned** - Approved and scheduled for implementation
4. **In Progress** - Currently being implemented
5. **Implemented** - Successfully completed with impact data
6. **Declined** - Not approved with explanation

### Database Schema

The module uses 7 interconnected tables:

1. **feedback_categories** - Submission categories
2. **feedback_submissions** - Main feedback/suggestion records
3. **feedback_votes** - User votes on submissions
4. **feedback_responses** - Administrative responses
5. **feedback_status_updates** - Status change history
6. **feedback_impacts** - Impact metrics for implemented ideas
7. **feedback_attachments** - File attachments (future use)

## Architecture

```
feedback/
├── services/
│   └── feedback_service.py     # Core service layer (884 lines)
├── cli/
│   └── feedback_cli.py         # CLI interface (729 lines)
├── gui/
│   └── feedback_gui.py         # GUI interface (1116 lines)
└── __init__.py                 # Module exports
```

## Usage

### Service Layer

```python
from university_system.modules.domain.feedback import FeedbackService

service = FeedbackService()

# Submit a suggestion
suggestion_id = service.submit_suggestion(
    user_id='student123',
    category='Dining',
    title='Add vegan options',
    description='More vegan meal choices needed',
    is_anonymous=False
)

# Upvote a suggestion
service.upvote_submission(suggestion_id, 'student456')

# Get trending suggestions
trending = service.get_trending_suggestions(limit=10)

# Add administrative response
service.add_response(
    submission_id=suggestion_id,
    responder_id='admin001',
    responder_name='Dean Smith',
    response_text='Great idea! We will discuss with dining services.'
)

# Update status
service.update_status(
    submission_id=suggestion_id,
    new_status='Under Review',
    updated_by='Dean Smith',
    notes='Meeting scheduled with dining team'
)

# Add impact data when implemented
service.add_impact_data(
    submission_id=suggestion_id,
    implementation_date='2024-09-01',
    users_affected=1500,
    satisfaction_increase=15.5,
    cost_savings=0,
    description='Added 5 new vegan options to daily menu'
)
```

### CLI Interface

```bash
# Run the CLI
python -m university_system.modules.domain.feedback.cli.feedback_cli

# Or from within the main CLI
# Select: Student Services > Feedback & Suggestions
```

CLI Features:
- Submit feedback (private)
- Submit suggestion (public, votable)
- Browse suggestions with filters
- View trending suggestions
- Search submissions
- Track your submissions
- View implemented suggestions
- Admin functions (respond, update status, add impact data)

### GUI Interface

```python
from university_system.modules.domain.feedback.gui import FeedbackGUI

# Standalone
app = FeedbackGUI()
app.run()

# Or as part of main GUI
# From the main menu, select "Feedback & Suggestions"
```

GUI Features:
- **Browse Tab**: Filter by category/status, sort by votes/date
- **Trending Tab**: Most popular suggestions with activity
- **Submit New Tab**: Easy form for feedback/suggestions
- **My Submissions Tab**: Track your submissions and responses
- **Implemented Tab**: Success stories with impact metrics
- **Statistics Tab**: System-wide statistics
- **Admin Tab**: Management functions (admin only)

## API Reference

### FeedbackService Methods

#### Submission Management
- `submit_feedback(user_id, category, title, description, is_anonymous, feedback_type)` → int
- `submit_suggestion(user_id, category, title, description, is_anonymous)` → int
- `delete_submission(submission_id, user_id)` → bool

#### Voting
- `upvote_submission(submission_id, user_id)` → bool
- `remove_vote(submission_id, user_id)` → bool
- `has_user_voted(submission_id, user_id)` → bool
- `get_user_votes(user_id)` → List[int]

#### Retrieval
- `get_submissions(type, category, status, user_id, sort_by, limit, offset)` → List[Dict]
- `get_submission_details(submission_id)` → Dict
- `get_trending_suggestions(limit)` → List[Dict]
- `get_implemented_suggestions(limit)` → List[Dict]
- `get_user_submissions(user_id)` → List[Dict]
- `search_submissions(search_term, limit)` → List[Dict]

#### Administrative
- `add_response(submission_id, responder_id, responder_name, response_text)` → int
- `update_status(submission_id, new_status, updated_by, notes)` → bool
- `add_impact_data(submission_id, impl_date, users_affected, satisfaction, cost_savings, desc)` → int

#### Utilities
- `get_categories()` → List[Dict]
- `get_statistics()` → Dict

## Configuration

### Categories
Default categories (configurable in `_initialize_categories`):
- 📚 Academic - Course content, teaching quality, curriculum
- 🏠 Housing - Dormitories, apartments, maintenance
- 🍽️ Dining - Cafeteria, meal plans, food quality
- 💻 Technology - IT services, WiFi, software, computers
- 🎉 Campus Life - Events, clubs, activities, facilities
- 🔒 Safety - Security, emergency services, lighting
- 💡 Other - General feedback and suggestions

### Status Options
- Submitted (default)
- Under Review
- Planned
- In Progress
- Implemented
- Declined

### Priority Levels
- Low
- Normal (default)
- High
- Critical

## Database Tables

### feedback_submissions
Main table for all submissions
- `id` - Primary key
- `user_id` - Submitter (NULL if anonymous)
- `category_id` - Foreign key to categories
- `type` - 'feedback' or 'suggestion'
- `title` - Brief summary
- `description` - Detailed description
- `is_anonymous` - Boolean flag
- `status` - Current status
- `priority` - Priority level
- `votes` - Vote count (denormalized for performance)
- `created_at`, `updated_at` - Timestamps

### feedback_votes
Vote tracking with uniqueness constraint
- `id` - Primary key
- `submission_id` - Foreign key to submissions
- `user_id` - Voter ID
- `vote_type` - 'upvote' or 'downvote' (currently only upvote used)
- `created_at` - Timestamp
- UNIQUE constraint on (submission_id, user_id)

### feedback_responses
Administrative responses
- `id` - Primary key
- `submission_id` - Foreign key
- `responder_id` - Admin ID
- `responder_name` - Display name
- `response_text` - Message content
- `created_at` - Timestamp

### feedback_status_updates
Full audit trail of status changes
- `id` - Primary key
- `submission_id` - Foreign key
- `old_status`, `new_status` - Status transition
- `updated_by` - Who made the change
- `notes` - Optional explanation
- `created_at` - Timestamp

### feedback_impacts
Impact metrics for implemented suggestions
- `id` - Primary key
- `submission_id` - Foreign key
- `implementation_date` - When implemented
- `users_affected` - Number of users impacted
- `satisfaction_increase` - Percentage increase
- `cost_savings` - Dollar amount saved
- `description` - Impact summary
- `metrics` - Additional JSON data

## Performance Optimizations

- **Indexed columns**: status, category, votes, user_id
- **Denormalized vote count**: Cached in submissions table
- **Connection pooling**: Efficient database access
- **Cascading deletes**: Automatic cleanup of related records

## Security Features

- **SQL injection prevention**: Parameterized queries throughout
- **Anonymous protection**: User IDs nullified when anonymous
- **Vote uniqueness**: Database constraint prevents duplicate votes
- **Transaction safety**: ACID compliance for all modifications
- **Activity logging**: Comprehensive audit trail

## Integration Points

### Activity Logging
All data modifications are logged via `activity_logger`:
- Submission creation
- Vote additions/removals
- Status updates
- Response additions
- Impact data recording

### Authentication
Uses `shared_context.get_auth()` for:
- User identification
- Permission checking
- Anonymous vs. attributed submissions

### Database
Uses centralized database layer:
- `get_connection()` for read operations
- `transaction()` for write operations
- Automatic connection pooling

## Examples

### Example 1: Student Submits Suggestion
```python
# Student logs in
service = FeedbackService()

# Submit suggestion
suggestion_id = service.submit_suggestion(
    user_id='stu_12345',
    category='Campus Life',
    title='Create a student lounge in Building A',
    description='Building A lacks common areas for students to relax between classes.',
    is_anonymous=False
)
# Returns: 42
```

### Example 2: Community Votes
```python
# Other students upvote
service.upvote_submission(42, 'stu_67890')  # Vote 1
service.upvote_submission(42, 'stu_11111')  # Vote 2
service.upvote_submission(42, 'stu_22222')  # Vote 3

# Check vote count
details = service.get_submission_details(42)
print(details['votes'])  # 3
```

### Example 3: Admin Responds
```python
# Administrator reviews trending suggestions
trending = service.get_trending_suggestions(limit=10)

# Respond to top suggestion
service.add_response(
    submission_id=42,
    responder_id='adm_001',
    responder_name='Facilities Director',
    response_text='Excellent suggestion! We have space available and will include this in the next budget proposal.'
)

# Update status
service.update_status(
    submission_id=42,
    new_status='Planned',
    updated_by='Facilities Director',
    notes='Scheduled for Fall 2024 renovation'
)
```

### Example 4: Implementation & Impact
```python
# After implementation
service.update_status(42, 'Implemented', 'Facilities Director')

# Add impact data
service.add_impact_data(
    submission_id=42,
    implementation_date='2024-09-15',
    users_affected=800,
    satisfaction_increase=22.5,
    cost_savings=0,
    description='New lounge with seating for 40, study tables, and vending machines. Student satisfaction with facilities increased significantly.'
)

# Now visible in "Implemented" tab with impact metrics
```

## Testing

Run syntax validation:
```bash
python3 -m py_compile university_system/modules/domain/feedback/services/feedback_service.py
python3 -m py_compile university_system/modules/domain/feedback/cli/feedback_cli.py
python3 -m py_compile university_system/modules/domain/feedback/gui/feedback_gui.py
```

Manual testing:
1. Run CLI: `python -m university_system.modules.domain.feedback.cli.feedback_cli`
2. Submit several suggestions with different categories
3. Upvote suggestions as different users
4. Add admin responses and status updates
5. View trending and implemented tabs
6. Test search functionality

## Future Enhancements

- **File attachments**: Upload images/documents with submissions
- **Email notifications**: Alert users when status changes or responses added
- **Downvoting**: Allow community to indicate low priority
- **Categories management**: Dynamic category creation by admins
- **Analytics dashboard**: Visualizations of submission trends
- **Export functionality**: Download reports in PDF/CSV
- **Mobile app integration**: REST API endpoints
- **Gamification**: Badges for active contributors and implemented suggestions

## File Locations

- Service: `/home/seancatchpole989/university_system/modules/domain/feedback/services/feedback_service.py`
- CLI: `/home/seancatchpole989/university_system/modules/domain/feedback/cli/feedback_cli.py`
- GUI: `/home/seancatchpole989/university_system/modules/domain/feedback/gui/feedback_gui.py`

## License

Part of the University Management System v5.0.0

## Support

For issues or questions, submit feedback through the system itself or contact the development team.

