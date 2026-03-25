"""Advanced chart types and interactive visualizations."""

import os
from datetime import datetime

from education_system.university_system.modules.shared.services.analytics.enhanced_reporting._compat import (
    pd, np, plt, sns, go, px, pyo,
    Paragraph, getSampleStyleSheet, ParagraphStyle, Table, TableStyle, colors,
)
from education_system.university_system.modules.shared.services.analytics.enhanced_reporting.config import CONFIG, get_reporting_db_connection, logger


class AdvancedVisualization:
    """Advanced chart types and interactive visualizations"""

    @staticmethod
    def create_heatmap(data, title, x_col, y_col, value_col):
        """Create a heatmap visualization"""
        plt.figure(figsize=(12, 8))

        # Pivot data for heatmap
        pivot_data = data.pivot(index=y_col, columns=x_col, values=value_col)

        sns.heatmap(pivot_data, annot=True, cmap='YlOrRd', fmt='.1f')
        plt.title(title)
        plt.tight_layout()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"heatmap_{timestamp}.png"
        filepath = os.path.join(CONFIG['reports_dir'], filename)
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close()

        return filepath

    @staticmethod
    def create_interactive_dashboard(data_dict):
        """Create an interactive Plotly dashboard"""
        from plotly.subplots import make_subplots

        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('Course Distribution', 'Age Distribution', 'Registration Trends', 'Module Popularity'),
            specs=[[{"type": "pie"}, {"type": "bar"}],
                   [{"type": "scatter"}, {"type": "bar"}]]
        )

        # Course distribution pie chart
        if 'course_distribution' in data_dict:
            course_data = data_dict['course_distribution']
            fig.add_trace(
                go.Pie(labels=course_data['course'], values=course_data['student_count'], name="Courses"),
                row=1, col=1
            )

        # Age distribution bar chart
        if 'age_distribution' in data_dict:
            age_data = data_dict['age_distribution']
            fig.add_trace(
                go.Bar(x=age_data['age_group'], y=age_data['student_count'], name="Age Groups"),
                row=1, col=2
            )

        # Registration trends line chart
        if 'registration_trends' in data_dict:
            reg_data = data_dict['registration_trends']
            fig.add_trace(
                go.Scatter(x=reg_data['registration_date'], y=reg_data['registration_count'],
                          mode='lines+markers', name="Registrations"),
                row=2, col=1
            )

        # Module popularity bar chart
        if 'module_popularity' in data_dict:
            module_data = data_dict['module_popularity'].head(10)
            fig.add_trace(
                go.Bar(x=module_data['module_code'], y=module_data['student_count'], name="Modules"),
                row=2, col=2
            )

        fig.update_layout(height=800, showlegend=False, title_text="Student Analytics Dashboard")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"dashboard_{timestamp}.html"
        filepath = os.path.join(CONFIG['reports_dir'], filename)

        pyo.plot(fig, filename=filepath, auto_open=False)

        return filepath

    @staticmethod
    def create_correlation_matrix(conn):
        """Create correlation matrix for numeric variables"""
        # Check which attendance table exists
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='attendance_records'")

        if cursor.fetchone():
            attendance_table = 'attendance_records'
            status_column = 'status'
        else:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='student_attendance'")
            if cursor.fetchone():
                attendance_table = 'student_attendance'
                status_column = 'status'
            else:
                return None

        # Fixed query with proper table aliases
        query = f"""
        SELECT s.age,
               COUNT(sm.module_code) as module_count,
               AVG(CASE WHEN sg.grade IS NOT NULL THEN CAST(sg.grade AS FLOAT) ELSE NULL END) as avg_grade,
               COUNT(sa.student_id) as attendance_records,
               SUM(CASE WHEN sa.{status_column} = 'present' THEN 1 ELSE 0 END) as present_count
        FROM students s
        LEFT JOIN student_modules sm ON s.student_id = sm.student_id
        LEFT JOIN student_grades sg ON s.student_id = sg.student_id
        LEFT JOIN {attendance_table} sa ON s.student_id = sa.student_id
        GROUP BY s.student_id, s.age
        """

        df = pd.read_sql_query(query, conn)
        df = df.fillna(0)

        if len(df) < 2:
            return None

        # Calculate attendance rate
        df['attendance_rate'] = df.apply(
            lambda row: row['present_count'] / row['attendance_records'] if row['attendance_records'] > 0 else 0,
            axis=1
        )

        # Select numeric columns for correlation
        numeric_cols = ['age', 'module_count', 'avg_grade', 'attendance_rate']
        corr_matrix = df[numeric_cols].corr()

        plt.figure(figsize=(10, 8))
        sns.heatmap(corr_matrix, annot=True, cmap='coolwarm', center=0,
                   square=True, linewidths=0.5)
        plt.title('Student Metrics Correlation Matrix')
        plt.tight_layout()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"correlation_matrix_{timestamp}.png"
        filepath = os.path.join(CONFIG['reports_dir'], filename)
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close()

        return filepath


