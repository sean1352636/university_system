import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

from .config import CONFIG


class PredictiveMixin:
    def predictive_analytics(self):
        """Perform predictive analytics using machine learning"""
        students_df = self.get_all_students(self.custom_filters)

        if students_df.empty or len(students_df) < 50:  # Need sufficient data for ML
            print("Insufficient data for predictive analytics (minimum 50 students required).")
            return

        print("\nGenerating Predictive Analytics...")

        # Prepare data for machine learning
        # Create target variables
        students_df['high_performer'] = (students_df['gpa'] >= 3.5).astype(int)
        students_df['at_risk'] = ((students_df['gpa'] < 2.0) | (students_df['engagement_score'] < 30)).astype(int)
        students_df['will_complete'] = (students_df['completion_status'] == 'Completed').astype(int)

        # Prepare features
        feature_columns = ['age', 'engagement_score']
        students_df['gender_encoded'] = pd.Categorical(students_df['gender']).codes
        students_df['course_encoded'] = pd.Categorical(students_df['course']).codes
        students_df['education_encoded'] = pd.Categorical(students_df['previous_education']).codes

        feature_columns.extend(['gender_encoded', 'course_encoded', 'education_encoded'])

        X = students_df[feature_columns].fillna(0)

        fig = plt.figure(figsize=(20, 15))
        fig.suptitle('Predictive Analytics Dashboard', fontsize=20)

        # 1. High Performer Prediction
        ax1 = fig.add_subplot(331)
        y_performance = students_df['high_performer']

        if len(y_performance.unique()) > 1:  # Ensure we have both classes
            X_train, X_test, y_train, y_test = train_test_split(X, y_performance, test_size=0.3, random_state=42)

            # Scale features
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)

            # Train Random Forest
            rf_performance = RandomForestClassifier(n_estimators=100, random_state=42)
            rf_performance.fit(X_train_scaled, y_train)

            # Feature importance
            importance = rf_performance.feature_importances_
            feature_names = ['Age', 'Engagement', 'Gender', 'Course', 'Education']

            ax1.barh(range(len(importance)), importance, color=CONFIG['colors'])
            ax1.set_yticks(range(len(importance)))
            ax1.set_yticklabels(feature_names)
            ax1.set_xlabel('Feature Importance')
            ax1.set_title('High Performer Prediction - Feature Importance')

            # Calculate accuracy
            accuracy = rf_performance.score(X_test_scaled, y_test)
            ax1.text(0.02, 0.98, f'Accuracy: {accuracy:.3f}', transform=ax1.transAxes,
                    bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))

        # 2. At-Risk Student Prediction
        ax2 = fig.add_subplot(332)
        y_risk = students_df['at_risk']

        if len(y_risk.unique()) > 1:
            X_train, X_test, y_train, y_test = train_test_split(X, y_risk, test_size=0.3, random_state=42)
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)

            rf_risk = RandomForestClassifier(n_estimators=100, random_state=42)
            rf_risk.fit(X_train_scaled, y_train)

            importance_risk = rf_risk.feature_importances_
            ax2.barh(range(len(importance_risk)), importance_risk, color='red', alpha=0.7)
            ax2.set_yticks(range(len(importance_risk)))
            ax2.set_yticklabels(feature_names)
            ax2.set_xlabel('Feature Importance')
            ax2.set_title('At-Risk Prediction - Feature Importance')

            accuracy_risk = rf_risk.score(X_test_scaled, y_test)
            ax2.text(0.02, 0.98, f'Accuracy: {accuracy_risk:.3f}', transform=ax2.transAxes,
                    bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))

        # 3. GPA Prediction Distribution
        ax3 = fig.add_subplot(333)

        # Create GPA prediction model
        from sklearn.ensemble import RandomForestRegressor
        rf_gpa = RandomForestRegressor(n_estimators=100, random_state=42)

        y_gpa = students_df['gpa']
        X_train, X_test, y_train, y_test = train_test_split(X, y_gpa, test_size=0.3, random_state=42)

        scaler_gpa = StandardScaler()
        X_train_scaled = scaler_gpa.fit_transform(X_train)
        X_test_scaled = scaler_gpa.transform(X_test)

        rf_gpa.fit(X_train_scaled, y_train)
        y_pred = rf_gpa.predict(X_test_scaled)

        ax3.scatter(y_test, y_pred, alpha=0.6, color=CONFIG['colors'][0])
        ax3.plot([y_test.min(), y_test.max()], [y_test.min(), y_test.max()], 'r--', lw=2)
        ax3.set_xlabel('Actual GPA')
        ax3.set_ylabel('Predicted GPA')
        ax3.set_title('GPA Prediction Accuracy')

        # Calculate R²
        from sklearn.metrics import r2_score
        r2 = r2_score(y_test, y_pred)
        ax3.text(0.05, 0.95, f'R² Score: {r2:.3f}', transform=ax3.transAxes,
                bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))

        # 4. Student Clustering
        ax4 = fig.add_subplot(334)

        # K-means clustering
        kmeans = KMeans(n_clusters=4, random_state=42, n_init=10)
        clusters = kmeans.fit_predict(X)
        students_df['cluster'] = clusters

        # Visualize clusters using first two principal components
        from sklearn.decomposition import PCA
        pca = PCA(n_components=2)
        X_pca = pca.fit_transform(X)

        colors = ['red', 'blue', 'green', 'orange']
        for i in range(4):
            cluster_data = X_pca[clusters == i]
            ax4.scatter(cluster_data[:, 0], cluster_data[:, 1],
                       c=colors[i], alpha=0.6, label=f'Cluster {i+1}')

        ax4.set_xlabel(f'PC1 ({pca.explained_variance_ratio_[0]:.1%} variance)')
        ax4.set_ylabel(f'PC2 ({pca.explained_variance_ratio_[1]:.1%} variance)')
        ax4.set_title('Student Clustering (PCA Visualization)')
        ax4.legend()

        # 5. Cluster Characteristics
        ax5 = fig.add_subplot(335)

        cluster_stats = students_df.groupby('cluster').agg({
            'gpa': 'mean',
            'engagement_score': 'mean',
            'age': 'mean'
        })

        x = range(len(cluster_stats))
        width = 0.25
        ax5.bar([i - width for i in x], cluster_stats['gpa'], width, label='Avg GPA', alpha=0.7)
        ax5.bar(x, cluster_stats['engagement_score']/25, width, label='Avg Engagement/25', alpha=0.7)
        ax5.bar([i + width for i in x], cluster_stats['age']/10, width, label='Avg Age/10', alpha=0.7)

        ax5.set_xlabel('Cluster')
        ax5.set_ylabel('Scaled Values')
        ax5.set_title('Cluster Characteristics')
        ax5.set_xticks(x)
        ax5.set_xticklabels([f'Cluster {i+1}' for i in range(len(cluster_stats))])
        ax5.legend()

        # 6. Enrollment Forecasting
        ax6 = fig.add_subplot(336)

        # Simple time series forecasting based on registration patterns
        if 'registration_datetime' in students_df.columns:
            students_df['reg_date'] = pd.to_datetime(students_df['registration_datetime'])
            monthly_enrollments = students_df.groupby(students_df['reg_date'].dt.to_period('M')).size()

            # Simple linear trend for forecasting
            if len(monthly_enrollments) > 3:
                x_months = range(len(monthly_enrollments))
                y_enrollments = monthly_enrollments.values

                # Fit trend line
                z = np.polyfit(x_months, y_enrollments, 1)
                p = np.poly1d(z)

                # Forecast next 6 months
                future_months = range(len(monthly_enrollments), len(monthly_enrollments) + 6)
                future_enrollments = [p(month) for month in future_months]

                # Plot historical and forecasted data
                ax6.plot(x_months, y_enrollments, 'o-', label='Historical', color=CONFIG['colors'][0])
                ax6.plot(future_months, future_enrollments, 's--', label='Forecast', color='red')
                ax6.set_xlabel('Month')
                ax6.set_ylabel('Enrollments')
                ax6.set_title('Enrollment Forecasting')
                ax6.legend()

                # Add trend line
                all_months = list(x_months) + list(future_months)
                trend_line = [p(month) for month in all_months]
                ax6.plot(all_months, trend_line, ':', alpha=0.5, color='gray', label='Trend')

        # 7. Risk Score Distribution
        ax7 = fig.add_subplot(337)

        # Calculate comprehensive risk score
        students_df['risk_score'] = (
            (students_df['gpa'] < 2.5).astype(int) * 2 +
            (students_df['engagement_score'] < 40).astype(int) * 2 +
            (students_df['age'] > 40).astype(int) * 1  # Older students might need different support
        )

        risk_dist = students_df['risk_score'].value_counts().sort_index()
        risk_colors = ['green', 'yellow', 'orange', 'red', 'darkred', 'purple']

        ax7.bar(risk_dist.index, risk_dist.values, color=risk_colors[:len(risk_dist)], alpha=0.7)
        ax7.set_xlabel('Risk Score')
        ax7.set_ylabel('Number of Students')
        ax7.set_title('Comprehensive Risk Score Distribution')

        # 8. Predictive Model Comparison
        ax8 = fig.add_subplot(338)

        # Compare different models for at-risk prediction
        from sklearn.linear_model import LogisticRegression
        from sklearn.svm import SVC
        from sklearn.naive_bayes import GaussianNB

        models = {
            'Random Forest': RandomForestClassifier(n_estimators=100, random_state=42),
            'Logistic Regression': LogisticRegression(random_state=42, max_iter=1000),
            'SVM': SVC(random_state=42),
            'Naive Bayes': GaussianNB()
        }

        model_scores = []
        model_names = []

        if len(y_risk.unique()) > 1:
            X_train, X_test, y_train, y_test = train_test_split(X, y_risk, test_size=0.3, random_state=42)
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)

            for name, model in models.items():
                try:
                    model.fit(X_train_scaled, y_train)
                    score = model.score(X_test_scaled, y_test)
                    model_scores.append(score)
                    model_names.append(name)
                except Exception:
                    continue  # Skip models that fail

            ax8.bar(range(len(model_scores)), model_scores, color=CONFIG['colors'], alpha=0.7)
            ax8.set_xticks(range(len(model_names)))
            ax8.set_xticklabels(model_names, rotation=45, ha='right')
            ax8.set_ylabel('Accuracy Score')
            ax8.set_title('Model Performance Comparison')
            ax8.set_ylim(0, 1)

        # 9. Feature Correlation with Predictions
        ax9 = fig.add_subplot(339)

        # Show how well individual features predict outcomes
        feature_predictive_power = []
        for i, feature in enumerate(feature_columns):
            if len(students_df[feature].unique()) > 1:
                corr_performance = abs(students_df[feature].corr(students_df['high_performer']))
                corr_risk = abs(students_df[feature].corr(students_df['at_risk']))
                avg_predictive_power = (corr_performance + corr_risk) / 2
                feature_predictive_power.append(avg_predictive_power)
            else:
                feature_predictive_power.append(0)

        ax9.barh(range(len(feature_names)), feature_predictive_power, color=CONFIG['colors'])
        ax9.set_yticks(range(len(feature_names)))
        ax9.set_yticklabels(feature_names)
        ax9.set_xlabel('Average Predictive Power')
        ax9.set_title('Feature Predictive Power Analysis')

        plt.tight_layout(rect=[0, 0, 1, 0.95])

        # Print detailed predictive analytics summary
        print("\n" + "="*60)
        print("PREDICTIVE ANALYTICS SUMMARY")
        print("="*60)

        print(f"Model Performance:")
        if len(y_performance.unique()) > 1:
            print(f"  High Performer Prediction Accuracy: {accuracy:.3f}")
        if len(y_risk.unique()) > 1:
            print(f"  At-Risk Student Prediction Accuracy: {accuracy_risk:.3f}")
        print(f"  GPA Prediction R² Score: {r2:.3f}")

        print(f"\nStudent Clusters Identified: {len(cluster_stats)}")
        for i, (cluster, stats) in enumerate(cluster_stats.iterrows()):
            print(f"  Cluster {cluster+1}: Avg GPA {stats['gpa']:.2f}, Avg Engagement {stats['engagement_score']:.1f}")

        print(f"\nRisk Score Distribution:")
        for score, count in risk_dist.items():
            risk_level = ['Very Low', 'Low', 'Medium', 'High', 'Very High', 'Critical'][min(score, 5)]
            print(f"  Score {score} ({risk_level}): {count} students ({count/len(students_df)*100:.1f}%)")

        print(f"\nTop Predictive Features:")
        feature_importance_sorted = sorted(zip(feature_names, feature_predictive_power),
                                         key=lambda x: x[1], reverse=True)
        for feature, power in feature_importance_sorted[:3]:
            print(f"  {feature}: {power:.3f}")

        if len(model_scores) > 0:
            best_model = model_names[np.argmax(model_scores)]
            print(f"\nBest Performing Model: {best_model} (Accuracy: {max(model_scores):.3f})")

        self.save_or_display_plot(fig, "predictive_analytics")
