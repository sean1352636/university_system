"""Chart builder functions for the enhanced reporting GUI."""

from education_system.post_18.university_system.modules.shared.gui.enhanced_reporting.standalone.constants import (
    logging, os, pd, datetime,
    paths, get_db_connection,
    ENHANCED_AVAILABLE,
    logger,
)


def create_advanced_visualization(section, df):
    """Create advanced visualization for section"""
    try:
        if not ENHANCED_AVAILABLE or df is None or df.empty:
            return None

        import matplotlib.pyplot as plt
        import seaborn as sns

        plt.style.use('seaborn-v0_8')
        fig, ax = plt.subplots(figsize=(12, 8))

        if section == 'course_distribution':
            colors = plt.cm.Set3(range(len(df)))
            bars = ax.bar(df.iloc[:, 0], df.iloc[:, 1], color=colors)
            ax.set_title('Course Distribution', fontsize=16, fontweight='bold')
            ax.set_xlabel('Course', fontsize=12)
            ax.set_ylabel('Student Count', fontsize=12)

            # Add value labels on bars
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{int(height)}', ha='center', va='bottom')

        elif section == 'gender_distribution':
            colors = ['#FF9999', '#66B2FF', '#99FF99']
            wedges, texts, autotexts = ax.pie(df.iloc[:, 1], labels=df.iloc[:, 0],
                                            autopct='%1.1f%%', colors=colors,
                                            startangle=90)
            ax.set_title('Gender Distribution', fontsize=16, fontweight='bold')

        elif section == 'age_distribution':
            sns.barplot(data=df, x=df.columns[0], y=df.columns[1], ax=ax, palette='viridis')
            ax.set_title('Age Distribution', fontsize=16, fontweight='bold')
            ax.set_xlabel('Age Group', fontsize=12)
            ax.set_ylabel('Count', fontsize=12)

        elif section == 'registration_trends':
            ax.plot(pd.to_datetime(df.iloc[:, 0]), df.iloc[:, 1],
                   marker='o', linewidth=2, markersize=6)
            ax.set_title('Registration Trends', fontsize=16, fontweight='bold')
            ax.set_xlabel('Date', fontsize=12)
            ax.set_ylabel('Registrations', fontsize=12)
            plt.xticks(rotation=45)

        plt.tight_layout()

        # Save chart
        chart_path = paths.CHARTS_DIR / f"{section}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        os.makedirs(os.path.dirname(chart_path), exist_ok=True)
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        plt.close()

        return chart_path

    except Exception as e:
        logging.error(f"Error creating visualization for {section}: {str(e)}")
        return None

def create_interactive_chart(section, df):
    """Create interactive chart using plotly"""
    try:
        if not df.empty:
            import plotly.graph_objects as go
            import plotly.express as px

            if section == 'course_distribution':
                fig = px.bar(df, x=df.columns[0], y=df.columns[1],
                           title='Interactive Course Distribution')
            elif section == 'gender_distribution':
                fig = px.pie(df, values=df.columns[1], names=df.columns[0],
                           title='Interactive Gender Distribution')
            elif section == 'registration_trends':
                fig = px.line(df, x=df.columns[0], y=df.columns[1],
                            title='Interactive Registration Trends')
            else:
                fig = px.bar(df, x=df.columns[0], y=df.columns[1])

            # Save as HTML
            chart_path = paths.CHARTS_DIR / f"{section}_interactive_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            os.makedirs(os.path.dirname(chart_path), exist_ok=True)
            fig.write_html(chart_path)
            return chart_path

    except ImportError:
        logging.warning("Plotly not available for interactive charts")
    except Exception as e:
        logging.error(f"Error creating interactive chart: {str(e)}")

    return None

def create_standard_chart(section, df):
    """Create standard matplotlib chart"""
    try:
        return create_advanced_visualization(section, df)
    except Exception as e:
        logging.error(f"Error creating standard chart: {str(e)}")
        return None