def create_advanced_visualization(section, df):
    """Create advanced visualizations using seaborn and plotly"""
    if section == "correlation_analysis":
        conn = get_reporting_db_connection()
        try:
            return AdvancedVisualization.create_correlation_matrix(conn)
        finally:
            conn.close()

    elif section in ["course_distribution", "gender_distribution"]:
        # Create enhanced pie chart with better styling
        plt.figure(figsize=(12, 8))

        if section == "course_distribution":
            labels = df['course']
            sizes = df['student_count']
            colors_list = plt.cm.Set3(np.linspace(0, 1, len(labels)))
        else:
            labels = df['gender']
            sizes = df['student_count']
            colors_list = ['#FF9999', '#66B2FF', '#99FF99', '#FFCC99']

        wedges, texts, autotexts = plt.pie(sizes, labels=labels, autopct='%1.1f%%',
                                          startangle=90, colors=colors_list,
                                          explode=[0.05] * len(labels))

        # Enhance text styling
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')

        plt.title(f"{section.replace('_', ' ').title()}", fontsize=16, fontweight='bold')

        # Add total count
        total = sizes.sum()
        plt.text(0, -1.3, f"Total: {total}", ha='center', fontsize=12, fontweight='bold')

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{section}_advanced_{timestamp}.png"
        filepath = os.path.join(CONFIG['reports_dir'], filename)
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close()

        return filepath

    return None


