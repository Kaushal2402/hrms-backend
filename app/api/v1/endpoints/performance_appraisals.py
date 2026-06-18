import uuid
from typing import List, Optional, Union, Dict, Any
from datetime import datetime, date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_, func

from app.api import deps
from app.models.organization import Organization
from app.models.employee import Employee, Department
from app.models.rbac import Role
from app.models.performance import (
    AppraisalRecord,
    SelfAppraisal,
    ManagerAppraisal,
    AppraisalAnswer,
    AppraisalCalibration,
    CalibrationParticipant,
    BellCurveDistribution,
    AppraisalCycle,
    AppraisalTemplate,
    RatingScale,
    AppraisalSection,
    AppraisalQuestion,
    EmployeeGoal,
    CompetencyFramework,
    AppraisalStatus,
    CycleStatus
)
from app.schemas.performance_appraisals import (
    AppraisalRecordResponse,
    AppraisalRecordListResponse,
    AppraisalRecordCreate,
    AppraisalRecordUpdate,
    AppraisalRecordAcknowledge,
    AppraisalRecordCalibrate,
    AppraisalRecordRecommendPromotion,
    BulkPublishRequest,
    BulkPublishResponse,
    GenerateRecordsResponse,
    ReopenRequest,
    AppraisalRecordHistoryResponse,
    AppraisalRecordHistoryItem,
    SelfAppraisalResponse,
    SelfAppraisalCreate,
    SelfAppraisalUpdate,
    SelfAppraisalCompletionResponse,
    PendingSelfAppraisalsListResponse,
    PendingSelfAppraisalItem,
    SelfAppraisalGoalsResponse,
    ManagerAppraisalResponse,
    ManagerAppraisalCreate,
    ManagerAppraisalUpdate,
    PendingManagerAppraisalsListResponse,
    PendingManagerAppraisalItem,
    ScoreComparisonResponse,
    ScoreComparisonSection,
    ManagerOverrideScoreRequest,
    AppraisalAnswerResponse,
    AppraisalAnswerListResponse,
    AppraisalAnswerCreate,
    AppraisalAnswerUpdate,
    AppraisalAnswerBulkRequest,
    AppraisalAnswerBulkResponse,
    AppraisalCalibrationResponse,
    AppraisalCalibrationListResponse,
    AppraisalCalibrationCreate,
    AppraisalCalibrationUpdate,
    CalibrationStartRequest,
    CalibrationCompleteRequest,
    CalibrationEmployeeListResponse,
    CalibrationEmployeeSchema,
    CalibrationDistributionResponse,
    CalibrationDistributionItem,
    CalibrationParticipantsCreate,
    CalibrationParticipantsResponse,
    CalibrationParticipantItem,
    BellCurveDistributionResponse,
    BellCurveDistributionItem,
    BellCurveComputeRequest,
    BellCurveTargetsUpdateRequest,
    BellCurveOutliersResponse,
    BellCurveOutlierItem,
    EmployeePerformanceSummary,
    AppraisalCycleSummary,
    RatingScaleSummary,
    RatingScaleListResponse,
    RatingScaleDetailResponse,
    RatingScaleCreate,
    RatingScaleUpdate,
    RatingScaleUsageResponse,
    RatingScaleLookupResponse,
    AppraisalTemplateListResponse,
    AppraisalTemplateLookupResponse,
    AppraisalTemplateDetailResponse,
    AppraisalTemplateCreate,
    AppraisalTemplateUpdate,
    AppraisalTemplateClone,
    AppraisalTemplatePreviewResponse,
    TemplateReorderSectionsRequest,
    TemplateUsageResponse,
    AppraisalSectionCreate,
    AppraisalSectionUpdate,
    AppraisalSectionListResponse,
    AppraisalSectionDetailResponse,
    AppraisalSectionResponseItem
)

router = APIRouter()

class PerformancePermissions:
    MANAGE = "209"
    SETUP = "210"
    READ = "213"
    UPDATE = "214"
    APPROVE = "215"

def _get_org_id(current_user: Union[Organization, Employee]) -> int:
    return current_user.id if isinstance(current_user, Organization) else current_user.organization_id

def _require_permission(db: Session, current_user: Union[Organization, Employee], code: str, action: str):
    if isinstance(current_user, Organization):
        return
    if not deps.has_permission(db, current_user, code):
        raise HTTPException(status_code=403, detail=f"You do not have permission to {action}")

def _get_appraisal_record(db: Session, record_uuid: uuid.UUID, org_id: int) -> AppraisalRecord:
    record = db.query(AppraisalRecord).filter(
        AppraisalRecord.uuid == record_uuid,
        AppraisalRecord.organization_id == org_id
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="Appraisal record not found")
    return record


# ============================================================
# 12. APPRAISAL RECORDS
# ============================================================

@router.get("/appraisal-records", response_model=AppraisalRecordListResponse)
def list_appraisal_records(
    appraisal_cycle_uuid: Optional[uuid.UUID] = None,
    employee_uuid: Optional[uuid.UUID] = None,
    manager_uuid: Optional[uuid.UUID] = None,
    department_uuid: Optional[uuid.UUID] = None,
    status: Optional[AppraisalStatus] = None,
    search: Optional[str] = None,
    sort_by: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PerformancePermissions.READ, "list appraisal records")
    org_id = _get_org_id(current_user)
    query = db.query(AppraisalRecord).filter(AppraisalRecord.organization_id == org_id)

    if appraisal_cycle_uuid:
        query = query.join(AppraisalCycle, AppraisalRecord.appraisal_cycle_id == AppraisalCycle.id).filter(AppraisalCycle.uuid == appraisal_cycle_uuid)
    if employee_uuid:
        query = query.join(Employee, AppraisalRecord.employee_id == Employee.id).filter(Employee.uuid == employee_uuid)
    if manager_uuid:
        query = query.join(Employee, AppraisalRecord.manager_id == Employee.id).filter(Employee.uuid == manager_uuid)
    if department_uuid:
        query = query.join(Employee, AppraisalRecord.employee_id == Employee.id).filter(Employee.department_id == db.query(Department.id).filter(Department.uuid == department_uuid).scalar_subquery())
    if status:
        query = query.filter(AppraisalRecord.status == status)

    if search:
        query = query.join(Employee, AppraisalRecord.employee_id == Employee.id).filter(
            or_(
                Employee.first_name.ilike(f"%{search}%"),
                Employee.last_name.ilike(f"%{search}%"),
                Employee.email.ilike(f"%{search}%")
            )
        )

    if sort_by:
        for s in sort_by.split(","):
            descending = s.startswith("-")
            field = s.lstrip("-")
            if hasattr(AppraisalRecord, field):
                col = getattr(AppraisalRecord, field)
                query = query.order_by(col.desc() if descending else col.asc())
    else:
        query = query.order_by(AppraisalRecord.created_at.desc())

    total_records = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()

    return AppraisalRecordListResponse(
        success=True,
        message="Appraisal records retrieved successfully",
        data=items,
        pagination={
            "total_records": total_records,
            "current_page": page,
            "total_pages": (total_records + limit - 1) // limit if total_records > 0 else 0,
            "page_size": limit
        }
    )