def create_enhanced_pie_chart(df, section):
    """Create enhanced pie chart"""
    try:
        import matplotlib.pyplot as plt

        if df.empty or len(df.columns) < 2:
            return None

        fig, ax = plt.subplots(figsize=(10, 8))

        # Use the first column as labels, second as values
        labels = df.iloc[:, 0].tolist()
        sizes = df.iloc[:, 1].tolist()

        # Color palette
        colors = plt.cm.Set3(range(len(labels)))

        # Create pie chart
        wedges, texts, autotexts = ax.pie(sizes, labels=labels, autopct='%1.1f%%',
                                        startangle=90, colors=colors,
                                        textprops={'fontsize': 10})

        # Enhance appearance
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')

        ax.set_title(f'Enhanced {section.replace("_", " ").title()}',
                    fontsize=14, fontweight='bold', pad=20)

        plt.tight_layout()

        # Save chart
        chart_path = paths.CHARTS_DIR / f"{section}_pie_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        os.makedirs(os.path.dirname(chart_path), exist_ok=True)
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        plt.close()

        return chart_path

    except Exception as e:
        logging.error(f"Error creating enhanced pie chart: {str(e)}")
        return None

def create_enhanced_bar_chart(df, section):
    """Create enhanced bar chart"""
    try:
        import matplotlib.pyplot as plt
        import seaborn as sns

        if df.empty or len(df.columns) < 2:
            return None

        plt.style.use('default')
        fig, ax = plt.subplots(figsize=(12, 8))

        # Use seaborn for better styling
        sns.barplot(data=df, x=df.columns[0], y=df.columns[1], ax=ax, palette='viridis')

        # Customize appearance
        ax.set_title(f'Enhanced {section.replace("_", " ").title()}',
                    fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel(df.columns[0].replace('_', ' ').title(), fontsize=12)
        ax.set_ylabel(df.columns[1].replace('_', ' ').title(), fontsize=12)

        # Add value labels on bars
        for i, bar in enumerate(ax.patches):
            height = bar.get_height()
            if not pd.isna(height):
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{int(height)}', ha='center', va='bottom', fontsize=10)

        # Rotate x-axis labels if needed
        if len(df) > 5:
            plt.xticks(rotation=45, ha='right')

        plt.tight_layout()

        # Save chart
        chart_path = paths.CHARTS_DIR / f"{section}_bar_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        os.makedirs(os.path.dirname(chart_path), exist_ok=True)
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        plt.close()

        return chart_path

    except Exception as e:
        logging.error(f"Error creating enhanced bar chart: {str(e)}")
        return None

def create_enhanced_line_chart(df, section):
    """Create enhanced line chart"""
    try:
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates

        if df.empty or len(df.columns) < 2:
            return None

        fig, ax = plt.subplots(figsize=(12, 8))

        # Convert first column to datetime if it looks like dates
        x_data = df.iloc[:, 0]
        y_data = df.iloc[:, 1]

        try:
            x_data = pd.to_datetime(x_data)
            ax.plot(x_data, y_data, marker='o', linewidth=2.5, markersize=6,
                   color='#1f77b4', markerfacecolor='#ff7f0e')
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(df)//10)))
            plt.xticks(rotation=45)
        except Exception:
            ax.plot(x_data, y_data, marker='o', linewidth=2.5, markersize=6,
                   color='#1f77b4', markerfacecolor='#ff7f0e')

        # Customize appearance
        ax.set_title(f'Enhanced {section.replace("_", " ").title()}',
                    fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel(df.columns[0].replace('_', ' ').title(), fontsize=12)
        ax.set_ylabel(df.columns[1].replace('_', ' ').title(), fontsize=12)

        # Add grid
        ax.grid(True, alpha=0.3)

        # Add trend line if more than 3 points
        if len(df) > 3:
            try:
                from numpy.polynomial.polynomial import Polynomial
                x_numeric = range(len(y_data))
                p = Polynomial.fit(x_numeric, y_data, deg=1)
                trend_y = p(x_numeric)
                ax.plot(x_data, trend_y, '--', color='red', alpha=0.7,
                       linewidth=2, label='Trend')
                ax.legend()
            except Exception as e:
                logger.debug(f"Failed to add legend to chart: {e}")

        plt.tight_layout()

        # Save chart
        chart_path = paths.CHARTS_DIR / f"{section}_line_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        os.makedirs(os.path.dirname(chart_path), exist_ok=True)
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        plt.close()

        return chart_path

    except Exception as e:
        logging.error(f"Error creating enhanced line chart: {str(e)}")
        return None

def generate_statistical_summary(df, section):
    """Generate statistical summary for dataframe"""
    try:
        if df.empty:
            return "No data available for statistical analysis"

        summary = f"Statistical Summary for {section.replace('_', ' ').title()}:\n\n"

        # Basic info
        summary += f"Total Records: {len(df)}\n"
        summary += f"Columns: {len(df.columns)}\n\n"

        # Numeric columns analysis
        numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns
        if len(numeric_cols) > 0:
            summary += "Numeric Analysis:\n"
            for col in numeric_cols:
                col_data = df[col].dropna()
                if len(col_data) > 0:
                    summary += f"  {col}:\n"
                    summary += f"    Mean: {col_data.mean():.2f}\n"
                    summary += f"    Median: {col_data.median():.2f}\n"
                    summary += f"    Std Dev: {col_data.std():.2f}\n"
                    summary += f"    Min: {col_data.min()}\n"
                    summary += f"    Max: {col_data.max()}\n\n"

        # Categorical columns analysis
        categorical_cols = df.select_dtypes(include=['object']).columns
        if len(categorical_cols) > 0:
            summary += "Categorical Analysis:\n"
            for col in categorical_cols[:3]:  # Limit to first 3 columns
                col_data = df[col].dropna()
                if len(col_data) > 0:
                    summary += f"  {col}:\n"
                    summary += f"    Unique Values: {col_data.nunique()}\n"
                    top_values = col_data.value_counts().head(3)
                    summary += f"    Top Values: {dict(top_values)}\n\n"

        return summary

    except Exception as e:
        logging.error(f"Error generating statistical summary: {str(e)}")
        return f"Error generating statistical summary: {str(e)}"

def create_enhanced_data_table(df):
    """Create enhanced HTML data table"""
    try:
        if df.empty:
            return "<p>No data available</p>"

        # Limit rows for display
        display_df = df.head(100)

        # Convert to HTML with styling
        html_table = display_df.to_html(classes='enhanced-table',
                                       table_id='data-table',
                                       escape=False,
                                       index=False)

        # Add CSS styling
        enhanced_html = f"""
        <style>
        .enhanced-table {{
            border-collapse: collapse;
            margin: 25px 0;
            font-size: 0.9em;
            font-family: sans-serif;
            min-width: 400px;
            box-shadow: 0 0 20px rgba(0, 0, 0, 0.15);
            width: 100%;
        }}
        .enhanced-table thead tr {{
            background-color: #009879;
            color: #ffffff;
            text-align: left;
        }}
        .enhanced-table th,
        .enhanced-table td {{
            padding: 12px 15px;
            border: 1px solid #dddddd;
        }}
        .enhanced-table tbody tr {{
            border-bottom: 1px solid #dddddd;
        }}
        .enhanced-table tbody tr:nth-of-type(even) {{
            background-color: #f3f3f3;
        }}
        .enhanced-table tbody tr:hover {{
            background-color: #f1f1f1;
        }}
        </style>
        {html_table}
        """

        if len(df) > 100:
            enhanced_html += f"<p><em>Showing first 100 of {len(df)} records</em></p>"

        return enhanced_html

    except Exception as e:
        logging.error(f"Error creating enhanced data table: {str(e)}")
        return f"<p>Error creating data table: {str(e)}</p>"