def create_interactive_chart(section, df):
    """Create interactive charts using Plotly"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{section}_interactive_{timestamp}.html"
    filepath = os.path.join(CONFIG['reports_dir'], filename)

    try:
        if section == "course_distribution":
            fig = px.pie(df, values='student_count', names='course',
                        title='Course Distribution',
                        hover_data=['student_count'])

        elif section == "registration_trends":
            fig = px.line(df, x='registration_date', y='registration_count',
                         title='Registration Trends Over Time',
                         markers=True)
            fig.update_layout(xaxis_title="Date", yaxis_title="Registrations")

        elif section == "module_popularity":
            top_modules = df.head(15)
            fig = px.bar(top_modules, x='module_code', y='student_count',
                        title='Module Popularity (Top 15)',
                        hover_data=['module_name'])
            fig.update_layout(xaxis_title="Module Code", yaxis_title="Student Count")

        else:
            return None

        fig.update_layout(
            font=dict(size=12),
            title_font_size=16,
            showlegend=True
        )

        pyo.plot(fig, filename=filepath, auto_open=False)
        return filepath

    except Exception as e:
        logger.error(f"Error creating interactive chart: {str(e)}")
        return None


def create_standard_chart(section, df):
    """Create standard charts with enhanced styling"""
    plt.style.use('seaborn-v0_8')

    if section in ["course_distribution", "gender_distribution", "age_distribution"]:
        return create_enhanced_pie_chart(df, section)
    elif section == "module_popularity":
        return create_enhanced_bar_chart(df, section)
    elif section == "registration_trends":
        return create_enhanced_line_chart(df, section)
    else:
        return None


def create_enhanced_pie_chart(df, section):
    """Create enhanced pie chart with better styling"""
    plt.figure(figsize=(10, 8))

    if section == "course_distribution":
        labels = df['course']
        sizes = df['student_count']
        title = "Course Distribution"
        chart_colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4']
    elif section == "gender_distribution":
        labels = df['gender']
        sizes = df['student_count']
        title = "Gender Distribution"
        chart_colors = ['#FF9999', '#66B2FF', '#99FF99']
    elif section == "age_distribution":
        labels = df['age_group']
        sizes = df['student_count']
        title = "Age Distribution"
        chart_colors = ['#FFB347', '#87CEEB', '#DDA0DD', '#98FB98', '#F0E68C']

    wedges, texts, autotexts = plt.pie(sizes, labels=labels, autopct='%1.1f%%',
                                      startangle=90, colors=chart_colors[:len(labels)],
                                      explode=[0.02] * len(labels), shadow=True)

    # Style the text
    for text in texts:
        text.set_fontsize(11)
        text.set_fontweight('bold')

    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontweight('bold')
        autotext.set_fontsize(10)

    plt.title(title, fontsize=16, fontweight='bold', pad=20)
    plt.axis('equal')

    # Add total count
    total = sizes.sum()
    plt.figtext(0.5, 0.02, f"Total: {total}", ha='center', fontsize=12, fontweight='bold')

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{section}_enhanced_{timestamp}.png"
    filepath = os.path.join(CONFIG['reports_dir'], filename)
    plt.savefig(filepath, dpi=300, bbox_inches='tight')
    plt.close()

    return filepath


def create_enhanced_bar_chart(df, section):
    """Create enhanced bar chart"""
    plt.figure(figsize=(14, 8))

    if section == "module_popularity":
        plot_df = df.head(12)  # Show top 12 modules

        bars = plt.bar(plot_df['module_code'], plot_df['student_count'],
                      color='steelblue', alpha=0.8, edgecolor='navy', linewidth=1)

        # Add value labels on bars
        for bar in bars:
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                    f'{int(height)}', ha='center', va='bottom', fontweight='bold')

        plt.title("Module Popularity (Top 12)", fontsize=16, fontweight='bold', pad=20)
        plt.xlabel("Module Code", fontsize=12, fontweight='bold')
        plt.ylabel("Number of Students", fontsize=12, fontweight='bold')
        plt.xticks(rotation=45, ha='right')

        # Add grid for better readability
        plt.grid(axis='y', alpha=0.3, linestyle='--')

        # Style the plot
        plt.gca().spines['top'].set_visible(False)
        plt.gca().spines['right'].set_visible(False)

        plt.tight_layout()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{section}_enhanced_{timestamp}.png"
    filepath = os.path.join(CONFIG['reports_dir'], filename)
    plt.savefig(filepath, dpi=300, bbox_inches='tight')
    plt.close()

    return filepath


def create_enhanced_line_chart(df, section):
    """Create enhanced line chart"""
    plt.figure(figsize=(14, 8))

    if section == "registration_trends":
        plt.plot(df['registration_date'], df['registration_count'],
                marker='o', linewidth=2.5, markersize=6,
                color='steelblue', markerfacecolor='orange', markeredgecolor='navy')

        # Add trend line with error handling
        try:
            if len(df) >= 2:  # Need at least 2 points for a trend line
                x_numeric = np.array(range(len(df)))
                y_numeric = np.array(df['registration_count'])

                # Check for valid data (no NaN, no infinite values)
                if not (np.isnan(y_numeric).any() or np.isinf(y_numeric).any()):
                    # Use polyfit with error handling
                    z = np.polyfit(x_numeric, y_numeric, 1)
                    p = np.poly1d(z)
                    plt.plot(df['registration_date'], p(x_numeric), "--",
                            color='red', alpha=0.8, linewidth=2, label='Trend')
        except (np.linalg.LinAlgError, ValueError) as e:
            # If polyfit fails (SVD convergence, etc.), skip the trend line
            logger.warning(f"Could not generate trend line for registration_trends: {e}")

        plt.title("Registration Trends Over Time", fontsize=16, fontweight='bold', pad=20)
        plt.xlabel("Date", fontsize=12, fontweight='bold')
        plt.ylabel("Number of Registrations", fontsize=12, fontweight='bold')
        plt.xticks(rotation=45)

        # Add grid
        plt.grid(True, alpha=0.3, linestyle='--')

        # Style the plot
        plt.gca().spines['top'].set_visible(False)
        plt.gca().spines['right'].set_visible(False)

        # Add legend if trend line was added
        if plt.gca().get_legend_handles_labels()[0]:
            plt.legend()

        plt.tight_layout()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{section}_enhanced_{timestamp}.png"
    filepath = os.path.join(CONFIG['reports_dir'], filename)
    plt.savefig(filepath, dpi=300, bbox_inches='tight')
    plt.close()

    return filepath


def generate_statistical_summary(df, section):
    """Generate statistical summary for numeric data"""
    styles = getSampleStyleSheet()

    if section == "grade_distribution" and 'grade' in df.columns:
        # Convert grades to numeric
        numeric_grades = pd.to_numeric(df['grade'], errors='coerce').dropna()

        if len(numeric_grades) > 0:
            stats = {
                'Mean': f"{numeric_grades.mean():.2f}",
                'Median': f"{numeric_grades.median():.2f}",
                'Std Dev': f"{numeric_grades.std():.2f}",
                'Min': f"{numeric_grades.min():.2f}",
                'Max': f"{numeric_grades.max():.2f}",
                'Count': f"{len(numeric_grades)}"
            }

            stats_text = " | ".join([f"{k}: {v}" for k, v in stats.items()])
            return Paragraph(stats_text, styles["Normal"])

    return None


def create_enhanced_data_table(df):
    """Create enhanced data table with better styling"""
    # Limit columns and rows for readability
    display_df = df.head(50)  # Show max 50 rows

    if len(df.columns) > 6:
        # Show only first 6 columns if too many
        display_df = display_df.iloc[:, :6]

    # Prepare data for table
    data = [display_df.columns.tolist()]
    for _, row in display_df.iterrows():
        formatted_row = []
        for value in row:
            if pd.isna(value):
                formatted_row.append("N/A")
            elif isinstance(value, float):
                formatted_row.append(f"{value:.2f}")
            else:
                formatted_row.append(str(value))
        data.append(formatted_row)

    # Create table with enhanced styling
    table = Table(data)
    table.setStyle(TableStyle([
        # Header styling
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),

        # Data styling
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),

        # Alternating row colors
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
    ]))

    return table
