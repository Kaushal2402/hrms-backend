from typing import List, Optional, Any, Dict
from datetime import datetime, date
from decimal import Decimal
import uuid
from pydantic import BaseModel, UUID4

from app.models.performance import (
    AppraisalStatus,
    CycleStatus,
    QuestionType
)

# ============================================================
# NESTED OBJECT SUMMARIES (OBJECT ENRICHMENT)
# ============================================================

class EmployeePerformanceSummary(BaseModel):
    uuid: UUID4
    first_name: str
    last_name: str
    email: str
    employee_id: Optional[str] = None

    class Config:
        from_attributes = True


class AppraisalCycleSummary(BaseModel):
    uuid: UUID4
    name: str
    status: CycleStatus

    class Config:
        from_attributes = True


class AppraisalTemplateSummary(BaseModel):
    uuid: UUID4
    name: str

    class Config:
        from_attributes = True


class RoleSummary(BaseModel):
    uuid: UUID4
    name: str

    class Config:
        from_attributes = True


class DepartmentSummary(BaseModel):
    uuid: UUID4
    name: str

    class Config:
        from_attributes = True


class RatingScaleSummary(BaseModel):
    uuid: UUID4
    name: str
    min_value: Optional[int] = None
    max_value: Optional[int] = None

    class Config:
        from_attributes = True


class GoalSummarySchema(BaseModel):
    uuid: UUID4
    title: str
    description: Optional[str] = None
    status: str
    weight: Optional[Decimal] = None
    target_value: Optional[str] = None
    current_value: Optional[str] = None

    class Config:
        from_attributes = True


class SelfAppraisalGoalsResponse(BaseModel):
    success: bool
    message: str
    data: List[GoalSummarySchema]


# ============================================================
# APPRAISAL ANSWERS
# ============================================================

class AppraisalAnswerBulkItem(BaseModel):
    question_uuid: UUID4
    rating_value: Optional[Decimal] = None
    text_answer: Optional[str] = None
    goal_uuid: Optional[UUID4] = None
    goal_achievement_percentage: Optional[Decimal] = None
    competency_uuid: Optional[UUID4] = None

    class Config:
        from_attributes = True


class AppraisalAnswerBase(BaseModel):
    respondent_type: str  # "self" or "manager"
    rating_value: Optional[Decimal] = None
    rating_label: Optional[str] = None
    text_answer: Optional[str] = None
    selected_choices: Optional[List[Any]] = None
    goal_achievement_percentage: Optional[Decimal] = None
    weight_applied: Optional[Decimal] = None
    weighted_score: Optional[Decimal] = None

    class Config:
        from_attributes = True


class AppraisalAnswerCreate(BaseModel):
    question_uuid: UUID4
    respondent_type: str
    rating_value: Optional[Decimal] = None
    rating_label: Optional[str] = None
    text_answer: Optional[str] = None
    selected_choices: Optional[List[Any]] = None
    goal_uuid: Optional[UUID4] = None
    goal_achievement_percentage: Optional[Decimal] = None
    competency_uuid: Optional[UUID4] = None

    class Config:
        from_attributes = True


class AppraisalAnswerUpdate(BaseModel):
    rating_value: Optional[Decimal] = None
    rating_label: Optional[str] = None
    text_answer: Optional[str] = None
    selected_choices: Optional[List[Any]] = None
    goal_achievement_percentage: Optional[Decimal] = None

    class Config:
        from_attributes = True


class AppraisalAnswerSchema(AppraisalAnswerBase):
    uuid: UUID4
    appraisal_record_uuid: UUID4
    question_uuid: UUID4
    respondent: Optional[EmployeePerformanceSummary] = None
    goal_uuid: Optional[UUID4] = None
    competency_uuid: Optional[UUID4] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AppraisalAnswerResponse(BaseModel):
    success: bool
    message: str
    data: Optional[AppraisalAnswerSchema] = None


class AppraisalAnswerListResponse(BaseModel):
    success: bool
    message: str
    data: List[AppraisalAnswerSchema]