@router.get("/appraisal-records/my-appraisal", response_model=AppraisalRecordResponse)
def get_my_appraisal(
    appraisal_cycle_uuid: Optional[uuid.UUID] = None,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    if isinstance(current_user, Organization):
        raise HTTPException(status_code=400, detail="Organizations do not have appraisal records")
    
    org_id = _get_org_id(current_user)
    query = db.query(AppraisalRecord).filter(
        AppraisalRecord.organization_id == org_id,
        AppraisalRecord.employee_id == current_user.id
    )
    if appraisal_cycle_uuid:
        query = query.join(AppraisalCycle).filter(AppraisalCycle.uuid == appraisal_cycle_uuid)
    else:
        query = query.join(AppraisalCycle).filter(AppraisalCycle.status == CycleStatus.ACTIVE)

    record = query.first()
    if not record:
        raise HTTPException(status_code=404, detail="No appraisal record found for current cycle")
    
    return AppraisalRecordResponse(
        success=True,
        message="My appraisal record retrieved successfully",
        data=record
    )

@router.get("/appraisal-records/team-appraisals", response_model=AppraisalRecordListResponse)
def get_team_appraisals(
    appraisal_cycle_uuid: Optional[uuid.UUID] = None,
    status: Optional[AppraisalStatus] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PerformancePermissions.READ, "view team appraisals")
    org_id = _get_org_id(current_user)
    
    query = db.query(AppraisalRecord).filter(AppraisalRecord.organization_id == org_id)
    if not isinstance(current_user, Organization):
        query = query.filter(AppraisalRecord.manager_id == current_user.id)
        
    if appraisal_cycle_uuid:
        query = query.join(AppraisalCycle).filter(AppraisalCycle.uuid == appraisal_cycle_uuid)
    if status:
        query = query.filter(AppraisalRecord.status == status)

    total_records = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()

    return AppraisalRecordListResponse(
        success=True,
        message="Team appraisals retrieved successfully",
        data=items,
        pagination={
            "total_records": total_records,
            "current_page": page,
            "total_pages": (total_records + limit - 1) // limit if total_records > 0 else 0,
            "page_size": limit
        }
    )

@router.get("/appraisal-records/{record_uuid}", response_model=AppraisalRecordResponse)
def get_appraisal_record(
    record_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PerformancePermissions.READ, "view appraisal record")
    org_id = _get_org_id(current_user)
    record = _get_appraisal_record(db, record_uuid, org_id)
    return AppraisalRecordResponse(
        success=True,
        message="Appraisal record retrieved successfully",
        data=record
    )

@router.patch("/appraisal-records/{record_uuid}/publish", response_model=AppraisalRecordResponse)
def publish_appraisal_record(
    record_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PerformancePermissions.UPDATE, "publish appraisal record")
    org_id = _get_org_id(current_user)
    record = _get_appraisal_record(db, record_uuid, org_id)
    
    record.status = AppraisalStatus.PUBLISHED
    record.published_at = datetime.utcnow()
    record.published_by = current_user.id if not isinstance(current_user, Organization) else None
    
    db.commit()
    db.refresh(record)
    return AppraisalRecordResponse(
        success=True,
        message="Appraisal record published successfully",
        data=record
    )

@router.patch("/appraisal-records/{record_uuid}/acknowledge", response_model=AppraisalRecordResponse)
def acknowledge_appraisal_record(
    record_uuid: uuid.UUID,
    payload: AppraisalRecordAcknowledge,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    if isinstance(current_user, Organization):
        raise HTTPException(status_code=400, detail="Organizations cannot acknowledge appraisals")
        
    org_id = _get_org_id(current_user)
    record = _get_appraisal_record(db, record_uuid, org_id)
    
    if record.employee_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only acknowledge your own appraisal")
        
    record.acknowledged_by_employee = payload.acknowledged if payload.acknowledged is not None else True
    record.employee_acknowledged_at = datetime.utcnow()
    if payload.employee_disagreement_reason:
        record.employee_disagreement_reason = payload.employee_disagreement_reason
    record.status = AppraisalStatus.ACKNOWLEDGED
    
    db.commit()
    db.refresh(record)
    return AppraisalRecordResponse(
        success=True,
        message="Appraisal record acknowledged successfully",
        data=record
    )

@router.patch("/appraisal-records/{record_uuid}/calibrate", response_model=AppraisalRecordResponse)
def calibrate_appraisal_record(
    record_uuid: uuid.UUID,
    payload: AppraisalRecordCalibrate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PerformancePermissions.APPROVE, "calibrate appraisal record")
    org_id = _get_org_id(current_user)
    record = _get_appraisal_record(db, record_uuid, org_id)
    
    if payload.calibrated_score is not None:
        record.calibrated_score = payload.calibrated_score
        record.final_score = payload.calibrated_score
    if payload.final_rating_label:
        record.final_rating_label = payload.final_rating_label
    if payload.calibration_notes:
        record.calibration_notes = payload.calibration_notes
        
    record.calibrated_by = current_user.id if not isinstance(current_user, Organization) else None
    record.calibrated_at = datetime.utcnow()
    record.status = AppraisalStatus.CALIBRATED
    
    db.commit()
    db.refresh(record)
    return AppraisalRecordResponse(
        success=True,
        message="Appraisal record calibrated successfully",
        data=record
    )

@router.patch("/appraisal-records/{record_uuid}/recommend-promotion", response_model=AppraisalRecordResponse)
def recommend_promotion(
    record_uuid: uuid.UUID,
    payload: AppraisalRecordRecommendPromotion,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PerformancePermissions.UPDATE, "recommend promotion")
    org_id = _get_org_id(current_user)
    record = _get_appraisal_record(db, record_uuid, org_id)
    
    if payload.promotion_recommended is not None:
        record.promotion_recommended = payload.promotion_recommended
    if payload.promotion_recommended_to_grade:
        record.promotion_recommended_to_grade = payload.promotion_recommended_to_grade
    if payload.notes:
        record.notes = payload.notes
        
    db.commit()
    db.refresh(record)
    return AppraisalRecordResponse(
        success=True,
        message="Promotion recommendation updated successfully",
        data=record
    )

@router.get("/appraisal-records/{record_uuid}/history", response_model=AppraisalRecordHistoryResponse)
def get_appraisal_history(
    record_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PerformancePermissions.READ, "view history")
    org_id = _get_org_id(current_user)
    record = _get_appraisal_record(db, record_uuid, org_id)
    
    # Construct history items from timestamps
    history = []
    if record.created_at:
        history.append(AppraisalRecordHistoryItem(
            status=AppraisalStatus.NOT_STARTED,
            changed_at=record.created_at,
            changed_by="System",
            notes="Appraisal record initialized"
        ))
    if record.self_appraisal_submitted_at:
        history.append(AppraisalRecordHistoryItem(
            status=AppraisalStatus.SELF_SUBMITTED,
            changed_at=record.self_appraisal_submitted_at,
            changed_by=record.employee.first_name + " " + record.employee.last_name if record.employee else "Employee",
            notes="Self evaluation form submitted"
        ))
    if record.manager_review_submitted_at:
        history.append(AppraisalRecordHistoryItem(
            status=AppraisalStatus.MANAGER_SUBMITTED,
            changed_at=record.manager_review_submitted_at,
            changed_by=record.manager.first_name + " " + record.manager.last_name if record.manager else "Manager",
            notes="Manager review form submitted"
        ))
    if record.calibrated_at:
        history.append(AppraisalRecordHistoryItem(
            status=AppraisalStatus.CALIBRATED,
            changed_at=record.calibrated_at,
            changed_by="Calibrator",
            notes=f"Calibrated final rating: {record.final_rating_label}"
        ))
    if record.published_at:
        history.append(AppraisalRecordHistoryItem(
            status=AppraisalStatus.PUBLISHED,
            changed_at=record.published_at,
            changed_by="HR Administrator",
            notes="Results published to employee"
        ))
    if record.employee_acknowledged_at:
        history.append(AppraisalRecordHistoryItem(
            status=AppraisalStatus.ACKNOWLEDGED,
            changed_at=record.employee_acknowledged_at,
            changed_by=record.employee.first_name + " " + record.employee.last_name if record.employee else "Employee",
            notes="Acknowledged by employee"
        ))
        
    return AppraisalRecordHistoryResponse(
        success=True,
        message="Appraisal history retrieved successfully",
        data=history
    )

@router.post("/appraisal-records/bulk-publish", response_model=BulkPublishResponse)
def bulk_publish_records(
    payload: BulkPublishRequest,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PerformancePermissions.UPDATE, "bulk publish appraisal records")
    org_id = _get_org_id(current_user)
    
    query = db.query(AppraisalRecord).filter(
        AppraisalRecord.organization_id == org_id,
        AppraisalRecord.status.in_([AppraisalStatus.MANAGER_SUBMITTED, AppraisalStatus.CALIBRATED])
    )
    
    if payload.appraisal_cycle_uuid:
        query = query.join(AppraisalCycle).filter(AppraisalCycle.uuid == payload.appraisal_cycle_uuid)
    if payload.department_uuids:
        query = query.join(Employee, AppraisalRecord.employee_id == Employee.id).filter(
            Employee.department_id.in_(db.query(Department.id).filter(Department.uuid.in_(payload.department_uuids)).subquery())
        )
    if payload.rating_labels:
        query = query.filter(AppraisalRecord.final_rating_label.in_(payload.rating_labels))

    records = query.all()
    count = 0
    for record in records:
        record.status = AppraisalStatus.PUBLISHED
        record.published_at = datetime.utcnow()
        record.published_by = current_user.id if not isinstance(current_user, Organization) else None
        count += 1
        
    db.commit()
    return BulkPublishResponse(
        success=True,
        message="Bulk publish complete",
        data={"published_count": count, "skipped_count": len(records) - count}
    )

@router.get("/appraisal-records/{record_uuid}/export")
def export_appraisal_record(
    record_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PerformancePermissions.READ, "export appraisal record")
    org_id = _get_org_id(current_user)
    record = _get_appraisal_record(db, record_uuid, org_id)
    
    # Return a basic dummy pdf file
    return Response(
        content=b"%PDF-1.4 dummy contents for appraisal record",
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=appraisal_record_{record.uuid}.pdf"}
    )

@router.post("/appraisal-cycles/{cycle_uuid}/generate-records", response_model=GenerateRecordsResponse)
def generate_cycle_records(
    cycle_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PerformancePermissions.UPDATE, "generate cycle records")
    org_id = _get_org_id(current_user)
    
    cycle = db.query(AppraisalCycle).filter(AppraisalCycle.uuid == cycle_uuid, AppraisalCycle.organization_id == org_id).first()
    if not cycle:
        raise HTTPException(status_code=404, detail="Appraisal cycle not found")
        
    # Query all active employees in organization
    employees = db.query(Employee).filter(
        Employee.organization_id == org_id,
        Employee.is_active == True
    ).all()
    
    # Simple default template and rating scale lookup
    template = db.query(AppraisalTemplate).filter(AppraisalTemplate.organization_id == org_id).first()
    rating_scale = db.query(RatingScale).filter(RatingScale.organization_id == org_id).first()
    
    if not template or not rating_scale:
        raise HTTPException(status_code=400, detail="Cannot generate records: default template or rating scale is missing.")
        
    created_count = 0
    for emp in employees:
        exists = db.query(AppraisalRecord).filter(
            AppraisalRecord.organization_id == org_id,
            AppraisalRecord.appraisal_cycle_id == cycle.id,
            AppraisalRecord.employee_id == emp.id
        ).first()
        if not exists:
            rec = AppraisalRecord(
                organization_id=org_id,
                appraisal_cycle_id=cycle.id,
                employee_id=emp.id,
                manager_id=emp.manager_id,
                template_id=template.id,
                rating_scale_id=rating_scale.id,
                status=AppraisalStatus.NOT_STARTED
            )
            db.add(rec)
            created_count += 1
            
    db.commit()
    return GenerateRecordsResponse(
        success=True,
        message=f"Successfully generated {created_count} appraisal records for cycle.",
        data={"records_created": created_count}
    )


# ============================================================
# 13. SELF-APPRAISAL
# ============================================================

@router.get("/appraisal-records/{record_uuid}/self-appraisal", response_model=SelfAppraisalResponse)
def get_self_appraisal(
    record_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PerformancePermissions.READ, "view self appraisal")
    org_id = _get_org_id(current_user)
    record = _get_appraisal_record(db, record_uuid, org_id)
    
    sa = db.query(SelfAppraisal).filter(SelfAppraisal.appraisal_record_id == record.id).first()
    if not sa:
        # Create an empty self appraisal draft
        sa = SelfAppraisal(
            appraisal_record_id=record.id,
            employee_id=record.employee_id,
            is_submitted=False
        )
        db.add(sa)
        db.commit()
        db.refresh(sa)
        
    return SelfAppraisalResponse(
        success=True,
        message="Self appraisal retrieved successfully",
        data=sa
    )

@router.put("/appraisal-records/{record_uuid}/self-appraisal", response_model=SelfAppraisalResponse)
def update_self_appraisal(
    record_uuid: uuid.UUID,
    payload: SelfAppraisalUpdate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    org_id = _get_org_id(current_user)
    record = _get_appraisal_record(db, record_uuid, org_id)
    
    if not isinstance(current_user, Organization) and record.employee_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only edit your own self appraisal")
        
    sa = db.query(SelfAppraisal).filter(SelfAppraisal.appraisal_record_id == record.id).first()
    if not sa:
        raise HTTPException(status_code=404, detail="Self appraisal not initialized")
        
    if sa.is_submitted:
        raise HTTPException(status_code=400, detail="Cannot edit a submitted self appraisal")
        
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "answers":
            continue
        setattr(sa, field, value)
        
    sa.last_saved_at = datetime.utcnow()
    sa.draft_version += 1
    
    # Process bulk answers if provided
    if payload.answers:
        for ans_item in payload.answers:
            # Look up question by UUID
            q = db.query(AppraisalQuestion).filter(AppraisalQuestion.uuid == ans_item.question_uuid).first()
            if q:
                existing_ans = db.query(AppraisalAnswer).filter(
                    AppraisalAnswer.appraisal_record_id == record.id,
                    AppraisalAnswer.question_id == q.id,
                    AppraisalAnswer.respondent_type == "self"
                ).first()
                
                goal_id = None
                if ans_item.goal_uuid:
                    goal_id = db.query(EmployeeGoal.id).filter(EmployeeGoal.uuid == ans_item.goal_uuid).scalar()
                    
                competency_id = None
                if ans_item.competency_uuid:
                    competency_id = db.query(CompetencyFramework.id).filter(CompetencyFramework.uuid == ans_item.competency_uuid).scalar()

                if existing_ans:
                    existing_ans.rating_value = ans_item.rating_value
                    existing_ans.text_answer = ans_item.text_answer
                    existing_ans.goal_id = goal_id
                    existing_ans.goal_achievement_percentage = ans_item.goal_achievement_percentage
                    existing_ans.competency_id = competency_id
                    existing_ans.updated_at = datetime.utcnow()
                else:
                    new_ans = AppraisalAnswer(
                        appraisal_record_id=record.id,
                        question_id=q.id,
                        respondent_type="self",
                        respondent_id=record.employee_id,
                        rating_value=ans_item.rating_value,
                        text_answer=ans_item.text_answer,
                        goal_id=goal_id,
                        goal_achievement_percentage=ans_item.goal_achievement_percentage,
                        competency_id=competency_id
                    )
                    db.add(new_ans)
                    
    record.status = AppraisalStatus.SELF_IN_PROGRESS
    db.commit()
    db.refresh(sa)
    return SelfAppraisalResponse(
        success=True,
        message="Self appraisal updated successfully",
        data=sa
    )

@router.post("/appraisal-records/{record_uuid}/self-appraisal/submit", response_model=SelfAppraisalResponse)
def submit_self_appraisal(
    record_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    org_id = _get_org_id(current_user)
    record = _get_appraisal_record(db, record_uuid, org_id)
    
    if not isinstance(current_user, Organization) and record.employee_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only submit your own self appraisal")
        
    sa = db.query(SelfAppraisal).filter(SelfAppraisal.appraisal_record_id == record.id).first()
    if not sa:
        raise HTTPException(status_code=404, detail="Self appraisal not initialized")
        
    sa.is_submitted = True
    sa.submitted_at = datetime.utcnow()
    record.status = AppraisalStatus.SELF_SUBMITTED
    record.self_appraisal_submitted_at = datetime.utcnow()
    
    db.commit()
    db.refresh(sa)
    return SelfAppraisalResponse(
        success=True,
        message="Self appraisal submitted successfully",
        data=sa
    )

@router.post("/appraisal-records/{record_uuid}/self-appraisal/reopen", response_model=SelfAppraisalResponse)
def reopen_self_appraisal(
    record_uuid: uuid.UUID,
    payload: ReopenRequest,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PerformancePermissions.UPDATE, "reopen self appraisal")
    org_id = _get_org_id(current_user)
    record = _get_appraisal_record(db, record_uuid, org_id)
    
    sa = db.query(SelfAppraisal).filter(SelfAppraisal.appraisal_record_id == record.id).first()
    if not sa:
        raise HTTPException(status_code=404, detail="Self appraisal not found")
        
    sa.is_submitted = False
    sa.submitted_at = None
    record.status = AppraisalStatus.SELF_IN_PROGRESS
    
    db.commit()
    db.refresh(sa)
    return SelfAppraisalResponse(
        success=True,
        message="Self appraisal reopened successfully",
        data=sa
    )

@router.get("/appraisal-records/{record_uuid}/self-appraisal/completion", response_model=SelfAppraisalCompletionResponse)
def get_self_appraisal_completion(
    record_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    org_id = _get_org_id(current_user)
    record = _get_appraisal_record(db, record_uuid, org_id)
    
    # Calculate answering counts
    total_q = db.query(AppraisalQuestion).join(AppraisalQuestion.section).filter(
        AppraisalQuestion.is_required == True,
        AppraisalQuestion.section.has(template_id=record.template_id)
    ).count()
    
    answered_q = db.query(AppraisalAnswer).filter(
        AppraisalAnswer.appraisal_record_id == record.id,
        AppraisalAnswer.respondent_type == "self",
        AppraisalAnswer.rating_value.isnot(None)
    ).count()
    
    pct = (answered_q / total_q * 100) if total_q > 0 else 100.0
    return SelfAppraisalCompletionResponse(
        success=True,
        message="Completion percentage retrieved successfully",
        data={
            "completion_percentage": round(pct, 2),
            "answered_count": answered_q,
            "total_required": total_q
        }
    )

@router.get("/appraisal-records/{record_uuid}/self-appraisal/goals", response_model=SelfAppraisalGoalsResponse)
def get_self_appraisal_goals(
    record_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    org_id = _get_org_id(current_user)
    record = _get_appraisal_record(db, record_uuid, org_id)
    
    goals = db.query(EmployeeGoal).filter(
        EmployeeGoal.organization_id == org_id,
        EmployeeGoal.employee_id == record.employee_id,
        EmployeeGoal.appraisal_cycle_id == record.appraisal_cycle_id
    ).all()
    
    return SelfAppraisalGoalsResponse(
        success=True,
        message="Goals retrieved successfully",
        data=goals
    )

@router.get("/self-appraisals/pending", response_model=PendingSelfAppraisalsListResponse)
def get_pending_self_appraisals(
    appraisal_cycle_uuid: Optional[uuid.UUID] = None,
    department_uuid: Optional[uuid.UUID] = None,
    manager_uuid: Optional[uuid.UUID] = None,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PerformancePermissions.READ, "list pending self appraisals")
    org_id = _get_org_id(current_user)
    
    query = db.query(AppraisalRecord).filter(
        AppraisalRecord.organization_id == org_id,
        AppraisalRecord.status.in_([AppraisalStatus.NOT_STARTED, AppraisalStatus.SELF_IN_PROGRESS])
    )
    
    if appraisal_cycle_uuid:
        query = query.join(AppraisalCycle).filter(AppraisalCycle.uuid == appraisal_cycle_uuid)
    if department_uuid:
        query = query.join(Employee, AppraisalRecord.employee_id == Employee.id).filter(
            Employee.department_id == db.query(Department.id).filter(Department.uuid == department_uuid).scalar_subquery()
        )
    if manager_uuid:
        query = query.filter(AppraisalRecord.manager_id == db.query(Employee.id).filter(Employee.uuid == manager_uuid).scalar_subquery())
        
    records = query.all()
    data = []
    for r in records:
        data.append(PendingSelfAppraisalItem(
            employee=r.employee,
            manager=r.manager,
            appraisal_cycle=r.appraisal_cycle,
            deadline=r.appraisal_cycle.self_appraisal_end if r.appraisal_cycle else None,
            days_remaining=(r.appraisal_cycle.self_appraisal_end - date.today()).days if r.appraisal_cycle and r.appraisal_cycle.self_appraisal_end else 0
        ))
        
    return PendingSelfAppraisalsListResponse(
        success=True,
        message="Pending self appraisals retrieved successfully",
        data=data
    )


# ============================================================
# 14. MANAGER APPRAISAL
# ============================================================

@router.get("/appraisal-records/{record_uuid}/manager-appraisal", response_model=ManagerAppraisalResponse)
def get_manager_appraisal(
    record_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PerformancePermissions.READ, "view manager appraisal")
    org_id = _get_org_id(current_user)
    record = _get_appraisal_record(db, record_uuid, org_id)
    
    ma = db.query(ManagerAppraisal).filter(ManagerAppraisal.appraisal_record_id == record.id).first()
    if not ma:
        # Create draft
        ma = ManagerAppraisal(
            appraisal_record_id=record.id,
            manager_id=record.manager_id or 0,
            employee_id=record.employee_id,
            is_submitted=False
        )
        db.add(ma)
        db.commit()
        db.refresh(ma)
        
    return ManagerAppraisalResponse(
        success=True,
        message="Manager appraisal retrieved successfully",
        data=ma
    )

@router.put("/appraisal-records/{record_uuid}/manager-appraisal", response_model=ManagerAppraisalResponse)
def update_manager_appraisal(
    record_uuid: uuid.UUID,
    payload: ManagerAppraisalUpdate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    org_id = _get_org_id(current_user)
    record = _get_appraisal_record(db, record_uuid, org_id)
    
    if not isinstance(current_user, Organization) and record.manager_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only evaluate your direct reports")
        
    ma = db.query(ManagerAppraisal).filter(ManagerAppraisal.appraisal_record_id == record.id).first()
    if not ma:
        raise HTTPException(status_code=404, detail="Manager appraisal not initialized")
        
    if ma.is_submitted:
        raise HTTPException(status_code=400, detail="Cannot edit a submitted manager appraisal")
        
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "answers":
            continue
        setattr(ma, field, value)
        
    ma.last_saved_at = datetime.utcnow()
    
    if payload.answers:
        for ans_item in payload.answers:
            q = db.query(AppraisalQuestion).filter(AppraisalQuestion.uuid == ans_item.question_uuid).first()
            if q:
                existing_ans = db.query(AppraisalAnswer).filter(
                    AppraisalAnswer.appraisal_record_id == record.id,
                    AppraisalAnswer.question_id == q.id,
                    AppraisalAnswer.respondent_type == "manager"
                ).first()
                
                goal_id = None
                if ans_item.goal_uuid:
                    goal_id = db.query(EmployeeGoal.id).filter(EmployeeGoal.uuid == ans_item.goal_uuid).scalar()
                    
                competency_id = None
                if ans_item.competency_uuid:
                    competency_id = db.query(CompetencyFramework.id).filter(CompetencyFramework.uuid == ans_item.competency_uuid).scalar()

                if existing_ans:
                    existing_ans.rating_value = ans_item.rating_value
                    existing_ans.text_answer = ans_item.text_answer
                    existing_ans.goal_id = goal_id
                    existing_ans.goal_achievement_percentage = ans_item.goal_achievement_percentage
                    existing_ans.competency_id = competency_id
                    existing_ans.updated_at = datetime.utcnow()
                else:
                    new_ans = AppraisalAnswer(
                        appraisal_record_id=record.id,
                        question_id=q.id,
                        respondent_type="manager",
                        respondent_id=record.manager_id or 0,
                        rating_value=ans_item.rating_value,
                        text_answer=ans_item.text_answer,
                        goal_id=goal_id,
                        goal_achievement_percentage=ans_item.goal_achievement_percentage,
                        competency_id=competency_id
                    )
                    db.add(new_ans)
                    
    record.status = AppraisalStatus.MANAGER_IN_PROGRESS
    db.commit()
    db.refresh(ma)
    return ManagerAppraisalResponse(
        success=True,
        message="Manager appraisal updated successfully",
        data=ma
    )

@router.post("/appraisal-records/{record_uuid}/manager-appraisal/submit", response_model=ManagerAppraisalResponse)
def submit_manager_appraisal(
    record_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    org_id = _get_org_id(current_user)
    record = _get_appraisal_record(db, record_uuid, org_id)
    
    if not isinstance(current_user, Organization) and record.manager_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only evaluate your direct reports")
        
    ma = db.query(ManagerAppraisal).filter(ManagerAppraisal.appraisal_record_id == record.id).first()
    if not ma:
        raise HTTPException(status_code=404, detail="Manager appraisal not initialized")
        
    ma.is_submitted = True
    ma.submitted_at = datetime.utcnow()
    record.status = AppraisalStatus.MANAGER_SUBMITTED
    record.manager_review_submitted_at = datetime.utcnow()
    
    db.commit()
    db.refresh(ma)
    return ManagerAppraisalResponse(
        success=True,
        message="Manager appraisal submitted successfully",
        data=ma
    )

@router.post("/appraisal-records/{record_uuid}/manager-appraisal/reopen", response_model=ManagerAppraisalResponse)
def reopen_manager_appraisal(
    record_uuid: uuid.UUID,
    payload: ReopenRequest,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PerformancePermissions.UPDATE, "reopen manager appraisal")
    org_id = _get_org_id(current_user)
    record = _get_appraisal_record(db, record_uuid, org_id)
    
    ma = db.query(ManagerAppraisal).filter(ManagerAppraisal.appraisal_record_id == record.id).first()
    if not ma:
        raise HTTPException(status_code=404, detail="Manager appraisal not found")
        
    ma.is_submitted = False
    ma.submitted_at = None
    record.status = AppraisalStatus.MANAGER_IN_PROGRESS
    
    db.commit()
    db.refresh(ma)
    return ManagerAppraisalResponse(
        success=True,
        message="Manager appraisal reopened successfully",
        data=ma
    )

@router.get("/manager-appraisals/pending", response_model=PendingManagerAppraisalsListResponse)
def get_pending_manager_appraisals(
    appraisal_cycle_uuid: Optional[uuid.UUID] = None,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PerformancePermissions.READ, "list pending manager appraisals")
    org_id = _get_org_id(current_user)
    
    query = db.query(AppraisalRecord).filter(
        AppraisalRecord.organization_id == org_id,
        AppraisalRecord.status == AppraisalStatus.SELF_SUBMITTED
    )
    if not isinstance(current_user, Organization):
        query = query.filter(AppraisalRecord.manager_id == current_user.id)
        
    if appraisal_cycle_uuid:
        query = query.join(AppraisalCycle).filter(AppraisalCycle.uuid == appraisal_cycle_uuid)
        
    records = query.all()
    data = []
    for r in records:
        data.append(PendingManagerAppraisalItem(
            employee=r.employee,
            appraisal_cycle=r.appraisal_cycle,
            deadline=r.appraisal_cycle.manager_review_end if r.appraisal_cycle else None,
            days_remaining=(r.appraisal_cycle.manager_review_end - date.today()).days if r.appraisal_cycle and r.appraisal_cycle.manager_review_end else 0
        ))
        
    return PendingManagerAppraisalsListResponse(
        success=True,
        message="Pending manager appraisals retrieved successfully",
        data=data
    )

@router.get("/appraisal-records/{record_uuid}/compare-scores", response_model=ScoreComparisonResponse)
def compare_appraisal_scores(
    record_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PerformancePermissions.READ, "compare appraisal scores")
    org_id = _get_org_id(current_user)
    record = _get_appraisal_record(db, record_uuid, org_id)
    
    # Comparison of scores per section
    sections = [
        ScoreComparisonSection(
            title="Goals Performance",
            self_score=record.self_goal_score,
            manager_score=record.manager_goal_score,
            delta=(record.manager_goal_score - record.self_goal_score) if (record.manager_goal_score is not None and record.self_goal_score is not None) else None
        ),
        ScoreComparisonSection(
            title="Competencies Performance",
            self_score=record.self_competency_score,
            manager_score=record.manager_competency_score,
            delta=(record.manager_competency_score - record.self_competency_score) if (record.manager_competency_score is not None and record.self_competency_score is not None) else None
        )
    ]
    return ScoreComparisonResponse(
        success=True,
        message="Score comparison retrieved successfully",
        data=sections
    )

@router.post("/appraisal-records/{record_uuid}/override-score", response_model=AppraisalRecordResponse)
def manager_override_score(
    record_uuid: uuid.UUID,
    payload: ManagerOverrideScoreRequest,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PerformancePermissions.APPROVE, "override appraisal score")
    org_id = _get_org_id(current_user)
    record = _get_appraisal_record(db, record_uuid, org_id)
    
    record.manager_overall_score = payload.manager_overall_score
    record.manager_rating_label = payload.manager_rating_label
    record.final_score = payload.manager_overall_score
    record.final_rating_label = payload.manager_rating_label
    record.notes = payload.override_reason
    
    db.commit()
    db.refresh(record)
    return AppraisalRecordResponse(
        success=True,
        message="Overall appraisal score overridden successfully",
        data=record
    )


# ============================================================
# 15. APPRAISAL ANSWERS
# ============================================================

@router.get("/appraisal-records/{record_uuid}/answers", response_model=AppraisalAnswerListResponse)
def get_appraisal_answers(
    record_uuid: uuid.UUID,
    respondent_type: Optional[str] = None,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PerformancePermissions.READ, "view appraisal answers")
    org_id = _get_org_id(current_user)
    record = _get_appraisal_record(db, record_uuid, org_id)
    
    query = db.query(AppraisalAnswer).filter(AppraisalAnswer.appraisal_record_id == record.id)
    if respondent_type:
        query = query.filter(AppraisalAnswer.respondent_type == respondent_type)
        
    return AppraisalAnswerListResponse(
        success=True,
        message="Appraisal answers retrieved successfully",
        data=query.all()
    )

@router.post("/appraisal-records/{record_uuid}/answers", response_model=AppraisalAnswerResponse)
def create_appraisal_answer(
    record_uuid: uuid.UUID,
    payload: AppraisalAnswerCreate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PerformancePermissions.UPDATE, "submit appraisal answer")
    org_id = _get_org_id(current_user)
    record = _get_appraisal_record(db, record_uuid, org_id)
    
    q = db.query(AppraisalQuestion).filter(AppraisalQuestion.uuid == payload.question_uuid).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")
        
    goal_id = None
    if payload.goal_uuid:
        goal_id = db.query(EmployeeGoal.id).filter(EmployeeGoal.uuid == payload.goal_uuid).scalar()
        
    competency_id = None
    if payload.competency_uuid:
        competency_id = db.query(CompetencyFramework.id).filter(CompetencyFramework.uuid == payload.competency_uuid).scalar()
        
    ans = AppraisalAnswer(
        appraisal_record_id=record.id,
        question_id=q.id,
        respondent_type=payload.respondent_type,
        respondent_id=current_user.id if not isinstance(current_user, Organization) else 0,
        rating_value=payload.rating_value,
        rating_label=payload.rating_label,
        text_answer=payload.text_answer,
        selected_choices=payload.selected_choices,
        goal_id=goal_id,
        goal_achievement_percentage=payload.goal_achievement_percentage,
        competency_id=competency_id
    )
    db.add(ans)
    db.commit()
    db.refresh(ans)
    return AppraisalAnswerResponse(
        success=True,
        message="Answer created successfully",
        data=ans
    )

@router.post("/appraisal-records/{record_uuid}/answers/bulk", response_model=AppraisalAnswerBulkResponse)
def bulk_create_appraisal_answers(
    record_uuid: uuid.UUID,
    payload: AppraisalAnswerBulkRequest,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PerformancePermissions.UPDATE, "submit bulk answers")
    org_id = _get_org_id(current_user)
    record = _get_appraisal_record(db, record_uuid, org_id)
    
    count = 0
    for item in payload.answers:
        q = db.query(AppraisalQuestion).filter(AppraisalQuestion.uuid == item.question_uuid).first()
        if q:
            existing = db.query(AppraisalAnswer).filter(
                AppraisalAnswer.appraisal_record_id == record.id,
                AppraisalAnswer.question_id == q.id,
                AppraisalAnswer.respondent_type == payload.respondent_type
            ).first()
            
            goal_id = None
            if item.goal_uuid:
                goal_id = db.query(EmployeeGoal.id).filter(EmployeeGoal.uuid == item.goal_uuid).scalar()
                
            competency_id = None
            if item.competency_uuid:
                competency_id = db.query(CompetencyFramework.id).filter(CompetencyFramework.uuid == item.competency_uuid).scalar()

            if existing:
                existing.rating_value = item.rating_value
                existing.text_answer = item.text_answer
                existing.goal_id = goal_id
                existing.goal_achievement_percentage = item.goal_achievement_percentage
                existing.competency_id = competency_id
                existing.updated_at = datetime.utcnow()
            else:
                ans = AppraisalAnswer(
                    appraisal_record_id=record.id,
                    question_id=q.id,
                    respondent_type=payload.respondent_type,
                    respondent_id=current_user.id if not isinstance(current_user, Organization) else 0,
                    rating_value=item.rating_value,
                    text_answer=item.text_answer,
                    goal_id=goal_id,
                    goal_achievement_percentage=item.goal_achievement_percentage,
                    competency_id=competency_id
                )
                db.add(ans)
            count += 1
            
    db.commit()
    return AppraisalAnswerBulkResponse(
        success=True,
        message=f"Successfully saved {count} answers",
        data={"saved_count": count}
    )


# ============================================================
# 16. CALIBRATION
# ============================================================

@router.get("/calibrations", response_model=AppraisalCalibrationListResponse)
def list_calibrations(
    appraisal_cycle_uuid: Optional[uuid.UUID] = None,
    department_uuid: Optional[uuid.UUID] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PerformancePermissions.READ, "list calibrations")
    org_id = _get_org_id(current_user)
    query = db.query(AppraisalCalibration).filter(AppraisalCalibration.organization_id == org_id)
    
    if appraisal_cycle_uuid:
        query = query.join(AppraisalCycle).filter(AppraisalCycle.uuid == appraisal_cycle_uuid)
    if department_uuid:
        query = query.join(Department).filter(Department.uuid == department_uuid)
    if search:
        query = query.filter(AppraisalCalibration.name.ilike(f"%{search}%"))
        
    total_records = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()
    
    return AppraisalCalibrationListResponse(
        success=True,
        message="Calibration sessions retrieved successfully",
        data=items,
        pagination={
            "total_records": total_records,
            "current_page": page,
            "total_pages": (total_records + limit - 1) // limit if total_records > 0 else 0,
            "page_size": limit
        }
    )

@router.post("/calibrations", response_model=AppraisalCalibrationResponse)
def create_calibration(
    payload: AppraisalCalibrationCreate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PerformancePermissions.UPDATE, "create calibration session")
    org_id = _get_org_id(current_user)
    
    cycle_id = db.query(AppraisalCycle.id).filter(AppraisalCycle.uuid == payload.appraisal_cycle_uuid, AppraisalCycle.organization_id == org_id).scalar()
    if not cycle_id:
        raise HTTPException(status_code=404, detail="Appraisal cycle not found")
        
    dept_id = None
    if payload.department_uuid:
        dept_id = db.query(Department.id).filter(Department.uuid == payload.department_uuid, Department.organization_id == org_id).scalar()
        
    facilitator_id = db.query(Employee.id).filter(Employee.uuid == payload.facilitator_uuid, Employee.organization_id == org_id).scalar()
    if not facilitator_id:
        raise HTTPException(status_code=400, detail="Facilitator not found")
        
    cal = AppraisalCalibration(
        organization_id=org_id,
        appraisal_cycle_id=cycle_id,
        name=payload.name,
        department_id=dept_id,
        scheduled_date=payload.scheduled_date,
        facilitator_id=facilitator_id,
        target_distribution=payload.target_distribution,
        status="SCHEDULED",
        created_by=current_user.id if not isinstance(current_user, Organization) else 0
    )
    db.add(cal)
    db.commit()
    db.refresh(cal)
    return AppraisalCalibrationResponse(
        success=True,
        message="Calibration session scheduled successfully",
        data=cal
    )

@router.get("/calibrations/{calibration_uuid}", response_model=AppraisalCalibrationResponse)
def get_calibration(
    calibration_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PerformancePermissions.READ, "view calibration")
    org_id = _get_org_id(current_user)
    cal = db.query(AppraisalCalibration).filter(AppraisalCalibration.uuid == calibration_uuid, AppraisalCalibration.organization_id == org_id).first()
    if not cal:
        raise HTTPException(status_code=404, detail="Calibration session not found")
    return AppraisalCalibrationResponse(
        success=True,
        message="Calibration session retrieved successfully",
        data=cal
    )

@router.put("/calibrations/{calibration_uuid}", response_model=AppraisalCalibrationResponse)
def update_calibration(
    calibration_uuid: uuid.UUID,
    payload: AppraisalCalibrationUpdate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PerformancePermissions.UPDATE, "update calibration")
    org_id = _get_org_id(current_user)
    cal = db.query(AppraisalCalibration).filter(AppraisalCalibration.uuid == calibration_uuid, AppraisalCalibration.organization_id == org_id).first()
    if not cal:
        raise HTTPException(status_code=404, detail="Calibration session not found")
        
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "facilitator_uuid":
            cal.facilitator_id = db.query(Employee.id).filter(Employee.uuid == value).scalar() or cal.facilitator_id
        else:
            setattr(cal, field, value)
            
    db.commit()
    db.refresh(cal)
    return AppraisalCalibrationResponse(
        success=True,
        message="Calibration session updated successfully",
        data=cal
    )

@router.delete("/calibrations/{calibration_uuid}")
def delete_calibration(
    calibration_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PerformancePermissions.UPDATE, "delete calibration")
    org_id = _get_org_id(current_user)
    cal = db.query(AppraisalCalibration).filter(AppraisalCalibration.uuid == calibration_uuid, AppraisalCalibration.organization_id == org_id).first()
    if not cal:
        raise HTTPException(status_code=404, detail="Calibration session not found")
        
    db.delete(cal)
    db.commit()
    return {"success": True, "message": "Calibration session deleted successfully"}

@router.patch("/calibrations/{calibration_uuid}/start", response_model=AppraisalCalibrationResponse)
def start_calibration_session(
    calibration_uuid: uuid.UUID,
    payload: CalibrationStartRequest,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PerformancePermissions.APPROVE, "start calibration")
    org_id = _get_org_id(current_user)
    cal = db.query(AppraisalCalibration).filter(AppraisalCalibration.uuid == calibration_uuid, AppraisalCalibration.organization_id == org_id).first()
    if not cal:
        raise HTTPException(status_code=404, detail="Calibration session not found")
        
    cal.status = "IN_PROGRESS"
    cal.conducted_date = payload.conducted_date or datetime.utcnow()
    db.commit()
    db.refresh(cal)
    return AppraisalCalibrationResponse(
        success=True,
        message="Calibration session started successfully",
        data=cal
    )

@router.patch("/calibrations/{calibration_uuid}/complete", response_model=AppraisalCalibrationResponse)
def complete_calibration_session(
    calibration_uuid: uuid.UUID,
    payload: CalibrationCompleteRequest,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PerformancePermissions.APPROVE, "complete calibration")
    org_id = _get_org_id(current_user)
    cal = db.query(AppraisalCalibration).filter(AppraisalCalibration.uuid == calibration_uuid, AppraisalCalibration.organization_id == org_id).first()
    if not cal:
        raise HTTPException(status_code=404, detail="Calibration session not found")
        
    cal.status = "COMPLETED"
    if payload.session_notes:
        cal.session_notes = payload.session_notes
    if payload.meeting_minutes:
        cal.meeting_minutes = payload.meeting_minutes
    if payload.actual_distribution:
        cal.actual_distribution = payload.actual_distribution
        
    db.commit()
    db.refresh(cal)
    return AppraisalCalibrationResponse(
        success=True,
        message="Calibration session completed successfully",
        data=cal
    )

@router.get("/calibrations/{calibration_uuid}/employees", response_model=CalibrationEmployeeListResponse)
def get_calibration_employees(
    calibration_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PerformancePermissions.READ, "view calibration employees")
    org_id = _get_org_id(current_user)
    cal = db.query(AppraisalCalibration).filter(AppraisalCalibration.uuid == calibration_uuid, AppraisalCalibration.organization_id == org_id).first()
    if not cal:
        raise HTTPException(status_code=404, detail="Calibration session not found")
        
    # Get all employees in the department or organization
    query = db.query(AppraisalRecord).filter(
        AppraisalRecord.organization_id == org_id,
        AppraisalRecord.appraisal_cycle_id == cal.appraisal_cycle_id
    )
    if cal.department_id:
        query = query.join(Employee).filter(Employee.department_id == cal.department_id)
        
    records = query.all()
    res = []
    for r in records:
        res.append(CalibrationEmployeeSchema(
            employee=r.employee,
            self_overall_score=r.self_overall_score,
            manager_overall_score=r.manager_overall_score,
            calibrated_score=r.calibrated_score,
            final_rating_label=r.final_rating_label
        ))
    return CalibrationEmployeeListResponse(
        success=True,
        message="Calibration employees retrieved successfully",
        data=res
    )

@router.get("/calibrations/{calibration_uuid}/distribution", response_model=CalibrationDistributionResponse)
def get_calibration_distribution(
    calibration_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PerformancePermissions.READ, "view calibration distribution")
    org_id = _get_org_id(current_user)
    cal = db.query(AppraisalCalibration).filter(AppraisalCalibration.uuid == calibration_uuid, AppraisalCalibration.organization_id == org_id).first()
    if not cal:
        raise HTTPException(status_code=404, detail="Calibration session not found")
        
    # Aggregate rating label counts for this calibration session
    query = db.query(
        AppraisalRecord.final_rating_label,
        func.count(AppraisalRecord.id)
    ).filter(
        AppraisalRecord.organization_id == org_id,
        AppraisalRecord.appraisal_cycle_id == cal.appraisal_cycle_id
    )
    if cal.department_id:
        query = query.join(Employee).filter(Employee.department_id == cal.department_id)
        
    groups = query.group_by(AppraisalRecord.final_rating_label).all()
    total = sum(g[1] for g in groups)
    
    target_dist = cal.target_distribution or {}
    items = []
    for label, count in groups:
        if not label:
            continue
        tgt_pct = target_dist.get(label, 0.0)
        act_pct = (count / total * 100.0) if total > 0 else 0.0
        items.append(CalibrationDistributionItem(
            label=label,
            target_pct=tgt_pct,
            target_count=int(total * tgt_pct / 100),
            actual_count=count,
            actual_pct=round(act_pct, 2),
            variance=round(act_pct - tgt_pct, 2)
        ))
        
    return CalibrationDistributionResponse(
        success=True,
        message="Calibration distribution computed successfully",
        data=items
    )

@router.post("/calibrations/{calibration_uuid}/participants", response_model=CalibrationParticipantsResponse)
def add_calibration_participants(
    calibration_uuid: uuid.UUID,
    payload: CalibrationParticipantsCreate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PerformancePermissions.UPDATE, "add calibration participants")
    org_id = _get_org_id(current_user)
    cal = db.query(AppraisalCalibration).filter(AppraisalCalibration.uuid == calibration_uuid, AppraisalCalibration.organization_id == org_id).first()
    if not cal:
        raise HTTPException(status_code=404, detail="Calibration session not found")
        
    added = []
    if payload.participants:
        for p in payload.participants:
            emp_id = db.query(Employee.id).filter(Employee.uuid == p.employee_uuid, Employee.organization_id == org_id).scalar()
            if emp_id:
                # Add to DB
                exists = db.query(CalibrationParticipant).filter(
                    CalibrationParticipant.calibration_id == cal.id,
                    CalibrationParticipant.participant_id == emp_id
                ).first()
                if not exists:
                    part = CalibrationParticipant(
                        calibration_id=cal.id,
                        participant_id=emp_id,
                        role=p.role
                    )
                    db.add(part)
                added.append(p)
                
    db.commit()
    return CalibrationParticipantsResponse(
        success=True,
        message=f"Added {len(added)} participants successfully",
        data=added
    )


# ============================================================
# 17. BELL CURVE DISTRIBUTION
# ============================================================

@router.get("/bell-curves", response_model=BellCurveDistributionResponse)
def get_bell_curve_distributions(
    appraisal_cycle_uuid: uuid.UUID,
    department_uuid: Optional[uuid.UUID] = None,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PerformancePermissions.READ, "view bell curves")
    org_id = _get_org_id(current_user)
    
    cycle = db.query(AppraisalCycle).filter(AppraisalCycle.uuid == appraisal_cycle_uuid, AppraisalCycle.organization_id == org_id).first()
    if not cycle:
        raise HTTPException(status_code=404, detail="Appraisal cycle not found")
        
    dept_id = None
    if department_uuid:
        dept_id = db.query(Department.id).filter(Department.uuid == department_uuid, Department.organization_id == org_id).scalar()
        
    distributions = db.query(BellCurveDistribution).filter(
        BellCurveDistribution.appraisal_cycle_id == cycle.id,
        BellCurveDistribution.department_id == dept_id
    ).all()
    
    res = []
    for d in distributions:
        res.append(BellCurveDistributionItem(
            rating_label=d.rating_label,
            target_percentage=float(d.target_percentage),
            target_count=d.target_count or 0,
            actual_count=d.actual_count or 0,
            actual_percentage=float(d.actual_percentage or 0.0),
            variance=float(d.variance or 0.0)
        ))
        
    return BellCurveDistributionResponse(
        success=True,
        message="Bell curve distributions retrieved successfully",
        data=res
    )

@router.post("/bell-curves/compute", response_model=BellCurveDistributionResponse)
def compute_bell_curve(
    payload: BellCurveComputeRequest,
    appraisal_cycle_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PerformancePermissions.APPROVE, "compute bell curves")
    org_id = _get_org_id(current_user)
    
    cycle = db.query(AppraisalCycle).filter(AppraisalCycle.uuid == appraisal_cycle_uuid, AppraisalCycle.organization_id == org_id).first()
    if not cycle:
        raise HTTPException(status_code=404, detail="Appraisal cycle not found")
        
    dept_id = None
    if payload.department_uuid:
        dept_id = db.query(Department.id).filter(Department.uuid == payload.department_uuid, Department.organization_id == org_id).scalar()
        
    # Aggregate actual counts
    query = db.query(
        AppraisalRecord.final_rating_label,
        func.count(AppraisalRecord.id)
    ).filter(
        AppraisalRecord.organization_id == org_id,
        AppraisalRecord.appraisal_cycle_id == cycle.id
    )
    if dept_id:
        query = query.join(Employee).filter(Employee.department_id == dept_id)
        
    groups = query.group_by(AppraisalRecord.final_rating_label).all()
    total = sum(g[1] for g in groups)
    
    target_dist = cycle.bell_curve_config or {}
    
    # Save computed distributions
    # First delete existing
    db.query(BellCurveDistribution).filter(
        BellCurveDistribution.appraisal_cycle_id == cycle.id,
        BellCurveDistribution.department_id == dept_id
    ).delete()
    
    res = []
    for label, count in groups:
        if not label:
            continue
        tgt_pct = target_dist.get(label, 0.0)
        act_pct = (count / total * 100.0) if total > 0 else 0.0
        var = act_pct - tgt_pct
        
        dist = BellCurveDistribution(
            appraisal_cycle_id=cycle.id,
            department_id=dept_id,
            rating_label=label,
            target_percentage=Decimal(str(tgt_pct)),
            target_count=int(total * tgt_pct / 100),
            actual_count=count,
            actual_percentage=Decimal(str(round(act_pct, 2))),
            variance=Decimal(str(round(var, 2))),
            computed_at=datetime.utcnow()
        )
        db.add(dist)
        
        res.append(BellCurveDistributionItem(
            rating_label=label,
            target_percentage=tgt_pct,
            target_count=int(total * tgt_pct / 100),
            actual_count=count,
            actual_percentage=round(act_pct, 2),
            variance=round(var, 2)
        ))
        
    db.commit()
    return BellCurveDistributionResponse(
        success=True,
        message="Bell curve distribution computed successfully",
        data=res
    )

@router.put("/bell-curves/targets")
def update_bell_curve_targets(
    payload: BellCurveTargetsUpdateRequest,
    appraisal_cycle_uuid: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PerformancePermissions.APPROVE, "update bell curve targets")
    org_id = _get_org_id(current_user)
    
    cycle = db.query(AppraisalCycle).filter(AppraisalCycle.uuid == appraisal_cycle_uuid, AppraisalCycle.organization_id == org_id).first()
    if not cycle:
        raise HTTPException(status_code=404, detail="Appraisal cycle not found")
        
    if payload.distribution:
        config = {item.rating_label: float(item.target_percentage) for item in payload.distribution}
        cycle.bell_curve_config = config
        db.commit()
        
    return {"success": True, "message": "Bell curve targets updated successfully"}

@router.get("/bell-curves/outliers", response_model=BellCurveOutliersResponse)
def get_bell_curve_outliers(
    appraisal_cycle_uuid: uuid.UUID,
    department_uuid: Optional[uuid.UUID] = None,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user),
    current_org: Organization = Depends(deps.get_current_org)
):
    _require_permission(db, current_user, PerformancePermissions.READ, "view outliers")
    org_id = _get_org_id(current_user)
    
    cycle = db.query(AppraisalCycle).filter(AppraisalCycle.uuid == appraisal_cycle_uuid, AppraisalCycle.organization_id == org_id).first()
    if not cycle:
        raise HTTPException(status_code=404, detail="Appraisal cycle not found")
        
    # Outliers: Appraisal records where Self Rating differs significantly from Manager Rating (e.g. delta > 1.5)
    query = db.query(AppraisalRecord).filter(
        AppraisalRecord.organization_id == org_id,
        AppraisalRecord.appraisal_cycle_id == cycle.id,
        AppraisalRecord.self_overall_score.isnot(None),
        AppraisalRecord.manager_overall_score.isnot(None)
    )
    if department_uuid:
        query = query.join(Employee).filter(Employee.department_id == db.query(Department.id).filter(Department.uuid == department_uuid).scalar_subquery())
        
    records = query.all()
    outliers = []
    for r in records:
        diff = abs(r.manager_overall_score - r.self_overall_score)
        if diff >= 1.5:
            outliers.append(BellCurveOutlierItem(
                employee=r.employee,
                self_overall_score=r.self_overall_score,
                manager_overall_score=r.manager_overall_score,
                variance=diff
            ))
            
    return BellCurveOutliersResponse(
        success=True,
        message="Bell curve outliers retrieved successfully",
        data=outliers
    )


# ============================================================
# TEMPLATES ROUTER & ENDPOINTS
# ============================================================

templates_router = APIRouter()

@templates_router.get("/", response_model=AppraisalTemplateListResponse)
def get_templates(
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    is_default: Optional[bool] = None,
    applicable_department: Optional[str] = None,
    sort_by: Optional[str] = Query("created_at", description="Field to sort by"),
    sort_order: Optional[str] = Query("desc", pattern="^(asc|desc)$", description="Sort order (asc or desc)"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, "217", "list appraisal templates")
    org_id = _get_org_id(current_user)
    
    query = db.query(AppraisalTemplate).filter(AppraisalTemplate.organization_id == org_id)
    
    if search:
        query = query.filter(
            or_(
                AppraisalTemplate.name.ilike(f"%{search}%"),
                AppraisalTemplate.description.ilike(f"%{search}%")
            )
        )
        
    if is_active is not None:
        query = query.filter(AppraisalTemplate.is_active == is_active)
    if is_default is not None:
        query = query.filter(AppraisalTemplate.is_default == is_default)
    if applicable_department:
        query = query.filter(func.json_contains(AppraisalTemplate.applicable_departments, func.json_quote(applicable_department)))
        
    total = query.count()
    
    if sort_by and hasattr(AppraisalTemplate, sort_by):
        column = getattr(AppraisalTemplate, sort_by)
        if sort_order == "desc":
            query = query.order_by(column.desc())
        else:
            query = query.order_by(column.asc())
    else:
        query = query.order_by(AppraisalTemplate.created_at.desc())
        
    items = query.offset((page - 1) * limit).limit(limit).all()
    
    roles_dict = {}
    depts_dict = {}
    for item in items:
        for r_uuid in (item.applicable_roles or []):
            roles_dict[str(r_uuid)] = None
        for d_uuid in (item.applicable_departments or []):
            depts_dict[str(d_uuid)] = None

    if roles_dict:
        roles_db = db.query(Role).filter(Role.uuid.in_(roles_dict.keys()), Role.organization_id == org_id).all()
        for r in roles_db:
            roles_dict[str(r.uuid)] = {"uuid": r.uuid, "name": r.role_name}
    
    if depts_dict:
        depts_db = db.query(Department).filter(Department.uuid.in_(depts_dict.keys()), Department.organization_id == org_id).all()
        for d in depts_db:
            depts_dict[str(d.uuid)] = {"uuid": d.uuid, "name": d.department_name}
            
    hydrated_items = []
    for item in items:
        item_dict = {
            "uuid": item.uuid,
            "name": item.name,
            "description": item.description,
            "is_active": item.is_active,
            "is_default": item.is_default,
            "applicable_roles": [roles_dict.get(str(r_uuid)) for r_uuid in (item.applicable_roles or []) if roles_dict.get(str(r_uuid))],
            "applicable_departments": [depts_dict.get(str(d_uuid)) for d_uuid in (item.applicable_departments or []) if depts_dict.get(str(d_uuid))],
            "applicable_grades": item.applicable_grades or [],
            "goal_section_weight": item.goal_section_weight,
            "competency_section_weight": item.competency_section_weight,
            "behavior_section_weight": item.behavior_section_weight,
            "other_section_weight": item.other_section_weight,
            "self_appraisal_enabled": item.self_appraisal_enabled,
            "self_rating_visible_to_manager": item.self_rating_visible_to_manager,
            "employee_comments_enabled": item.employee_comments_enabled,
            "manager_override_enabled": item.manager_override_enabled,
            "final_rating_formula": item.final_rating_formula,
            "version": item.version,
            "rating_scale": item.rating_scale,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        }
        hydrated_items.append(item_dict)
    
    return AppraisalTemplateListResponse(
        success=True,
        message="Appraisal templates retrieved successfully",
        data=hydrated_items,
        pagination={"total_records": total, "current_page": page, "total_pages": (total + limit - 1) // limit if total > 0 else 0, "page_size": limit}
    )


@templates_router.get("/lookup", response_model=AppraisalTemplateLookupResponse)
def lookup_templates(
    search: Optional[str] = None,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    org_id = _get_org_id(current_user)
    query = db.query(AppraisalTemplate).filter(
        AppraisalTemplate.organization_id == org_id,
        AppraisalTemplate.is_active == True
    )
    if search:
        query = query.filter(AppraisalTemplate.name.ilike(f"%{search}%"))
    items = query.order_by(AppraisalTemplate.name.asc()).all()
    
    return AppraisalTemplateLookupResponse(
        success=True,
        message="Appraisal templates lookup retrieved successfully",
        data=items
    )

@templates_router.get("/{template_id}", response_model=AppraisalTemplateDetailResponse)
def get_template(
    template_id: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, "217", "view appraisal template")
    org_id = _get_org_id(current_user)
    
    template = db.query(AppraisalTemplate).filter(
        AppraisalTemplate.uuid == template_id,
        AppraisalTemplate.organization_id == org_id
    ).first()
    
    if not template:
        raise HTTPException(status_code=404, detail="Appraisal template not found")
        
    roles = []
    if template.applicable_roles:
        roles_db = db.query(Role).filter(Role.uuid.in_(template.applicable_roles), Role.organization_id == org_id).all()
        roles = [{"uuid": r.uuid, "name": r.role_name} for r in roles_db]
        
    departments = []
    if template.applicable_departments:
        dept_db = db.query(Department).filter(Department.uuid.in_(template.applicable_departments), Department.organization_id == org_id).all()
        departments = [{"uuid": d.uuid, "name": d.department_name} for d in dept_db]
        
    sections = db.query(AppraisalSection).filter(AppraisalSection.template_id == template.id).order_by(AppraisalSection.section_order.asc()).all()
    template_dict = {
        "uuid": template.uuid,
        "name": template.name,
        "description": template.description,
        "is_active": template.is_active,
        "is_default": template.is_default,
        "applicable_roles": roles,
        "applicable_departments": departments,
        "applicable_grades": template.applicable_grades or [],
        "goal_section_weight": template.goal_section_weight,
        "competency_section_weight": template.competency_section_weight,
        "behavior_section_weight": template.behavior_section_weight,
        "other_section_weight": template.other_section_weight,
        "self_appraisal_enabled": template.self_appraisal_enabled,
        "self_rating_visible_to_manager": template.self_rating_visible_to_manager,
        "employee_comments_enabled": template.employee_comments_enabled,
        "manager_override_enabled": template.manager_override_enabled,
        "final_rating_formula": template.final_rating_formula,
        "version": template.version,
        "rating_scale": template.rating_scale,
        "created_at": template.created_at,
        "updated_at": template.updated_at,
        "sections": []
    }
    
    for section in sections:
        questions = db.query(AppraisalQuestion).filter(AppraisalQuestion.section_id == section.id).order_by(AppraisalQuestion.question_order.asc()).all()
        sec_dict = {
            "uuid": section.uuid,
            "title": section.title,
            "description": section.description,
            "section_order": section.section_order,
            "weight": section.weight,
            "section_type": section.section_type,
            "is_required": section.is_required,
            "instructions": section.instructions,
            "visible_to_employee": section.visible_to_employee,
            "visible_to_manager": section.visible_to_manager,
            "questions": []
        }
        for q in questions:
            q_dict = {
                "uuid": q.uuid,
                "question_text": q.question_text,
                "question_type": q.question_type,
                "question_order": q.question_order,
                "is_required": q.is_required,
                "weight": q.weight,
                "use_section_rating_scale": q.use_section_rating_scale,
                "custom_rating_scale_uuid": q.custom_rating_scale.uuid if q.custom_rating_scale else None,
                "custom_rating_scale": q.custom_rating_scale,
                "choices": q.choices or [],
                "allow_multiple_selection": q.allow_multiple_selection,
                "competency_uuid": q.competency.uuid if q.competency else None,
                "auto_populate_goals": q.auto_populate_goals,
                "guidance": q.guidance,
                "placeholder_text": q.placeholder_text
            }
            sec_dict["questions"].append(q_dict)
            
        template_dict["sections"].append(sec_dict)

    return AppraisalTemplateDetailResponse(
        success=True,
        message="Appraisal template retrieved successfully",
        data=template_dict
    )

@templates_router.post("/", response_model=AppraisalTemplateDetailResponse, status_code=status.HTTP_201_CREATED)
def create_template(
    payload: AppraisalTemplateCreate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, "218", "create appraisal template")
    org_id = _get_org_id(current_user)
    
    existing_template = db.query(AppraisalTemplate).filter(
        AppraisalTemplate.organization_id == org_id,
        AppraisalTemplate.name == payload.name
    ).first()
    
    if existing_template:
        raise HTTPException(status_code=400, detail="An appraisal template with this name already exists.")
        
    rating_scale = db.query(RatingScale).filter(
        RatingScale.uuid == payload.rating_scale_uuid,
        RatingScale.organization_id == org_id
    ).first()
    if not rating_scale:
        raise HTTPException(status_code=400, detail="Invalid rating scale UUID")
        
    if payload.is_default:
        db.query(AppraisalTemplate).filter(
            AppraisalTemplate.organization_id == org_id,
            AppraisalTemplate.is_default == True
        ).update({"is_default": False})

    creator_id = None
    if isinstance(current_user, Employee):
        creator_id = current_user.id
        
    template = AppraisalTemplate(
        organization_id=org_id,
        rating_scale_id=rating_scale.id,
        name=payload.name,
        description=payload.description,
        is_active=payload.is_active,
        is_default=payload.is_default,
        applicable_roles=[str(u) for u in payload.applicable_roles] if payload.applicable_roles else [],
        applicable_departments=[str(u) for u in payload.applicable_departments] if payload.applicable_departments else [],
        applicable_grades=payload.applicable_grades or [],
        goal_section_weight=payload.goal_section_weight,
        competency_section_weight=payload.competency_section_weight,
        behavior_section_weight=payload.behavior_section_weight,
        other_section_weight=payload.other_section_weight,
        self_appraisal_enabled=payload.self_appraisal_enabled,
        self_rating_visible_to_manager=payload.self_rating_visible_to_manager,
        employee_comments_enabled=payload.employee_comments_enabled,
        manager_override_enabled=payload.manager_override_enabled,
        final_rating_formula=payload.final_rating_formula,
        created_by=creator_id
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    
    for sec_data in payload.sections:
        section = AppraisalSection(
            template_id=template.id,
            title=sec_data.title,
            description=sec_data.description,
            section_order=sec_data.section_order,
            weight=sec_data.weight,
            section_type=sec_data.section_type,
            is_required=sec_data.is_required,
            instructions=sec_data.instructions,
            visible_to_employee=sec_data.visible_to_employee,
            visible_to_manager=sec_data.visible_to_manager
        )
        db.add(section)
        db.flush() 
        
        for q_data in sec_data.questions:
            custom_rs_id = None
            if q_data.custom_rating_scale_uuid:
                custom_rs = db.query(RatingScale).filter(RatingScale.uuid == q_data.custom_rating_scale_uuid, RatingScale.organization_id == org_id).first()
                if custom_rs:
                    custom_rs_id = custom_rs.id
                    
            comp_id = None
            if q_data.competency_uuid:
                comp = db.query(CompetencyFramework).filter(CompetencyFramework.uuid == q_data.competency_uuid, CompetencyFramework.organization_id == org_id).first()
                if comp:
                    comp_id = comp.id
                    
            question = AppraisalQuestion(
                section_id=section.id,
                question_text=q_data.question_text,
                question_type=q_data.question_type,
                question_order=q_data.question_order,
                is_required=q_data.is_required,
                weight=q_data.weight,
                use_section_rating_scale=q_data.use_section_rating_scale,
                custom_rating_scale_id=custom_rs_id,
                choices=q_data.choices or [],
                allow_multiple_selection=q_data.allow_multiple_selection,
                competency_id=comp_id,
                auto_populate_goals=q_data.auto_populate_goals,
                guidance=q_data.guidance,
                placeholder_text=q_data.placeholder_text
            )
            db.add(question)
            
    db.commit()
    return get_template(template.uuid, db, current_user)

@templates_router.put("/{template_id}", response_model=AppraisalTemplateDetailResponse)
def update_template(
    template_id: uuid.UUID,
    payload: AppraisalTemplateUpdate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, "219", "update appraisal template")
    org_id = _get_org_id(current_user)
    
    template = db.query(AppraisalTemplate).filter(
        AppraisalTemplate.uuid == template_id,
        AppraisalTemplate.organization_id == org_id
    ).first()
    
    if not template:
        raise HTTPException(status_code=404, detail="Appraisal template not found")
        
    is_used = db.query(AppraisalCycle).filter(
        AppraisalCycle.template_id == template.id,
        AppraisalCycle.status != CycleStatus.DRAFT,
        AppraisalCycle.status != CycleStatus.ARCHIVED
    ).first()
    
    if is_used:
        raise HTTPException(
            status_code=400, 
            detail="Cannot update an appraisal template that is currently in use by an active appraisal cycle."
        )
        
    if payload.name != template.name:
        existing_template = db.query(AppraisalTemplate).filter(
            AppraisalTemplate.organization_id == org_id,
            AppraisalTemplate.name == payload.name
        ).first()
        if existing_template:
            raise HTTPException(status_code=400, detail="An appraisal template with this name already exists.")

    rating_scale = db.query(RatingScale).filter(
        RatingScale.uuid == payload.rating_scale_uuid,
        RatingScale.organization_id == org_id
    ).first()
    if not rating_scale:
        raise HTTPException(status_code=400, detail="Invalid rating scale UUID")

    if payload.is_default:
        db.query(AppraisalTemplate).filter(
            AppraisalTemplate.organization_id == org_id,
            AppraisalTemplate.is_default == True,
            AppraisalTemplate.id != template.id
        ).update({"is_default": False})

    template.name = payload.name
    template.description = payload.description
    template.rating_scale_id = rating_scale.id
    template.is_active = payload.is_active
    template.is_default = payload.is_default
    template.applicable_roles = [str(u) for u in payload.applicable_roles] if payload.applicable_roles else []
    template.applicable_departments = [str(u) for u in payload.applicable_departments] if payload.applicable_departments else []
    template.applicable_grades = payload.applicable_grades or []
    template.goal_section_weight = payload.goal_section_weight
    template.competency_section_weight = payload.competency_section_weight
    template.behavior_section_weight = payload.behavior_section_weight
    template.other_section_weight = payload.other_section_weight
    template.self_appraisal_enabled = payload.self_appraisal_enabled
    template.self_rating_visible_to_manager = payload.self_rating_visible_to_manager
    template.employee_comments_enabled = payload.employee_comments_enabled
    template.manager_override_enabled = payload.manager_override_enabled
    template.final_rating_formula = payload.final_rating_formula
    
    db.query(AppraisalQuestion).filter(
        AppraisalQuestion.section_id.in_(
            db.query(AppraisalSection.id).filter(AppraisalSection.template_id == template.id).subquery()
        )
    ).delete(synchronize_session=False)
    db.query(AppraisalSection).filter(AppraisalSection.template_id == template.id).delete(synchronize_session=False)
    
    for sec_data in payload.sections:
        section = AppraisalSection(
            template_id=template.id,
            title=sec_data.title,
            description=sec_data.description,
            section_order=sec_data.section_order,
            weight=sec_data.weight,
            section_type=sec_data.section_type,
            is_required=sec_data.is_required,
            instructions=sec_data.instructions,
            visible_to_employee=sec_data.visible_to_employee,
            visible_to_manager=sec_data.visible_to_manager
        )
        db.add(section)
        db.flush()
        
        for q_data in sec_data.questions:
            custom_rs_id = None
            if q_data.custom_rating_scale_uuid:
                custom_rs = db.query(RatingScale).filter(RatingScale.uuid == q_data.custom_rating_scale_uuid, RatingScale.organization_id == org_id).first()
                if custom_rs:
                    custom_rs_id = custom_rs.id
                    
            comp_id = None
            if q_data.competency_uuid:
                comp = db.query(CompetencyFramework).filter(CompetencyFramework.uuid == q_data.competency_uuid, CompetencyFramework.organization_id == org_id).first()
                if comp:
                    comp_id = comp.id
                    
            question = AppraisalQuestion(
                section_id=section.id,
                question_text=q_data.question_text,
                question_type=q_data.question_type,
                question_order=q_data.question_order,
                is_required=q_data.is_required,
                weight=q_data.weight,
                use_section_rating_scale=q_data.use_section_rating_scale,
                custom_rating_scale_id=custom_rs_id,
                choices=q_data.choices or [],
                allow_multiple_selection=q_data.allow_multiple_selection,
                competency_id=comp_id,
                auto_populate_goals=q_data.auto_populate_goals,
                guidance=q_data.guidance,
                placeholder_text=q_data.placeholder_text
            )
            db.add(question)

    template.version += 1
    db.commit()
    return get_template(template.uuid, db, current_user)

@templates_router.post("/{template_id}/clone", response_model=AppraisalTemplateDetailResponse)
def clone_template(
    template_id: uuid.UUID,
    payload: AppraisalTemplateClone,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, "217", "clone appraisal template")
    org_id = _get_org_id(current_user)
    
    template = db.query(AppraisalTemplate).filter(
        AppraisalTemplate.uuid == template_id,
        AppraisalTemplate.organization_id == org_id
    ).first()
    
    if not template:
        raise HTTPException(status_code=404, detail="Appraisal template not found")
        
    creator_id = None
    if isinstance(current_user, Employee):
        creator_id = current_user.id
        
    new_template = AppraisalTemplate(
        organization_id=template.organization_id,
        rating_scale_id=template.rating_scale_id,
        name=payload.new_name,
        description=template.description,
        is_active=True,
        is_default=False,
        applicable_roles=template.applicable_roles,
        applicable_departments=template.applicable_departments,
        applicable_grades=template.applicable_grades,
        goal_section_weight=template.goal_section_weight,
        competency_section_weight=template.competency_section_weight,
        behavior_section_weight=template.behavior_section_weight,
        other_section_weight=template.other_section_weight,
        self_appraisal_enabled=template.self_appraisal_enabled,
        self_rating_visible_to_manager=template.self_rating_visible_to_manager,
        employee_comments_enabled=template.employee_comments_enabled,
        manager_override_enabled=template.manager_override_enabled,
        final_rating_formula=template.final_rating_formula,
        version=1,
        cloned_from_id=template.id,
        created_by=creator_id
    )
    db.add(new_template)
    db.commit()
    db.refresh(new_template)
    
    sections = db.query(AppraisalSection).filter(AppraisalSection.template_id == template.id).all()
    for sec in sections:
        new_sec = AppraisalSection(
            template_id=new_template.id,
            title=sec.title,
            description=sec.description,
            section_type=sec.section_type,
            weight=sec.weight,
            section_order=sec.section_order,
            is_required=sec.is_required,
            instructions=sec.instructions,
            visible_to_employee=sec.visible_to_employee,
            visible_to_manager=sec.visible_to_manager
        )
        db.add(new_sec)
        db.commit()
        db.refresh(new_sec)
        
        questions = db.query(AppraisalQuestion).filter(AppraisalQuestion.section_id == sec.id).all()
        for q in questions:
            new_q = AppraisalQuestion(
                section_id=new_sec.id,
                question_text=q.question_text,
                question_type=q.question_type,
                question_order=q.question_order,
                is_required=q.is_required,
                weight=q.weight,
                use_section_rating_scale=q.use_section_rating_scale,
                custom_rating_scale_id=q.custom_rating_scale_id,
                choices=q.choices,
                allow_multiple_selection=q.allow_multiple_selection,
                competency_id=q.competency_id,
                auto_populate_goals=q.auto_populate_goals,
                guidance=q.guidance,
                placeholder_text=q.placeholder_text
            )
            db.add(new_q)
    
    db.commit()
    return get_template(new_template.uuid, db, current_user)


@templates_router.patch("/{template_id}/set-default", response_model=AppraisalTemplateDetailResponse)
def set_default_template(
    template_id: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, "218", "set default appraisal template")
    org_id = _get_org_id(current_user)
    
    template = db.query(AppraisalTemplate).filter(
        AppraisalTemplate.uuid == template_id,
        AppraisalTemplate.organization_id == org_id
    ).first()
    
    if not template:
        raise HTTPException(status_code=404, detail="Appraisal template not found")
        
    db.query(AppraisalTemplate).filter(
        AppraisalTemplate.organization_id == org_id,
        AppraisalTemplate.is_default == True
    ).update({"is_default": False})
    
    template.is_default = True
    db.commit()
    return get_template(template.uuid, db, current_user)


@templates_router.delete("/{template_id}")
def delete_template(
    template_id: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, "220", "delete appraisal template")
    org_id = _get_org_id(current_user)
    
    template = db.query(AppraisalTemplate).filter(
        AppraisalTemplate.uuid == template_id,
        AppraisalTemplate.organization_id == org_id
    ).first()
    
    if not template:
        raise HTTPException(status_code=404, detail="Appraisal template not found")
        
    template.is_active = False
    template.is_default = False
    db.commit()
    
    return {"success": True, "message": "Appraisal template successfully deleted."}


@templates_router.get("/{template_id}/preview", response_model=AppraisalTemplatePreviewResponse)
def preview_template(
    template_id: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, "217", "preview appraisal template")
    org_id = _get_org_id(current_user)
    
    template = db.query(AppraisalTemplate).filter(
        AppraisalTemplate.uuid == template_id,
        AppraisalTemplate.organization_id == org_id
    ).first()
    
    if not template:
        raise HTTPException(status_code=404, detail="Appraisal template not found")
        
    sections = db.query(AppraisalSection).filter(AppraisalSection.template_id == template.id).order_by(AppraisalSection.section_order.asc()).all()
    preview_sections = []
    
    for sec in sections:
        questions = db.query(AppraisalQuestion).filter(AppraisalQuestion.section_id == sec.id).order_by(AppraisalQuestion.question_order.asc()).all()
        q_list = []
        for q in questions:
            q_list.append({
                "uuid": str(q.uuid),
                "question_text": q.question_text,
                "question_type": q.question_type.value if hasattr(q.question_type, 'value') else q.question_type,
                "is_required": q.is_required,
                "weight": float(q.weight) if q.weight else None,
                "choices": q.choices,
                "allow_multiple_selection": q.allow_multiple_selection,
                "guidance": q.guidance,
                "placeholder_text": q.placeholder_text
            })
            
        preview_sections.append({
            "uuid": str(sec.uuid),
            "name": sec.title,
            "description": sec.description,
            "section_type": sec.section_type,
            "weight": float(sec.weight) if sec.weight else None,
            "questions": q_list
        })
        
    return AppraisalTemplatePreviewResponse(
        success=True,
        message="Preview generated successfully",
        data={
            "template_name": template.name,
            "description": template.description,
            "sections": preview_sections
        }
    )


@templates_router.post("/{template_id}/reorder-sections", response_model=dict)
def reorder_sections(
    template_id: uuid.UUID,
    payload: TemplateReorderSectionsRequest,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, "217", "update appraisal template")
    org_id = _get_org_id(current_user)
    
    template = db.query(AppraisalTemplate).filter(
        AppraisalTemplate.uuid == template_id,
        AppraisalTemplate.organization_id == org_id
    ).first()
    
    if not template:
        raise HTTPException(status_code=404, detail="Appraisal template not found")
        
    # Pass 1: Shift all updating sections to a temporary safe range to avoid unique constraint collisions
    # Pass 1: Shift all updating sections to a temporary safe range (within SmallInteger limit) to avoid unique constraint collisions
    for item in payload.sections:
        db.query(AppraisalSection).filter(
            AppraisalSection.uuid == item.section_id,
            AppraisalSection.template_id == template.id
        ).update({"section_order": item.new_order + 10000}, synchronize_session=False)
        
    # Pass 2: Set them to their actual target orders
    for item in payload.sections:
        db.query(AppraisalSection).filter(
            AppraisalSection.uuid == item.section_id,
            AppraisalSection.template_id == template.id
        ).update({"section_order": item.new_order}, synchronize_session=False)
        
    db.commit()
    return {"success": True, "message": "Sections reordered successfully"}


@templates_router.get("/{template_id}/usage", response_model=TemplateUsageResponse)
def template_usage(
    template_id: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, "217", "view appraisal template usage")
    org_id = _get_org_id(current_user)
    
    template = db.query(AppraisalTemplate).filter(
        AppraisalTemplate.uuid == template_id,
        AppraisalTemplate.organization_id == org_id
    ).first()
    
    if not template:
        raise HTTPException(status_code=404, detail="Appraisal template not found")
        
    cycles = db.query(AppraisalCycle).filter(AppraisalCycle.template_id == template.id).all()
    
    cycle_list = []
    for c in cycles:
        cycle_list.append({
            "uuid": str(c.uuid),
            "name": c.name,
            "status": c.status.value if hasattr(c.status, 'value') else c.status,
            "start_date": c.start_date,
            "end_date": c.end_date
        })
        
    return TemplateUsageResponse(
        success=True,
        message="Usage retrieved successfully",
        data={"cycles": cycle_list}
    )

@templates_router.get("/{template_id}/sections", response_model=AppraisalSectionListResponse)
def get_template_sections(
    template_id: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, "217", "list appraisal template sections")
    org_id = _get_org_id(current_user)
    
    template = db.query(AppraisalTemplate).filter(
        AppraisalTemplate.uuid == template_id,
        AppraisalTemplate.organization_id == org_id
    ).first()
    
    if not template:
        raise HTTPException(status_code=404, detail="Appraisal template not found")
        
    sections = db.query(AppraisalSection).filter(
        AppraisalSection.template_id == template.id
    ).order_by(AppraisalSection.section_order.asc()).all()
    
    data = []
    for s in sections:
        q_count = db.query(AppraisalQuestion).filter(AppraisalQuestion.section_id == s.id).count()
        item = AppraisalSectionResponseItem.model_validate(s)
        item.question_count = q_count
        data.append(item)
        
    return AppraisalSectionListResponse(
        success=True,
        message="Sections retrieved successfully",
        data=data
    )


@templates_router.post("/{template_id}/sections", response_model=AppraisalSectionDetailResponse, status_code=201)
def create_template_section(
    template_id: uuid.UUID,
    payload: AppraisalSectionCreate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, "218", "create appraisal section")
    org_id = _get_org_id(current_user)
    
    template = db.query(AppraisalTemplate).filter(
        AppraisalTemplate.uuid == template_id,
        AppraisalTemplate.organization_id == org_id
    ).first()
    
    if not template:
        raise HTTPException(status_code=404, detail="Appraisal template not found")
        
    from sqlalchemy import func
    
    existing_order = db.query(AppraisalSection).filter(
        AppraisalSection.template_id == template.id,
        AppraisalSection.section_order == payload.section_order
    ).first()
    
    if existing_order:
        max_order = db.query(func.max(AppraisalSection.section_order)).filter(
            AppraisalSection.template_id == template.id
        ).scalar() or 0
        payload.section_order = max_order + 1
        
    new_sec = AppraisalSection(
        template_id=template.id,
        **payload.model_dump()
    )
    db.add(new_sec)
    db.commit()
    db.refresh(new_sec)
    
    item = AppraisalSectionResponseItem.model_validate(new_sec)
    return AppraisalSectionDetailResponse(
        success=True,
        message="Section created successfully",
        data=item.model_dump()
    )


# ============================================================
# APPRAISAL SECTIONS ROUTER
# ============================================================
sections_router = APIRouter()

@sections_router.get("/{section_id}", response_model=AppraisalSectionDetailResponse)
def get_section(
    section_id: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, "217", "view appraisal section")
    org_id = _get_org_id(current_user)
    
    section = db.query(AppraisalSection).join(AppraisalTemplate).filter(
        AppraisalSection.uuid == section_id,
        AppraisalTemplate.organization_id == org_id
    ).first()
    
    if not section:
        raise HTTPException(status_code=404, detail="Appraisal section not found")
        
    questions = db.query(AppraisalQuestion).filter(AppraisalQuestion.section_id == section.id).order_by(AppraisalQuestion.question_order.asc()).all()
    q_list = []
    for q in questions:
        q_list.append({
            "uuid": str(q.uuid),
            "question_text": q.question_text,
            "question_type": q.question_type.value if hasattr(q.question_type, 'value') else q.question_type,
            "is_required": q.is_required,
            "weight": float(q.weight) if q.weight else None,
            "choices": q.choices,
            "allow_multiple_selection": q.allow_multiple_selection,
            "guidance": q.guidance,
            "placeholder_text": q.placeholder_text
        })
        
    sec_data = AppraisalSectionResponseItem.model_validate(section).model_dump()
    sec_data['questions'] = q_list
    
    return AppraisalSectionDetailResponse(
        success=True,
        message="Section retrieved successfully",
        data=sec_data
    )

@sections_router.put("/{section_id}", response_model=AppraisalSectionDetailResponse)
def update_section(
    section_id: uuid.UUID,
    payload: AppraisalSectionUpdate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, "219", "update appraisal section")
    org_id = _get_org_id(current_user)
    
    section = db.query(AppraisalSection).join(AppraisalTemplate).filter(
        AppraisalSection.uuid == section_id,
        AppraisalTemplate.organization_id == org_id
    ).first()
    
    if not section:
        raise HTTPException(status_code=404, detail="Appraisal section not found")
        
    update_data = payload.model_dump(exclude_unset=True)
    
    if "section_order" in update_data and update_data["section_order"] != section.section_order:
        existing_order = db.query(AppraisalSection).filter(
            AppraisalSection.template_id == section.template_id,
            AppraisalSection.section_order == update_data["section_order"],
            AppraisalSection.id != section.id
        ).first()
        if existing_order:
            raise HTTPException(status_code=400, detail="Another section already uses this Display Order.")
            
    for key, value in update_data.items():
        setattr(section, key, value)
        
    db.commit()
    db.refresh(section)
    
    item = AppraisalSectionResponseItem.model_validate(section)
    return AppraisalSectionDetailResponse(
        success=True,
        message="Section updated successfully",
        data=item.model_dump()
    )

@sections_router.delete("/{section_id}")
def delete_section(
    section_id: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, "220", "delete appraisal section")
    org_id = _get_org_id(current_user)
    
    section = db.query(AppraisalSection).join(AppraisalTemplate).filter(
        AppraisalSection.uuid == section_id,
        AppraisalTemplate.organization_id == org_id
    ).first()
    
    if not section:
        raise HTTPException(status_code=404, detail="Appraisal section not found")
        
    # Check for active appraisals
    active_cycles = db.query(AppraisalCycle).filter(
        AppraisalCycle.template_id == section.template_id,
        AppraisalCycle.status.in_([AppraisalCycleStatus.ACTIVE, AppraisalCycleStatus.IN_PROGRESS])
    ).first()
    
    if active_cycles:
        raise HTTPException(status_code=400, detail="Cannot delete section because the template is used in an active appraisal cycle.")
        
    db.query(AppraisalQuestion).filter(AppraisalQuestion.section_id == section.id).delete()
    db.delete(section)
    db.commit()
    
    return {"success": True, "message": "Section deleted successfully"}



# ============================================================
# RATING SCALES ROUTER & ENDPOINTS
# ============================================================

scales_router = APIRouter()

@scales_router.get("/", response_model=RatingScaleListResponse)
def get_scales(
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    sort_by: Optional[str] = Query("name"),
    sort_order: Optional[str] = Query("asc"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PerformancePermissions.READ, "list rating scales")
    org_id = _get_org_id(current_user)
    
    query = db.query(RatingScale).filter(RatingScale.organization_id == org_id)
    if is_active is not None:
        query = query.filter(RatingScale.is_active == is_active)
        
    if search:
        query = query.filter(RatingScale.name.ilike(f"%{search}%"))
        
    allowed_sort_fields = {
        "name": RatingScale.name,
        "created_at": RatingScale.created_at,
    }
    sort_field = allowed_sort_fields.get(sort_by, RatingScale.name)
    if sort_order == "desc":
        query = query.order_by(sort_field.desc())
    else:
        query = query.order_by(sort_field.asc())
        
    total = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()
    
    return RatingScaleListResponse(
        success=True,
        message="Rating scales retrieved successfully",
        data=items,
        pagination={"total_records": total, "current_page": page, "total_pages": (total + limit - 1) // limit, "page_size": limit}
    )


@scales_router.get("/lookup", response_model=RatingScaleLookupResponse)
def lookup_scales(
    search: Optional[str] = None,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    org_id = _get_org_id(current_user)
    query = db.query(RatingScale).filter(
        RatingScale.organization_id == org_id,
        RatingScale.is_active == True
    )
    if search:
        query = query.filter(RatingScale.name.ilike(f"%{search}%"))
    items = query.order_by(RatingScale.name.asc()).all()
    
    return RatingScaleLookupResponse(
        success=True,
        message="Rating scales lookup retrieved successfully",
        data=items
    )


@scales_router.get("/{scale_id}", response_model=RatingScaleDetailResponse)
def get_scale_detail(
    scale_id: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PerformancePermissions.READ, "view rating scale")
    org_id = _get_org_id(current_user)
    
    scale = db.query(RatingScale).filter(
        RatingScale.uuid == scale_id,
        RatingScale.organization_id == org_id
    ).first()
    
    if not scale:
        raise HTTPException(status_code=404, detail="Rating scale not found")
        
    return RatingScaleDetailResponse(
        success=True,
        message="Rating scale retrieved successfully",
        data=scale
    )

@scales_router.post("/", response_model=RatingScaleDetailResponse, status_code=201)
def create_rating_scale(
    scale_in: RatingScaleCreate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, "214", "create rating scale")
    org_id = _get_org_id(current_user)
    
    # Check for duplicate name
    existing_scale = db.query(RatingScale).filter(
        RatingScale.organization_id == org_id,
        RatingScale.name == scale_in.name
    ).first()
    if existing_scale:
        raise HTTPException(status_code=400, detail="A rating scale with this name already exists in your organization.")
        
    # Handle is_default logic
    if scale_in.is_default:
        db.query(RatingScale).filter(
            RatingScale.organization_id == org_id,
            RatingScale.is_default == True
        ).update({"is_default": False})
        
    creator_id = current_user.id if not isinstance(current_user, Organization) else None
        
    new_scale = RatingScale(
        organization_id=org_id,
        name=scale_in.name,
        description=scale_in.description,
        is_default=scale_in.is_default,
        is_active=scale_in.is_active,
        scale_points=[p.dict() for p in scale_in.scale_points],
        min_value=scale_in.min_value,
        max_value=scale_in.max_value,
        created_by=creator_id
    )
    db.add(new_scale)
    db.commit()
    db.refresh(new_scale)
    
    return RatingScaleDetailResponse(
        success=True,
        message="Rating scale created successfully",
        data=new_scale
    )

@scales_router.put("/{scale_id}", response_model=RatingScaleDetailResponse)
def update_rating_scale(
    scale_id: uuid.UUID,
    scale_in: RatingScaleUpdate,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, "215", "update rating scale")
    org_id = _get_org_id(current_user)
    
    scale = db.query(RatingScale).filter(
        RatingScale.uuid == scale_id,
        RatingScale.organization_id == org_id
    ).first()
    
    if not scale:
        raise HTTPException(status_code=404, detail="Rating scale not found")
        
    # Check if used in active cycle
    is_used = db.query(AppraisalRecord).join(
        AppraisalCycle, AppraisalRecord.appraisal_cycle_id == AppraisalCycle.id
    ).filter(
        AppraisalRecord.rating_scale_id == scale.id,
        AppraisalCycle.status != CycleStatus.DRAFT,
        AppraisalCycle.status != CycleStatus.ARCHIVED
    ).first()
    
    if is_used:
        raise HTTPException(
            status_code=400, 
            detail="Cannot update a rating scale that is currently in use by an active appraisal cycle."
        )
        
    # Update fields
    update_data = scale_in.dict(exclude_unset=True)
    
    if "name" in update_data and update_data["name"] != scale.name:
        existing_scale = db.query(RatingScale).filter(
            RatingScale.organization_id == org_id,
            RatingScale.name == update_data["name"]
        ).first()
        if existing_scale:
            raise HTTPException(status_code=400, detail="A rating scale with this name already exists in your organization.")
            
    if update_data.get("is_default"):
        db.query(RatingScale).filter(
            RatingScale.organization_id == org_id,
            RatingScale.is_default == True,
            RatingScale.id != scale.id
        ).update({"is_default": False})
        
    for key, value in update_data.items():
        if key == "scale_points":
            setattr(scale, key, [p.dict() for p in scale_in.scale_points] if scale_in.scale_points else [])
        else:
            setattr(scale, key, value)
            
    db.commit()
    db.refresh(scale)
    
    return RatingScaleDetailResponse(
        success=True,
        message="Rating scale updated successfully",
        data=scale
    )

@scales_router.patch("/{scale_id}/set-default", response_model=RatingScaleDetailResponse)
def set_default_rating_scale(
    scale_id: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, "215", "update rating scale")
    org_id = _get_org_id(current_user)
    
    scale = db.query(RatingScale).filter(
        RatingScale.uuid == scale_id,
        RatingScale.organization_id == org_id
    ).first()
    
    if not scale:
        raise HTTPException(status_code=404, detail="Rating scale not found")
        
    if not scale.is_default:
        db.query(RatingScale).filter(
            RatingScale.organization_id == org_id,
            RatingScale.is_default == True,
            RatingScale.id != scale.id
        ).update({"is_default": False})
        
        scale.is_default = True
        db.commit()
        db.refresh(scale)
        
    return RatingScaleDetailResponse(
        success=True,
        message="Rating scale set as default successfully",
        data=scale
    )

@scales_router.delete("/{scale_id}")
def delete_rating_scale(
    scale_id: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, "216", "delete rating scale")
    org_id = _get_org_id(current_user)
    
    scale = db.query(RatingScale).filter(
        RatingScale.uuid == scale_id,
        RatingScale.organization_id == org_id
    ).first()
    
    if not scale:
        raise HTTPException(status_code=404, detail="Rating scale not found")
        
    # Check if used in any AppraisalTemplate
    used_in_templates = db.query(AppraisalTemplate).filter(
        AppraisalTemplate.rating_scale_id == scale.id,
        AppraisalTemplate.is_active == True
    ).first()
    
    # Check if used in any AppraisalCycle (direct link)
    used_in_cycles = db.query(AppraisalCycle).filter(
        AppraisalCycle.rating_scale_id == scale.id,
        AppraisalCycle.status != CycleStatus.ARCHIVED
    ).first()
    
    if used_in_templates or used_in_cycles:
        raise HTTPException(
            status_code=400, 
            detail="Cannot delete a rating scale that is currently in use by active templates or cycles."
        )
        
    scale.is_active = False
    db.commit()
    
    return {"success": True, "message": "Rating scale deleted successfully"}

@scales_router.get("/{scale_id}/usage", response_model=RatingScaleUsageResponse)
def get_rating_scale_usage(
    scale_id: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PerformancePermissions.READ, "view rating scale")
    org_id = _get_org_id(current_user)
    
    scale = db.query(RatingScale).filter(
        RatingScale.uuid == scale_id,
        RatingScale.organization_id == org_id
    ).first()
    
    if not scale:
        raise HTTPException(status_code=404, detail="Rating scale not found")
        
    templates = db.query(AppraisalTemplate).filter(
        AppraisalTemplate.rating_scale_id == scale.id
    ).all()
    
    cycles = db.query(AppraisalCycle).filter(
        AppraisalCycle.rating_scale_id == scale.id
    ).all()
    
    return RatingScaleUsageResponse(
        success=True,
        message="Rating scale usage retrieved successfully",
        data={
            "templates": [{"uuid": str(t.uuid), "name": t.name} for t in templates],
            "cycles": [{"uuid": str(c.uuid), "name": c.name} for c in cycles]
        }
    )

