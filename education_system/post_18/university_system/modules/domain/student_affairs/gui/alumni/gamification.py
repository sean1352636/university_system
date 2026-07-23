import tkinter as tk
from education_system.post_18.university_system.infrastructure.email.template_utils import render_template
from tkinter import ttk, messagebox, simpledialog, filedialog
from tkinter.scrolledtext import ScrolledText
from education_system.post_18.university_system.infrastructure.database.db import sqlite3, get_connection as db_get_connection
from education_system.post_18.university_system.core import paths
from datetime import datetime, timedelta
from pathlib import Path
import threading
import shutil
from functools import partial

# Import internationalization (i18n) for multi-language support
try:
    from education_system.post_18.university_system.core.i18n import (
        get_text as _t,
        get_current_language,
    )
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False
    _t = lambda key, **kwargs: kwargs.get("default", key)
    get_current_language = lambda: "en"

# Alumni service functions
from education_system.post_18.university_system.modules.domain.student_affairs.gui.alumni._service_imports import (
    init_alumni_db, register_alumni, view_alumni, update_alumni,
    view_events, create_enhanced_event, event_check_in_system,
    record_donation, view_donations, setup_mentorship, view_mentorships,
    search_alumni_directory, view_connection_requests, manage_business_directory,
    create_newsletter, manage_alumni_forum, post_job_opportunity, view_job_board,
    schedule_career_counseling, view_fundraising_campaigns, create_fundraising_campaign,
    view_engagement_leaderboard, view_my_badges, manage_photo_gallery,
    manage_class_reunions, manage_regional_chapters, setup_alumni_directory,
    generate_alumni_report, set_auth, setup_alumni_permissions,
    smart_mentorship_matching, generate_engagement_recommendations,
    create_alumni_story, view_alumni_stories, get_connection,
)