class AppraisalAnswerBulkRequest(BaseModel):
    respondent_type: str
    answers: List[AppraisalAnswerBulkItem]


class AppraisalAnswerBulkResponse(BaseModel):
    success: bool
    message: str
    data: Dict[str, Any]  # {"saved_count": int}


# ============================================================
# SELF APPRAISALS
# ============================================================

class SelfAppraisalBase(BaseModel):
    achievements_summary: Optional[str] = None
    challenges_faced: Optional[str] = None
    learning_development: Optional[str] = None
    career_aspirations: Optional[str] = None
    support_needed: Optional[str] = None
    is_submitted: bool = False
    submitted_at: Optional[datetime] = None
    last_saved_at: Optional[datetime] = None
    draft_version: int = 1

    class Config:
        from_attributes = True


class SelfAppraisalCreate(BaseModel):
    appraisal_record_uuid: UUID4
    achievements_summary: Optional[str] = None
    challenges_faced: Optional[str] = None
    learning_development: Optional[str] = None
    career_aspirations: Optional[str] = None
    support_needed: Optional[str] = None

    class Config:
        from_attributes = True


class SelfAppraisalUpdate(BaseModel):
    achievements_summary: Optional[str] = None
    challenges_faced: Optional[str] = None
    learning_development: Optional[str] = None
    career_aspirations: Optional[str] = None
    support_needed: Optional[str] = None
    answers: Optional[List[AppraisalAnswerBulkItem]] = None

    class Config:
        from_attributes = True


class SelfAppraisalSchema(SelfAppraisalBase):
    uuid: UUID4
    appraisal_record_uuid: UUID4
    employee: Optional[EmployeePerformanceSummary] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SelfAppraisalResponse(BaseModel):
    success: bool
    message: str
    data: Optional[SelfAppraisalSchema] = None


class SelfAppraisalCompletionResponse(BaseModel):
    success: bool
    message: str
    data: Dict[str, Any]  # {"completion_percentage": float, "answered_count": int, "total_required": int}


class PendingSelfAppraisalItem(BaseModel):
    employee: EmployeePerformanceSummary
    manager: Optional[EmployeePerformanceSummary] = None
    appraisal_cycle: AppraisalCycleSummary
    deadline: Optional[date] = None
    days_remaining: int

    class Config:
        from_attributes = True


class PendingSelfAppraisalsListResponse(BaseModel):
    success: bool
    message: str
    data: List[PendingSelfAppraisalItem]


# ============================================================
# MANAGER APPRAISALS
# ============================================================

class ManagerAppraisalBase(BaseModel):
    performance_summary: Optional[str] = None
    strengths: Optional[str] = None
    areas_for_improvement: Optional[str] = None
    development_plan: Optional[str] = None
    promotion_recommendation: Optional[str] = None
    override_reason: Optional[str] = None
    is_submitted: bool = False
    submitted_at: Optional[datetime] = None
    last_saved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ManagerAppraisalCreate(BaseModel):
    appraisal_record_uuid: UUID4
    performance_summary: Optional[str] = None
    strengths: Optional[str] = None
    areas_for_improvement: Optional[str] = None
    development_plan: Optional[str] = None
    promotion_recommendation: Optional[str] = None

    class Config:
        from_attributes = True


class ManagerAppraisalUpdate(BaseModel):
    performance_summary: Optional[str] = None
    strengths: Optional[str] = None
    areas_for_improvement: Optional[str] = None
    development_plan: Optional[str] = None
    promotion_recommendation: Optional[str] = None
    answers: Optional[List[AppraisalAnswerBulkItem]] = None

    class Config:
        from_attributes = True


class ManagerAppraisalSchema(ManagerAppraisalBase):
    uuid: UUID4
    appraisal_record_uuid: UUID4
    manager: Optional[EmployeePerformanceSummary] = None
    employee: Optional[EmployeePerformanceSummary] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ManagerAppraisalResponse(BaseModel):
    success: bool
    message: str
    data: Optional[ManagerAppraisalSchema] = None


class PendingManagerAppraisalItem(BaseModel):
    employee: EmployeePerformanceSummary
    appraisal_cycle: AppraisalCycleSummary
    deadline: Optional[date] = None
    days_remaining: int

    class Config:
        from_attributes = True


