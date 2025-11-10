#!/usr/bin/env python3
"""
Demo script to showcase the new enhanced console output utility
"""

from university_system.modules.shared.utils.console_output import console

def demo_basic_messages():
    """Demonstrate basic message types"""
    console.header("Basic Message Types Demo", width=70)

    console.success("Operation completed successfully!")
    console.error("An error occurred during processing")
    console.warning("This is a warning message")
    console.info("Here's some informational text")
    console.debug("Debug information for developers")

    print()

def demo_formatted_output():
    """Demonstrate formatted output"""
    console.header("Formatted Output Demo", width=70)

    # Section divider
    console.section("Database Connection Status")
    console.status("Database", "Connected", success=True)
    console.status("Connection Pool", "5/10 connections", success=True)
    console.status("Cache Hit Rate", "87.3%", success=True)

    # Box message
    print()
    console.box("Important Notice:\n\nAll systems are operational.\nDatabase backup completed at 14:30.")

    # Key-value list
    data = {
        "Total Students": "1,247",
        "Active Courses": "156",
        "Faculty Members": "89",
        "Departments": "12"
    }
    console.key_value_list(data, title="System Statistics")

def demo_tables():
    """Demonstrate table output"""
    console.header("Table Output Demo", width=70)

    # Simple data table
    headers = ["ID", "Name", "Course", "Grade", "Status"]
    rows = [
        ["12345", "John Doe", "CS101", "A", "Enrolled"],
        ["12346", "Jane Smith", "CS102", "B+", "Enrolled"],
        ["12347", "Bob Johnson", "CS103", "A-", "Enrolled"],
        ["12348", "Alice Brown", "CS101", "B", "Enrolled"],
        ["12349", "Charlie Davis", "CS102", "A", "Completed"]
    ]

    console.table(headers, rows, title="Student Enrollment Records")

    print()

    # Simple table (no borders)
    console.simple_table(headers, rows[:3], title="Quick View")

def demo_progress():
    """Demonstrate progress indicators"""
    console.header("Progress Indicators Demo", width=70)

    import time

    total = 50
    for i in range(total + 1):
        console.progress(i, total, label="Processing records")
        time.sleep(0.02)  # Simulate work

    print()

def demo_interactive():
    """Demonstrate interactive elements"""
    console.header("Interactive Elements Demo", width=70)

    # Menu
    console.menu("Main Menu", [
        "View Student Records",
        "Search Database",
        "Generate Reports",
        "System Settings",
        "Exit"
    ])

    # List items
    console.list_items([
        "Database initialization complete",
        "User authentication enabled",
        "Email notifications configured",
        "Backup system active"
    ], title="System Status", bullet="✓")

    print()

def demo_banner():
    """Demonstrate banner"""
    console.banner("Advanced Search System v5.0", width=70, style="double")

    # Summary box
    stats = {
        "Searches Today": "1,234",
        "Active Users": "89",
        "Cache Hit Rate": "92.5%",
        "Avg Response Time": "0.23s"
    }
    console.summary("Daily Statistics", stats, width=60)

def main():
    """Run all demos"""
    console.banner("Console Output Utility Demo", width=70, style="bold")

    demo_basic_messages()
    demo_formatted_output()
    demo_tables()
    demo_progress()
    demo_interactive()
    demo_banner()

    console.divider(width=70)
    console.success("Demo completed successfully!")
    console.divider(width=70)

if __name__ == "__main__":
    main()