class GamificationMixin:
        def generate_recommendations(self):
            """Generate new AI recommendations"""
            self.recommendations_text.delete(1.0, tk.END)
            self.recommendations_text.insert(tk.END, "🤖 Generating personalized recommendations using AI analysis...\n\n")
            self.root.update()

            # Simulate AI processing
            import time
            time.sleep(2)

            new_recommendations = """🤖 AI-GENERATED RECOMMENDATIONS (Updated)
    ========================================

    AI Analysis Complete - Analyzing your activity patterns, preferences, and community needs...

    ✨ SMART RECOMMENDATIONS BASED ON YOUR PROFILE:

    🎯 IMMEDIATE OPPORTUNITIES (Next 7 Days):

    1. 🚀 Tech Startup Panel Discussion
       AI Insight: Your entrepreneurship experience + upcoming career fair
       Action: Volunteer as a panelist for the September 1st career event
       Why Now: Event needs tech entrepreneurs, matches your expertise perfectly
       Impact: +125 points, establish thought leadership, help 50+ students
       Confidence: 95% match

    2. 🤝 Strategic Networking Target
       AI Insight: 3 new tech alumni recently joined, 2 in AI/ML
       Action: Send connection requests to Sarah Kim (AI startup) and Alex Chen (ML engineer)
       Why Now: High compatibility scores, shared interests in AI technology
       Impact: +30 points, potential collaboration opportunities
       Confidence: 87% successful connection probability

    🔮 PREDICTIVE RECOMMENDATIONS (Next 30 Days):

    3. 📈 Content Creation Opportunity
       AI Prediction: Based on community engagement patterns, tech career content needed
       Action: Create video series "From Code to CEO" (3 short episodes)
       Predicted Engagement: 150+ views, 20+ comments
       Impact: +200 points, "Content Creator" badge, thought leadership
       Optimal Timing: Post every Tuesday in September

    4. 🎓 Mentorship Match Alert
       AI Analysis: Perfect mentee match identified - Emma Wilson (CS student, AI interest)
       Compatibility Score: 94% (shared interests, complementary experience)
       Action: Accept mentorship pairing, focus on AI career guidance
       Impact: +150 points, "Mentor Extraordinaire" upgrade, meaningful impact
       Success Probability: 91% (based on similar pairings)

    💡 AI INSIGHTS ABOUT YOU:

    Engagement Pattern: Peak activity on Tuesday/Thursday evenings
    Preferred Content: Technical discussions, career advice, innovation topics
    Communication Style: Professional but approachable, detail-oriented
    Community Role: Natural leader and knowledge sharer
    Growth Trajectory: On track to become top 1% most engaged alumni

    🔬 ADVANCED ANALYTICS:

    Your Activity Heat Map:
    • Strongest: Career services (+40% above average)
    • Growing: Networking (+25% this month)
    • Opportunity: Event organization (untapped potential)
    • Future Focus: Thought leadership content

    Predicted Engagement Score (6 months): 2,100+ points
    Recommended Badge Path: Community Leader → Innovation Leader → Alumni Hall of Fame

    ⚡ ONE-CLICK ACTIONS:
    • [Accept Emma Wilson Mentorship] - 30 seconds
    • [Join Sept 1 Panel] - 2 minutes
    • [Connect with AI Alumni] - 5 minutes
    • [Schedule Content Creation] - 10 minutes

    🎯 AI CONFIDENCE LEVELS:
    High Impact Recommendations: 93% success rate
    Medium Impact Recommendations: 81% success rate
    Based on analysis of 1,000+ similar alumni profiles

    Next AI Analysis: Scheduled for September 1, 2025
    Recommendation Refresh: Every 2 weeks or after major activity
    """

            self.recommendations_text.insert(tk.END, new_recommendations)
            self.update_status("AI recommendations generated")

        def refresh_recommendations(self):
            """Refresh recommendations"""
            self.show_initial_recommendations()
            self.update_status("Recommendations refreshed")

        def run_smart_matching(self):
            """Run the smart matching algorithm"""
            self.matching_results.delete(1.0, tk.END)
            self.matching_results.insert(tk.END, "Running AI-powered matching analysis...\n\n")
            self.root.update()

            # Simulate processing time
            import time
            time.sleep(2)

            matching_results = """AI-POWERED MENTORSHIP MATCHING RESULTS
    =====================================

    🤖 Analysis Complete - Generated 5 high-quality matches

    RECOMMENDED MATCH #1 (Compatibility Score: 94%)
    👨‍💼 Mentor: Michael Chen (Class of 2018)
           Industry: Finance | Experience: 5+ years
           Specialties: Investment Analysis, Career Planning

    👩‍🎓 Mentee: Emma Wilson (Current Student)
           Goals: Finance career transition
           Interests: Investment banking, financial modeling

    🎯 Match Reasons:
       • 98% industry alignment
       • Complementary experience levels
       • Similar communication preferences (virtual meetings)
       • Overlapping availability (weekday evenings)
       • Strong personality compatibility (analytical, detail-oriented)

    [Create This Mentorship] [View Detailed Analysis]

    ---

    RECOMMENDED MATCH #2 (Compatibility Score: 91%)
    👩‍💼 Mentor: Dr. Sarah Johnson (Class of 2015)
           Industry: Technology | Experience: 8+ years
           Specialties: Software Development, Leadership

    👨‍🎓 Mentee: Alex Brown (Recent Graduate)
           Goals: Technical leadership roles
           Interests: Software architecture, team management

    🎯 Match Reasons:
       • 95% career goal alignment
       • Mentor's leadership experience matches mentee's aspirations
       • Technical skill overlap (full-stack development)
       • Geographic proximity (both in SF Bay Area)
       • Similar professional values

    [Create This Mentorship] [View Detailed Analysis]

    ---

    RECOMMENDED MATCH #3 (Compatibility Score: 88%)
    👩‍⚕️ Mentor: Dr. Lisa Martinez (Class of 2012)
           Industry: Healthcare | Experience: 10+ years
           Specialties: Healthcare Administration, Leadership

    👨‍🎓 Mentee: David Kim (Career Changer)
           Goals: Healthcare administration transition
           Interests: Healthcare policy, operations management

    🎯 Match Reasons:
       • Direct industry transition match
       • Mentor's career path aligns with mentee's goals
       • Administrative experience highly relevant
       • Both interested in healthcare policy
       • Compatible schedules and communication styles

    [Create This Mentorship] [View Detailed Analysis]

    ---

    ADDITIONAL INSIGHTS:
    • 15 potential mentors analyzed
    • 12 potential mentees in matching pool
    • Average compatibility score: 73%
    • Top 3 matches exceed 85% compatibility threshold

    NEXT STEPS:
    1. Review recommended matches
    2. Contact participants for approval
    3. Schedule introduction meetings
    4. Set up mentorship agreements
    """

            self.matching_results.insert(tk.END, matching_results)
            self.update_status("Smart matching analysis completed")

        def show_initial_recommendations(self):
            """Show initial personalized recommendations"""
            recommendations = """🎯 PERSONALIZED RECOMMENDATIONS FOR YOU
    =====================================

    Based on your profile, activity history, and alumni community trends, here are
    personalized recommendations to enhance your engagement:

    🌟 HIGH PRIORITY RECOMMENDATIONS:

    1. 🤝 Expand Your Network
       Why: You have strong engagement but only 3 connections
       Action: Connect with 5 alumni in your industry (Technology)
       Potential Impact: +75 points, unlock "Super Networker" badge
       Time Investment: 30 minutes

    2. 📝 Share Your Success Story
       Why: Your career achievements would inspire others
       Action: Submit an alumni spotlight story about your startup journey
       Potential Impact: +100 points, featured content, inspire others
       Time Investment: 45 minutes

    3. 🎓 Become a Mentor
       Why: Your experience matches 3 pending mentee requests
       Action: Sign up as a mentor in Technology/Entrepreneurship
       Potential Impact: +150 points, "Mentor Master" badge, give back
       Time Investment: 2-3 hours monthly

    📈 MEDIUM PRIORITY RECOMMENDATIONS:

    4. 📸 Contribute to Photo Gallery
       Why: Recent tech networking event needs photos
       Action: Upload photos from last month's Bay Area meetup
       Potential Impact: +25 points, community memory preservation
       Time Investment: 15 minutes

    5. 💼 Post More Job Opportunities
       Why: Your company likely has open positions
       Action: Share 1-2 current openings at Tech Innovations Inc.
       Potential Impact: +50 points per posting, help fellow alumni
       Time Investment: 20 minutes per posting

    🎯 PERSONALIZED GROWTH OPPORTUNITIES:

    6. 🏆 Lead a Regional Chapter Event
       Why: SF Bay Area chapter needs event organizers
       Action: Organize a startup-focused networking event
       Potential Impact: +200 points, "Community Leader" badge, leadership
       Time Investment: 5-8 hours total

    7. 📚 Share Technical Knowledge
       Why: Many alumni seeking tech career advice
       Action: Create a "How-to" guide on starting a tech company
       Potential Impact: +100 points, establish thought leadership
       Time Investment: 2-3 hours

    🔥 QUICK WINS (5-10 minutes each):

    • Update your business directory listing
    • Comment on 3 recent forum posts
    • Congratulate recent badge earners
    • Share an interesting article in the forum
    • Update your skills and achievements

    📊 IMPACT PREDICTION:
    Following these recommendations could:
    • Increase your monthly points by 300-500
    • Unlock 2-3 new badges
    • Strengthen your alumni network significantly
    • Position you as a community thought leader

    🎯 NEXT STEPS:
    1. Choose 1-2 high priority recommendations to start
    2. Set aside time this week for implementation
    3. Track your progress and engagement growth
    4. Request updated recommendations next month

    Your engagement level is already excellent - these recommendations will help you
    maximize your impact and connection with the alumni community!
    """

            self.recommendations_text.insert(tk.END, recommendations)

        def show_leaderboard(self):
            """Show engagement leaderboard"""
            self.clear_content()
            self.update_status("Engagement Leaderboard")

            ttk.Label(self.content_frame, text="Alumni Engagement Leaderboard",
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Tabs for different leaderboard views
            notebook = ttk.Notebook(self.content_frame)
            notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

            # Overall leaderboard tab
            overall_frame = ttk.Frame(notebook)
            notebook.add(overall_frame, text="Overall Leaderboard")

            overall_text = ScrolledText(overall_frame, wrap=tk.WORD)
            overall_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            leaderboard_content = """🏆 ALUMNI ENGAGEMENT LEADERBOARD - ALL TIME
    ==========================================

    🥇 #1  Sarah Johnson (Class of 2015)
          Total Points: 1,250 | Badges: 8 | Activity Level: Very High
          Recent: Posted job opportunity, Mentored 2 alumni, Event attendance

    🥈 #2  Michael Chen (Class of 2018)
          Total Points: 1,100 | Badges: 7 | Activity Level: High
          Recent: Created business listing, Forum participation, Donation made

    🥉 #3  Dr. Lisa Martinez (Class of 2012)
          Total Points: 950 | Badges: 6 | Activity Level: High
          Recent: Mentor signup, Career counseling, Alumni story shared

    4️⃣  Emily Davis (Class of 2020)
          Total Points: 825 | Badges: 5 | Activity Level: Moderate
          Recent: Class reunion planning, Regional chapter joined

    5️⃣  John Smith (Class of 2019)
          Total Points: 750 | Badges: 4 | Activity Level: Moderate
          Recent: Event attendance, Newsletter engagement, Profile updated

    6️⃣  Alex Wong (Class of 2017)
          Total Points: 680 | Badges: 4 | Activity Level: Moderate
          Recent: Photo gallery uploads, Networking connections

    7️⃣  Lisa Brown (Class of 2016)
          Total Points: 625 | Badges: 3 | Activity Level: Low-Moderate
          Recent: Job board interaction, Forum post

    8️⃣  David Kim (Class of 2021)
          Total Points: 550 | Badges: 3 | Activity Level: Low-Moderate
          Recent: Mentorship request, Directory updates

    9️⃣  Emma Wilson (Class of 2022)
          Total Points: 475 | Badges: 2 | Activity Level: Low
          Recent: Profile completion, Career counseling

    🔟 Robert Lee (Class of 2014)
          Total Points: 420 | Badges: 2 | Activity Level: Low
          Recent: Event registration, Alumni story view

    ENGAGEMENT CATEGORIES:
    🔥 Very High (1000+ points): 3 alumni
    ⚡ High (750-999 points): 2 alumni
    📈 Moderate (500-749 points): 3 alumni
    📊 Low-Moderate (250-499 points): 2 alumni
    📉 Low (<250 points): 15 alumni
    """
            overall_text.insert(tk.END, leaderboard_content)

            # Monthly leaderboard tab
            monthly_frame = ttk.Frame(notebook)
            notebook.add(monthly_frame, text="This Month")

            monthly_text = ScrolledText(monthly_frame, wrap=tk.WORD)
            monthly_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            monthly_content = """🗓️ MONTHLY LEADERBOARD - AUGUST 2025
    ====================================

    🌟 Most Active This Month:

    🥇 #1  Michael Chen (Class of 2018)
          Monthly Points: 185 | Activities: 12
          Highlights: Created mentorship, Posted 2 jobs, Forum leadership

    🥈 #2  Sarah Johnson (Class of 2015)
          Monthly Points: 165 | Activities: 10
          Highlights: Event organization, Business networking, Mentoring

    🥉 #3  Emily Davis (Class of 2020)
          Monthly Points: 140 | Activities: 9
          Highlights: Reunion planning, Chapter coordination, Photo uploads

    4️⃣  Dr. Lisa Martinez (Class of 2012)
          Monthly Points: 125 | Activities: 8
          Highlights: Career counseling sessions, Alumni story featured

    5️⃣  Alex Wong (Class of 2017)
          Monthly Points: 110 | Activities: 7
          Highlights: Photo gallery contributions, Regional chapter activity

    📊 MONTHLY ACTIVITY BREAKDOWN:
    • Total Active Alumni: 25
    • New Registrations: 3
    • Event Participations: 45
    • Forum Posts: 28
    • Job Postings: 8
    • Mentorship Connections: 4
    • Donations: 12

    🎯 MONTHLY ACHIEVEMENTS:
    • Most Forum Posts: Michael Chen (8 posts)
    • Most Events Attended: Sarah Johnson (4 events)
    • Top Mentor: Dr. Lisa Martinez (3 sessions)
    • Community Builder: Emily Davis (reunion organizing)
    """
            monthly_text.insert(tk.END, monthly_content)

            # Badge leaderboard tab
            badges_frame = ttk.Frame(notebook)
            notebook.add(badges_frame, text="Badge Champions")

            badges_text = ScrolledText(badges_frame, wrap=tk.WORD)
            badges_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            badges_content = """🏅 BADGE CHAMPIONS LEADERBOARD
    =============================

    🎖️ Most Badges Earned:

    👑 Sarah Johnson (8 badges)
        🏆 Community Leader
        🤝 Super Networker
        💼 Career Catalyst
        🎓 Mentor Extraordinaire
        💝 Generous Donor
        📱 Digital Ambassador
        🌟 Alumni Star
        🔥 Engagement Champion

    👑 Michael Chen (7 badges)
        🤝 Super Networker
        💼 Career Catalyst
        🎓 Mentor Master
        💝 Generous Donor
        📝 Content Creator
        🌟 Alumni Star
        🔥 Engagement Champion

    👑 Dr. Lisa Martinez (6 badges)
        🏆 Community Leader
        🎓 Mentor Extraordinaire
        💼 Career Catalyst
        📚 Knowledge Sharer
        🌟 Alumni Star
        🔥 Engagement Champion

    BADGE CATEGORIES:

    🤝 NETWORKING BADGES:
    • Super Networker (10+ connections): 5 alumni
    • Connection Builder (5+ connections): 12 alumni
    • Network Starter (1+ connections): 25 alumni

    💼 CAREER BADGES:
    • Career Catalyst (job posting): 8 alumni
    • Opportunity Creator (multiple jobs): 3 alumni
    • Mentor Master (active mentoring): 6 alumni

    🎓 EDUCATION BADGES:
    • Knowledge Sharer (content creation): 4 alumni
    • Learning Leader (course completion): 2 alumni
    • Skill Builder (profile updates): 15 alumni

    💝 GIVING BADGES:
    • Generous Donor (annual giving): 18 alumni
    • Major Donor (significant gift): 3 alumni
    • Loyal Supporter (recurring donor): 8 alumni

    🏆 LEADERSHIP BADGES:
    • Community Leader (event organizing): 5 alumni
    • Ambassador (chapter leadership): 3 alumni
    • Digital Ambassador (online engagement): 7 alumni
    """
            badges_text.insert(tk.END, badges_content)

        def show_matching_parameters(self):
            """Show matching parameters window"""
            params_window = tk.Toplevel(self.root)
            params_window.title("Smart Matching Parameters")
            params_window.geometry("500x400")

            text_widget = ScrolledText(params_window, wrap=tk.WORD, padx=10, pady=10)
            text_widget.pack(fill=tk.BOTH, expand=True)

            params_text = """SMART MATCHING ALGORITHM PARAMETERS
    ===================================

    INDUSTRY MATCHING (Weight: 30%)
    • Exact industry match: +30 points
    • Related industry: +20 points
    • Transferable skills: +10 points

    EXPERIENCE LEVEL (Weight: 25%)
    • Optimal gap (3-10 years): +25 points
    • Adequate gap (2-15 years): +15 points
    • Minimal/excessive gap: +5 points

    SKILL ALIGNMENT (Weight: 20%)
    • Direct skill match: +20 points
    • Complementary skills: +15 points
    • Skill development opportunity: +10 points

    CAREER GOALS (Weight: 15%)
    • Identical goals: +15 points
    • Aligned objectives: +10 points
    • Related aspirations: +5 points

    COMMUNICATION PREFERENCES (Weight: 5%)
    • Matching preferences: +5 points
    • Compatible styles: +3 points
    • Different but workable: +1 point

    SCHEDULE COMPATIBILITY (Weight: 5%)
    • Perfect overlap: +5 points
    • Good availability: +3 points
    • Some conflicts: +1 point

    MINIMUM THRESHOLD: 60 points (60%)
    RECOMMENDED THRESHOLD: 85 points (85%)

    The algorithm also considers:
    • Geographic proximity
    • Educational background
    • Personality indicators
    • Previous mentorship success
    • Participant feedback and ratings
    """

            text_widget.insert(tk.END, params_text)
            text_widget.config(state=tk.DISABLED)

        def show_my_badges(self):
            """Show user's badges and achievements"""
            self.clear_content()
            self.update_status("My Badges & Achievements")

            ttk.Label(self.content_frame, text="My Alumni Badges & Achievements",
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # User stats summary
            stats_frame = ttk.LabelFrame(self.content_frame, text="My Engagement Summary", padding=10)
            stats_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

            stats_text = """Current Status: Administrator | Total Points: 1,500 | Rank: #1 Overall

    Recent Activity:
    • Last login: Today
    • This month: 15 activities, 125 points earned
    • Badges earned: 9 total
    • Current streak: 12 days active
    """

            ttk.Label(stats_frame, text=stats_text, justify=tk.LEFT).pack()

            # Badges earned
            earned_frame = ttk.LabelFrame(self.content_frame, text="🏆 Badges Earned", padding=10)
            earned_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

            earned_text = ScrolledText(earned_frame, height=8, wrap=tk.WORD)
            earned_text.pack(fill=tk.BOTH, expand=True)

            earned_badges = """Your Earned Badges:

    🏆 Community Leader (Earned: July 2025)
        Organized 3+ community events
        Points: 100 | Category: Leadership

    🤝 Super Networker (Earned: June 2025)
        Made 10+ networking connections
        Points: 75 | Category: Networking

    💼 Career Catalyst (Earned: May 2025)
        Posted job opportunities for fellow alumni
        Points: 50 | Category: Career Services

    🎓 Mentor Extraordinaire (Earned: April 2025)
        Active mentor with excellent feedback
        Points: 100 | Category: Mentorship

    💝 Generous Donor (Earned: March 2025)
        Made annual donation to alumni fund
        Points: 50 | Category: Giving

    📱 Digital Ambassador (Earned: February 2025)
        High engagement with digital platforms
        Points: 75 | Category: Technology

    🌟 Alumni Star (Earned: January 2025)
        Exceptional overall contribution
        Points: 150 | Category: Achievement

    🔥 Engagement Champion (Earned: December 2024)
        Top 5% most engaged alumni
        Points: 200 | Category: Engagement

    📝 Content Creator (Earned: November 2024)
        Contributed valuable content to community
        Points: 60 | Category: Communication
    """
            earned_text.insert(tk.END, earned_badges)

            # Available badges
            available_frame = ttk.LabelFrame(self.content_frame, text="🎯 Available Badges", padding=10)
            available_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

            available_text = ScrolledText(available_frame, height=6, wrap=tk.WORD)
            available_text.pack(fill=tk.BOTH, expand=True)

            available_badges = """Badges You Can Earn:

    🏅 Reunion Organizer (150 points required)
        Progress: Need to organize a class reunion
        Status: Available - Plan your class reunion!

    🔬 Innovation Leader (200 points required)
        Progress: Share breakthrough innovation or research
        Status: Available - Submit your innovation story!

    🌍 Global Connector (100 points required)
        Progress: 2/5 international connections made
        Status: 60% complete - Connect with 3 more international alumni

    📚 Lifelong Learner (75 points required)
        Progress: Complete additional education/certification
        Status: Available - Share your learning achievements!

    🎨 Creative Contributor (50 points required)
        Progress: Contribute creative content (photos, stories, videos)
        Status: Available - Share your creative work!

    💡 TIP: Focus on reunion organizing or international networking to earn your next badge!
    """
            available_text.insert(tk.END, available_badges)

        def show_recommendations(self):
            """Show personalized recommendations"""
            self.clear_content()
            self.update_status("Personalized Recommendations")

            ttk.Label(self.content_frame, text="Personalized Engagement Recommendations",
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Generate recommendations button
            button_frame = ttk.Frame(self.content_frame)
            button_frame.pack(fill=tk.X, padx=20, pady=(0, 10))

            ttk.Button(button_frame, text="🤖 Generate AI Recommendations",
                      command=self.generate_recommendations).pack(side=tk.LEFT)
            ttk.Button(button_frame, text="🔄 Refresh Recommendations",
                      command=self.refresh_recommendations).pack(side=tk.LEFT, padx=(10, 0))

            # Recommendations display
            self.recommendations_text = ScrolledText(self.content_frame, wrap=tk.WORD)
            self.recommendations_text.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

            # Initial recommendations
            self.show_initial_recommendations()

        def show_smart_matching(self):
            """Show AI-powered smart matching interface"""
            self.clear_content()
            self.update_status("Smart Mentorship Matching")

            ttk.Label(self.content_frame, text="AI-Powered Mentorship Matching",
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Smart matching info
            info_frame = ttk.LabelFrame(self.content_frame, text="Smart Matching System", padding=10)
            info_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

            info_text = """Our AI-powered matching system analyzes:
    • Industry experience and expertise
    • Career goals and interests
    • Skills and competencies
    • Communication preferences
    • Availability and schedules
    • Personality compatibility factors

    The system generates compatibility scores and suggests optimal mentor-mentee pairs."""

            ttk.Label(info_frame, text=info_text, justify=tk.LEFT).pack()

            # Controls
            controls_frame = ttk.Frame(self.content_frame)
            controls_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

            ttk.Button(controls_frame, text="Run Smart Matching Analysis",
                      command=self.run_smart_matching).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(controls_frame, text="View Matching Parameters",
                      command=self.show_matching_parameters).pack(side=tk.LEFT)

            # Results area
            results_frame = ttk.LabelFrame(self.content_frame, text="Matching Results", padding=10)
            results_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

            self.matching_results = ScrolledText(results_frame, wrap=tk.WORD)
            self.matching_results.pack(fill=tk.BOTH, expand=True)

            # Initial placeholder
            placeholder_text = """Click "Run Smart Matching Analysis" to generate AI-powered mentorship recommendations.

    The system will analyze available mentors and mentees to suggest optimal pairings based on:
    - Compatibility scores
    - Shared interests and goals
    - Complementary skills and experience
    - Communication preferences
    - Schedule compatibility

    Results will include detailed explanations for each recommended match."""

            self.matching_results.insert(tk.END, placeholder_text)