class PendingManagerAppraisalsListResponse(BaseModel):
    success: bool
    message: str
    data: List[PendingManagerAppraisalItem]


class ScoreComparisonSection(BaseModel):
    title: str
    self_score: Optional[Decimal] = None
    manager_score: Optional[Decimal] = None
    delta: Optional[Decimal] = None

    class Config:
        from_attributes = True


class ScoreComparisonResponse(BaseModel):
    success: bool
    message: str
    data: List[ScoreComparisonSection]


class ManagerOverrideScoreRequest(BaseModel):
    manager_overall_score: Decimal
    manager_rating_label: str
    override_reason: str

    class Config:
        from_attributes = True


# ============================================================
# APPRAISAL RECORDS
# ============================================================

class AppraisalRecordBase(BaseModel):
    status: AppraisalStatus = AppraisalStatus.NOT_STARTED
    self_goal_score: Optional[Decimal] = None
    self_competency_score: Optional[Decimal] = None
    self_overall_score: Optional[Decimal] = None
    self_rating_label: Optional[str] = None
    manager_goal_score: Optional[Decimal] = None
    manager_competency_score: Optional[Decimal] = None
    manager_overall_score: Optional[Decimal] = None
    manager_rating_label: Optional[str] = None
    final_score: Optional[Decimal] = None
    final_rating_label: Optional[str] = None
    calibrated_score: Optional[Decimal] = None
    calibration_notes: Optional[str] = None
    acknowledged_by_employee: bool = False
    employee_disagreement_reason: Optional[str] = None
    has_360_feedback: bool = False
    feedback_360_score: Optional[Decimal] = None
    compensation_action_triggered: bool = False
    promotion_recommended: bool = False
    promotion_recommended_to_grade: Optional[str] = None
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class AppraisalRecordCreate(BaseModel):
    appraisal_cycle_uuid: UUID4
    employee_uuid: UUID4
    manager_uuid: Optional[UUID4] = None
    template_uuid: UUID4
    rating_scale_uuid: UUID4
    status: Optional[AppraisalStatus] = AppraisalStatus.NOT_STARTED
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class AppraisalRecordUpdate(BaseModel):
    status: Optional[AppraisalStatus] = None
    self_goal_score: Optional[Decimal] = None
    self_competency_score: Optional[Decimal] = None
    self_overall_score: Optional[Decimal] = None
    self_rating_label: Optional[str] = None
    manager_goal_score: Optional[Decimal] = None
    manager_competency_score: Optional[Decimal] = None
    manager_overall_score: Optional[Decimal] = None
    manager_rating_label: Optional[str] = None
    final_score: Optional[Decimal] = None
    final_rating_label: Optional[str] = None
    calibrated_score: Optional[Decimal] = None
    calibration_notes: Optional[str] = None
    acknowledged_by_employee: Optional[bool] = None
    employee_disagreement_reason: Optional[str] = None
    has_360_feedback: Optional[bool] = None
    feedback_360_score: Optional[Decimal] = None
    compensation_action_triggered: Optional[bool] = None
    promotion_recommended: Optional[bool] = None
    promotion_recommended_to_grade: Optional[str] = None
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class AppraisalRecordSchema(AppraisalRecordBase):
    uuid: UUID4
    appraisal_cycle: Optional[AppraisalCycleSummary] = None
    employee: Optional[EmployeePerformanceSummary] = None
    manager: Optional[EmployeePerformanceSummary] = None
    template: Optional[AppraisalTemplateSummary] = None
    rating_scale: Optional[RatingScaleSummary] = None
    calibrated_by: Optional[EmployeePerformanceSummary] = None
    calibrated_at: Optional[datetime] = None
    self_appraisal_submitted_at: Optional[datetime] = None
    manager_review_submitted_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    published_by: Optional[EmployeePerformanceSummary] = None
    employee_acknowledged_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AppraisalRecordResponse(BaseModel):
    success: bool
    message: str
    data: Optional[AppraisalRecordSchema] = None


