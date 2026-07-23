from datetime import datetime
import numpy as np

from education_system.post_18.university_system.infrastructure.database.db import get_connection

from education_system.post_18.university_system.modules.domain.finance.reporting.financial_reports import _common
from education_system.post_18.university_system.modules.domain.finance.reporting.financial_reports._common import get_current_academic_year


def scenario_planning_tools():
    """Advanced scenario planning and what-if analysis"""
    import matplotlib.pyplot as plt
    auth = _common.auth

    if not auth or not auth.current_user:
        print("You must be logged in to access scenario planning tools.")
        return

    if not auth.check_permission('manage_finances'):
        print("You don't have permission to access scenario planning tools.")
        return

    print("\nFinancial Scenario Planning & What-If Analysis")
    print("=" * 60)

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get baseline data
        cursor.execute('''
        SELECT
            SUM(sf.amount) as total_expected,
            SUM(CASE WHEN sf.status = 'paid' THEN sf.amount ELSE 0 END) as total_collected,
            COUNT(DISTINCT sf.student_id) as student_count
        FROM student_fees sf
        JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
        WHERE ft.academic_year = ?
        ''', (get_current_academic_year(),))

        baseline = cursor.fetchone()
        baseline_expected = baseline[0] or 0
        baseline_collected = baseline[1] or 0
        baseline_students = baseline[2] or 0
        baseline_rate = (baseline_collected / baseline_expected * 100) if baseline_expected > 0 else 0

        print("Baseline Scenario (Current):")
        print(f"  Students: {baseline_students}")
        print(f"  Expected Revenue: £{baseline_expected:,.2f}")
        print(f"  Current Collection: £{baseline_collected:,.2f} ({baseline_rate:.1f}%)")

        # Scenario 1: Fee increase
        fee_increase_scenarios = [0.05, 0.10, 0.15, 0.20]  # 5%, 10%, 15%, 20%

        print("\nScenario 1: Fee Increase Impact")
        print("-" * 40)

        for increase in fee_increase_scenarios:
            # Assume some student dropout due to fee increase
            dropout_rate = increase * 0.5  # 50% of fee increase as dropout rate
            adjusted_students = int(baseline_students * (1 - dropout_rate))
            adjusted_expected = baseline_expected * (1 + increase) * (adjusted_students / baseline_students)

            # Assume collection rate might decrease slightly due to affordability
            adjusted_collection_rate = baseline_rate * (1 - increase * 0.1)
            adjusted_collected = adjusted_expected * (adjusted_collection_rate / 100)

            print(f"  {increase:.0%} increase: {adjusted_students} students, "
                  f"£{adjusted_collected:,.2f} collected ({adjusted_collection_rate:.1f}% rate)")

        # Scenario 2: Economic downturn impact
        downturn_scenarios = ['mild', 'moderate', 'severe']
        downturn_impacts = {
            'mild': {'collection_rate_impact': -5, 'enrollment_impact': -10, 'payment_delay': 15},
            'moderate': {'collection_rate_impact': -15, 'enrollment_impact': -20, 'payment_delay': 30},
            'severe': {'collection_rate_impact': -25, 'enrollment_impact': -35, 'payment_delay': 60}
        }

        print("\nScenario 2: Economic Downturn Impact")
        print("-" * 40)

        for scenario_name, impacts in downturn_impacts.items():
            adjusted_students = int(baseline_students * (1 + impacts['enrollment_impact']/100))
            adjusted_rate = baseline_rate + impacts['collection_rate_impact']
            adjusted_expected = baseline_expected * (adjusted_students / baseline_students)
            adjusted_collected = adjusted_expected * (adjusted_rate / 100)

            print(f"  {scenario_name.title()} downturn: {adjusted_students} students, "
                  f"£{adjusted_collected:,.2f} collected ({adjusted_rate:.1f}% rate)")

        # Scenario 3: Scholarship program expansion
        scholarship_scenarios = [0.10, 0.20, 0.30]  # 10%, 20%, 30% more scholarships

        print("\nScenario 3: Scholarship Program Expansion")
        print("-" * 40)

        for scholarship_increase in scholarship_scenarios:
            # More scholarships might attract more students but reduce net revenue
            enrollment_boost = scholarship_increase * 1.2  # 20% more effective than cost
            adjusted_students = int(baseline_students * (1 + enrollment_boost))

            # Reduce per-student revenue due to scholarships
            per_student_revenue = (baseline_expected / baseline_students) * (1 - scholarship_increase * 0.7)
            adjusted_expected = per_student_revenue * adjusted_students

            # Better collection rate due to affordability
            adjusted_rate = min(100, baseline_rate * (1 + scholarship_increase * 0.1))
            adjusted_collected = adjusted_expected * (adjusted_rate / 100)

            print(f"  {scholarship_increase:.0%} more scholarships: {adjusted_students} students, "
                  f"£{adjusted_collected:,.2f} collected ({adjusted_rate:.1f}% rate)")

        # Scenario 4: Payment plan optimization
        payment_plan_scenarios = ['basic', 'flexible', 'comprehensive']
        plan_impacts = {
            'basic': {'collection_improvement': 5, 'admin_cost': 1000},
            'flexible': {'collection_improvement': 12, 'admin_cost': 3000},
            'comprehensive': {'collection_improvement': 20, 'admin_cost': 8000}
        }

        print("\nScenario 4: Payment Plan Optimization")
        print("-" * 40)

        for plan_name, impacts in plan_impacts.items():
            improved_rate = min(100, baseline_rate + impacts['collection_improvement'])
            improved_collected = baseline_expected * (improved_rate / 100)
            net_benefit = (improved_collected - baseline_collected) - impacts['admin_cost']

            print(f"  {plan_name.title()} plan: {improved_rate:.1f}% collection rate, "
                  f"£{net_benefit:,.2f} net benefit")

        # Create scenario comparison visualization
        scenarios = ['Baseline', '10% Fee Increase', 'Mild Downturn', '20% More Scholarships', 'Flexible Payment Plans']

        # Calculate values for visualization
        scenario_values = [
            baseline_collected,
            baseline_expected * 1.10 * 0.95 * 0.97,  # Fee increase scenario
            baseline_expected * 0.8 * 0.8,  # Mild downturn
            baseline_expected * 1.24 * 0.86 * 1.02,  # Scholarship expansion
            baseline_expected * 1.12  # Payment plan optimization
        ]

        plt.figure(figsize=(12, 8))

        plt.subplot(2, 2, 1)
        colors = ['blue', 'green', 'red', 'orange', 'purple']
        plt.bar(scenarios, scenario_values, color=colors)
        plt.title('Revenue Collection by Scenario')
        plt.ylabel('Revenue (£)')
        plt.xticks(rotation=45)

        # ROI comparison for interventions
        intervention_costs = [0, 5000, -20000, -50000, 3000]  # Costs/savings
        # Fixed the list comprehension syntax
        intervention_benefits = [0] + [s - baseline_collected for s in scenario_values[1:]]

        plt.subplot(2, 2, 2)
        net_benefits = [b - c for b, c in zip(intervention_benefits, intervention_costs)]
        plt.bar(scenarios, net_benefits, color=colors)
        plt.title('Net Benefit by Scenario')
        plt.ylabel('Net Benefit (£)')
        plt.xticks(rotation=45)

        # Risk vs Return scatter
        plt.subplot(2, 2, 3)
        risks = [0, 15, 35, 25, 10]  # Risk scores (0-100)
        returns = [(v/baseline_collected - 1) * 100 for v in scenario_values]

        plt.scatter(risks, returns, s=100, c=colors)
        for i, scenario in enumerate(scenarios):
            plt.annotate(scenario.split()[0], (risks[i], returns[i]),
                        xytext=(5, 5), textcoords='offset points')
        plt.xlabel('Risk Score')
        plt.ylabel('Return (%)')
        plt.title('Risk vs Return Analysis')

        # Timeline impact
        plt.subplot(2, 2, 4)
        months = list(range(1, 13))
        baseline_monthly = [baseline_collected/12] * 12

        # Show cumulative impact over time for best scenario
        best_scenario_monthly = [scenario_values[4]/12] * 12
        cumulative_baseline = np.cumsum(baseline_monthly)
        cumulative_best = np.cumsum(best_scenario_monthly)

        plt.plot(months, cumulative_baseline, label='Baseline', linewidth=2)
        plt.plot(months, cumulative_best, label='Flexible Payment Plans', linewidth=2)
        plt.xlabel('Month')
        plt.ylabel('Cumulative Revenue (£)')
        plt.title('12-Month Impact Projection')
        plt.legend()

        plt.tight_layout()
        plt.savefig('scenario_planning_analysis.png', dpi=300, bbox_inches='tight')
        plt.close()

        print("\nScenario planning analysis chart saved as 'scenario_planning_analysis.png'")

        # Generate recommendations
        print("\nScenario Planning Recommendations:")
        print("-" * 40)
        print("1. Flexible Payment Plans show highest ROI with lowest risk")
        print("2. Fee increases require careful balance with enrollment impact")
        print("3. Scholarship expansion needs targeted approach to maximize enrollment")
        print("4. Economic downturn preparation should focus on collection efficiency")
        print("5. Consider implementing multiple low-risk strategies simultaneously")

        conn.close()

    except Exception as e:
        print(f"Error in scenario planning: {e}")
