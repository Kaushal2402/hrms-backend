"""
performance_backend_business_rules.py — Business rules and configurations for Performance Management sub-modules.
"""

MODULE_PRIORITY = [
    "goal_frameworks",
    "appraisal_cycles",
    "appraisals"
]

ROUTE_MAP = {
    "goal_frameworks": "/performance/goals",
    "appraisal_cycles": "/performance/cycles",
    "appraisals": "/performance/appraisals",
    "feedback_360": "/performance/feedback-360",
    "competencies": "/performance/competencies",
    "one_on_ones": "/performance/meetings",
    "pip": "/performance/pip",
    "talent_reviews": "/performance/talent",
    "performance_integrations": "/performance/integrations"
}

PERMISSION_CODES = {
    "goal_frameworks": {"READ": "201", "CREATE": "202", "UPDATE": "203", "DELETE": "204"},
    "appraisal_cycles": {"READ": "209", "CREATE": "210", "UPDATE": "211", "DELETE": "212"},
    "appraisals": {"READ": "213", "UPDATE": "214", "APPROVE": "215"},
    "feedback_360": {"READ": "216", "CREATE": "217", "SUBMIT": "218"},
    "competencies": {"READ": "219", "CREATE": "220", "UPDATE": "221"},
    "one_on_ones": {"READ": "222", "CREATE": "223"},
    "pip": {"READ": "224", "CREATE": "225", "UPDATE": "226"},
    "talent_reviews": {"READ": "227", "CREATE": "228", "UPDATE": "229"},
    "performance_integrations": {"READ": "205", "CREATE": "206", "UPDATE": "207", "DELETE": "208"}
}

MODULE_RULES = {
    "goal_frameworks": """
BUSINESS RULES:
- GoalFramework: framework_type must be GoalFrameworkType (OKR, SMART, KPI, CUSTOM).
- When a framework is set as default (is_default=True), all other frameworks in the same organization must have is_default set to False.
- OrganizationGoal: owner must be an active employee. FISCAL YEAR format verification (e.g. FY2025).
- DepartmentGoal: must link to a valid organization goal if cascading is specified.
- EmployeeGoal: supports SMART verification (is_specific, is_measurable, is_achievable, is_relevant, is_time_bound) and OKR objectives/key results alignment.
- GoalProgress check-in: current_value should update progress_percentage based on measurement type and baseline/target values.
- GoalAlignment mapping: allows explicit parent-child goal hierarchy linkage.
""",

    "appraisal_cycles": """
BUSINESS RULES:
- AppraisalCycle: validate dates: review_period_start < review_period_end. Goal setting window, self appraisal window, and manager review window must lie within or sequence correctly.
- CycleStatus transition: DRAFT -> ACTIVE -> SELF_APPRAISAL -> MANAGER_REVIEW -> CALIBRATION -> COMPLETED.
- RatingScale: scale_points must be a valid JSON array of scale point objects (with value, label, description, color). Max and Min values must match scale point bounds.
- AppraisalTemplate: weights of all sections (goal_section_weight, competency_section_weight, behavior_section_weight, other_section_weight) must sum to exactly 100.00.
- AppraisalSection: ordering must be unique within a template.
- AppraisalQuestion: QuestionType must be QuestionType (RATING, TEXT, MULTI_CHOICE, GOAL_RATING, COMPETENCY_RATING).
""",

    "appraisals": """
BUSINESS RULES:
- AppraisalRecord: status transitions NOT_STARTED -> SELF_IN_PROGRESS -> SELF_SUBMITTED -> MANAGER_IN_PROGRESS -> MANAGER_SUBMITTED -> CALIBRATION_PENDING -> CALIBRATED -> PUBLISHED -> ACKNOWLEDGED.
- Computed scores: self_overall_score and manager_overall_score must be computed using template section weights.
- SelfAppraisal: Narrative summary validation. Career aspirations logging.
- ManagerAppraisal: Performance rating override checks, feedback commentary.
- Calibration: Calibrators can adjust final score and rating labels. Audit logs should record calibrated_by and calibration_notes.
- Bell Curve: Verify rating distribution matches Cycle's bell_curve_config if enabled.
""",

    "feedback_360": """
BUSINESS RULES:
- 360 FeedbackRequest: status transitions: PENDING -> IN_PROGRESS -> COMPLETED -> EXPIRED.
- FeedbackProviderType must be PEER, SUBORDINATE, SUPERVISOR, EXTERNAL.
- RespondentType must be EMPLOYEE, MANAGER, HR.
- Prevent duplicate requests to the same provider for the same employee in the same appraisal cycle.
- FeedbackResponse: answers must be verified against the feedback questions.
""",

    "competencies": """
BUSINESS RULES:
- CompetencyFramework: defines core organizational competencies.
- CompetencyMapping: links job titles/departments to specific competencies with required proficiency levels.
- EmployeeCompetency: tracks employee's self-assessed and manager-assessed competency levels.
- Skills Gap Analysis: computes required competency level vs actual level for an employee. Gap = required - actual.
""",

    "one_on_ones": """
BUSINESS RULES:
- 1-on-1 Meeting: status transitions: SCHEDULED -> COMPLETED -> CANCELLED.
- Agenda Items: must belong to a 1-on-1 meeting. Can be checked off (is_completed=True).
- ContinuousFeedback: log feedback between any two employees. Can specify is_anonymous.
- PerformanceNotes: private or manager-shared journal notes for continuous tracking.
""",

    "pip": """
BUSINESS RULES:
- PIP Plan: status transitions: DRAFT -> ACTIVE -> ON_TRACK -> AT_RISK -> COMPLETED_SUCCESS -> COMPLETED_FAILURE -> WITHDRAWN.
- PIP duration should normally be 30, 60, or 90 days.
- PIP Objectives: specific targets to achieve during the PIP period.
- Progress Logs: periodic check-ins. Must record performance status and reviewer comments.
""",

    "talent_reviews": """
BUSINESS RULES:
- TalentReview: evaluates potential vs performance (NineBoxPosition).
- Nine-Box Grid Positions: LOW_LOW, LOW_MED, LOW_HIGH, MED_LOW, MED_MED, MED_HIGH, HIGH_LOW, HIGH_MED, HIGH_HIGH.
- SuccessionPlan: defines critical positions, backup readiness, and risk of loss (RetentionRisk).
- SuccessionCandidates: readiness levels (READY_NOW, READY_1_2_YEARS, READY_3_5_YEARS).
""",

    "performance_integrations": """
BUSINESS RULES:
- Performance Analytics: retrieve organization-wide goal completion rates, average appraisal scores, and distribution stats.
- Notification Templates: maps performance events to email/system notification formats.
- Compensation Integration: recommend promotion or salary adjustment based on final appraisal rating.
"""
}