class AppraisalRecordListResponse(BaseModel):
    success: bool
    message: str
    pagination: Dict[str, Any]
    data: List[AppraisalRecordSchema]


class AppraisalRecordAcknowledge(BaseModel):
    acknowledged: Optional[bool] = None
    employee_disagreement_reason: Optional[str] = None

    class Config:
        from_attributes = True


class AppraisalRecordCalibrate(BaseModel):
    calibrated_score: Optional[Decimal] = None
    final_rating_label: Optional[str] = None
    calibration_notes: Optional[str] = None

    class Config:
        from_attributes = True


class AppraisalRecordRecommendPromotion(BaseModel):
    promotion_recommended: Optional[bool] = None
    promotion_recommended_to_grade: Optional[str] = None
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class BulkPublishRequest(BaseModel):
    appraisal_cycle_uuid: Optional[UUID4] = None
    department_uuids: Optional[List[UUID4]] = None
    rating_labels: Optional[List[str]] = None

    class Config:
        from_attributes = True


class BulkPublishResponse(BaseModel):
    success: bool
    message: str
    data: Dict[str, int]  # {"published_count": int, "skipped_count": int}


class GenerateRecordsResponse(BaseModel):
    success: bool
    message: str
    data: Dict[str, int]  # {"records_created": int}


class ReopenRequest(BaseModel):
    reason: Optional[str] = None

    class Config:
        from_attributes = True


class AppraisalRecordHistoryItem(BaseModel):
    status: AppraisalStatus
    changed_at: datetime
    changed_by: str
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class AppraisalRecordHistoryResponse(BaseModel):
    success: bool
    message: str
    data: List[AppraisalRecordHistoryItem]


# ============================================================
# CALIBRATION
# ============================================================

class AppraisalCalibrationBase(BaseModel):
    name: str
    scheduled_date: Optional[datetime] = None
    conducted_date: Optional[datetime] = None
    target_distribution: Optional[Dict[str, float]] = None
    actual_distribution: Optional[Dict[str, float]] = None
    status: str = "SCHEDULED"
    session_notes: Optional[str] = None
    meeting_minutes: Optional[str] = None

    class Config:
        from_attributes = True


class AppraisalCalibrationCreate(BaseModel):
    appraisal_cycle_uuid: UUID4
    name: str
    department_uuid: Optional[UUID4] = None
    scheduled_date: Optional[datetime] = None
    facilitator_uuid: UUID4
    target_distribution: Optional[Dict[str, float]] = None

    class Config:
        from_attributes = True


class AppraisalCalibrationUpdate(BaseModel):
    name: Optional[str] = None
    scheduled_date: Optional[datetime] = None
    facilitator_uuid: Optional[UUID4] = None
    target_distribution: Optional[Dict[str, float]] = None
    notes: Optional[str] = None
    status: Optional[str] = None

    class Config:
        from_attributes = True


class AppraisalCalibrationSchema(AppraisalCalibrationBase):
    uuid: UUID4
    appraisal_cycle: Optional[AppraisalCycleSummary] = None
    department_uuid: Optional[UUID4] = None
    facilitator: Optional[EmployeePerformanceSummary] = None
    created_by: Optional[EmployeePerformanceSummary] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AppraisalCalibrationResponse(BaseModel):
    success: bool
    message: str
    data: Optional[AppraisalCalibrationSchema] = None


class AppraisalCalibrationListResponse(BaseModel):
    success: bool
    message: str
    pagination: Dict[str, Any]
    data: List[AppraisalCalibrationSchema]


class CalibrationStartRequest(BaseModel):
    conducted_date: Optional[datetime] = None

    class Config:
        from_attributes = True


class CalibrationCompleteRequest(BaseModel):
    session_notes: Optional[str] = None
    meeting_minutes: Optional[str] = None
    actual_distribution: Optional[Dict[str, float]] = None

    class Config:
        from_attributes = True


class CalibrationEmployeeSchema(BaseModel):
    employee: EmployeePerformanceSummary
    self_overall_score: Optional[Decimal] = None
    manager_overall_score: Optional[Decimal] = None
    calibrated_score: Optional[Decimal] = None
    final_rating_label: Optional[str] = None

    class Config:
        from_attributes = True


class CalibrationEmployeeListResponse(BaseModel):
    success: bool
    message: str
    data: List[CalibrationEmployeeSchema]


class CalibrationDistributionItem(BaseModel):
    label: str
    target_pct: float
    target_count: int
    actual_count: int
    actual_pct: float
    variance: float

    class Config:
        from_attributes = True


class CalibrationDistributionResponse(BaseModel):
    success: bool
    message: str
    data: List[CalibrationDistributionItem]


class CalibrationParticipantItem(BaseModel):
    employee_uuid: UUID4
    role: str

    class Config:
        from_attributes = True


class CalibrationParticipantsCreate(BaseModel):
    participants: Optional[List[CalibrationParticipantItem]] = None

    class Config:
        from_attributes = True


class CalibrationParticipantsResponse(BaseModel):
    success: bool
    message: str
    data: List[CalibrationParticipantItem]


# ============================================================
# BELL CURVE DISTRIBUTION
# ============================================================

class BellCurveDistributionItem(BaseModel):
    rating_label: str
    target_percentage: float
    target_count: int
    actual_count: int
    actual_percentage: float
    variance: float

    class Config:
        from_attributes = True


class BellCurveDistributionResponse(BaseModel):
    success: bool
    message: str
    data: List[BellCurveDistributionItem]


class BellCurveComputeRequest(BaseModel):
    department_uuid: Optional[UUID4] = None

    class Config:
        from_attributes = True


class BellCurveTargetItem(BaseModel):
    rating_label: str
    target_percentage: float

    class Config:
        from_attributes = True


class BellCurveTargetsUpdateRequest(BaseModel):
    department_uuid: Optional[UUID4] = None
    distribution: Optional[List[BellCurveTargetItem]] = None

    class Config:
        from_attributes = True


class BellCurveOutlierItem(BaseModel):
    employee: EmployeePerformanceSummary
    self_overall_score: Optional[Decimal] = None
    manager_overall_score: Optional[Decimal] = None
    variance: Optional[Decimal] = None

    class Config:
        from_attributes = True


class BellCurveOutliersResponse(BaseModel):
    success: bool
    message: str
    data: List[BellCurveOutlierItem]


# ============================================================
# RATING SCALES & TEMPLATES SCHEMAS
# ============================================================

class RatingScalePointSchema(BaseModel):
    value: float
    label: str
    description: Optional[str] = None
    color: Optional[str] = None
    is_passing: Optional[bool] = False

class RatingScaleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    scale_points: List[RatingScalePointSchema]
    min_value: Decimal
    max_value: Decimal
    is_default: bool = False
    is_active: bool = True

class RatingScaleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    scale_points: Optional[List[RatingScalePointSchema]] = None
    min_value: Optional[Decimal] = None
    max_value: Optional[Decimal] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None

class RatingScaleSchema(BaseModel):
    uuid: UUID4
    name: str
    description: Optional[str] = None
    is_default: bool
    is_active: bool
    scale_points: List[Any]
    min_value: Decimal
    max_value: Decimal
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RatingScaleListResponse(BaseModel):
    success: bool
    message: str
    data: List[RatingScaleSchema]
    pagination: Optional[dict] = None


class RatingScaleDetailResponse(BaseModel):
    success: bool
    message: str
    data: RatingScaleSchema


class RatingScaleLookupSchema(BaseModel):
    uuid: UUID4
    name: str
    min_value: Decimal
    max_value: Decimal

    class Config:
        from_attributes = True


class RatingScaleLookupResponse(BaseModel):
    success: bool
    message: str
    data: List[RatingScaleLookupSchema]

class UsageItemSchema(BaseModel):
    uuid: UUID4
    name: str

class RatingScaleUsageSchema(BaseModel):
    templates: List[UsageItemSchema]
    cycles: List[UsageItemSchema]

class RatingScaleUsageResponse(BaseModel):
    success: bool
    message: str
    data: RatingScaleUsageSchema


class AppraisalTemplateSchema(BaseModel):
    uuid: UUID4
    name: str
    description: Optional[str] = None
    is_active: bool
    is_default: bool
    applicable_roles: List[RoleSummary]
    applicable_departments: List[DepartmentSummary]
    applicable_grades: List[Any]
    goal_section_weight: Decimal
    competency_section_weight: Decimal
    behavior_section_weight: Decimal
    other_section_weight: Decimal
    self_appraisal_enabled: bool
    self_rating_visible_to_manager: bool
    employee_comments_enabled: bool
    manager_override_enabled: bool
    final_rating_formula: str
    version: int
    rating_scale: Optional[RatingScaleSummary] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AppraisalTemplateListResponse(BaseModel):
    success: bool
    message: str
    data: List[AppraisalTemplateSchema]
    pagination: Optional[dict] = None


class AppraisalTemplateLookupSchema(BaseModel):
    uuid: UUID4
    name: str
    is_active: bool
    is_default: bool

    class Config:
        from_attributes = True


class AppraisalTemplateLookupResponse(BaseModel):
    success: bool
    message: str
    data: List[AppraisalTemplateLookupSchema]


class AppraisalQuestionCreate(BaseModel):
    question_text: str
    question_type: QuestionType
    question_order: int
    is_required: bool = True
    weight: Decimal = Decimal("100.00")
    use_section_rating_scale: bool = True
    custom_rating_scale_uuid: Optional[UUID4] = None
    choices: Optional[List[Any]] = None
    allow_multiple_selection: bool = False
    competency_uuid: Optional[UUID4] = None
    auto_populate_goals: bool = False
    guidance: Optional[str] = None
    placeholder_text: Optional[str] = None

class AppraisalQuestionUpdate(AppraisalQuestionCreate):
    pass

class AppraisalQuestionSchema(AppraisalQuestionCreate):
    uuid: UUID4
    custom_rating_scale: Optional[RatingScaleSummary] = None

    class Config:
        from_attributes = True


class AppraisalSectionCreate(BaseModel):
    title: str
    description: Optional[str] = None
    section_order: int
    weight: Decimal
    section_type: str
    is_required: bool = True
    instructions: Optional[str] = None
    visible_to_employee: bool = True
    visible_to_manager: bool = True
    questions: List[AppraisalQuestionCreate] = []

class AppraisalSectionUpdate(AppraisalSectionCreate):
    questions: List[AppraisalQuestionUpdate] = []

class AppraisalSectionSchema(BaseModel):
    uuid: UUID4
    title: str
    description: Optional[str] = None
    section_order: int
    weight: Decimal
    section_type: str
    is_required: bool
    instructions: Optional[str] = None
    visible_to_employee: bool
    visible_to_manager: bool
    questions: List[AppraisalQuestionSchema] = []

    class Config:
        from_attributes = True


class AppraisalTemplateCreate(BaseModel):
    name: str
    description: Optional[str] = None
    rating_scale_uuid: UUID4
    is_active: bool = True
    is_default: bool = False
    applicable_roles: List[UUID4]
    applicable_departments: List[UUID4]
    applicable_grades: Optional[List[str]] = None
    goal_section_weight: Decimal = Decimal("40.00")
    competency_section_weight: Decimal = Decimal("30.00")
    behavior_section_weight: Decimal = Decimal("20.00")
    other_section_weight: Decimal = Decimal("10.00")
    self_appraisal_enabled: bool = True
    self_rating_visible_to_manager: bool = True
    employee_comments_enabled: bool = True
    manager_override_enabled: bool = True
    final_rating_formula: str = "weighted_average"
    sections: List[AppraisalSectionCreate] = []

class AppraisalTemplateUpdate(AppraisalTemplateCreate):
    sections: List[AppraisalSectionUpdate] = []

class AppraisalTemplateDetailSchema(AppraisalTemplateSchema):
    sections: List[AppraisalSectionSchema] = []

    class Config:
        from_attributes = True

class AppraisalTemplateDetailResponse(BaseModel):
    success: bool
    message: str
    data: AppraisalTemplateDetailSchema
