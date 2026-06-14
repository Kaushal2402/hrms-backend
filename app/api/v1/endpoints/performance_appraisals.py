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
    RatingScaleLookupResponse,
    AppraisalTemplateListResponse,
    AppraisalTemplateLookupResponse
)

router = APIRouter()

class PerformancePermissions:
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
    is_active: Optional[bool] = None,
    is_default: Optional[bool] = None,
    applicable_department: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(deps.get_db),
    current_user: Union[Organization, Employee] = Depends(deps.get_current_user)
):
    _require_permission(db, current_user, PerformancePermissions.READ, "list appraisal templates")
    org_id = _get_org_id(current_user)
    
    query = db.query(AppraisalTemplate).filter(AppraisalTemplate.organization_id == org_id)
    if is_active is not None:
        query = query.filter(AppraisalTemplate.is_active == is_active)
    if is_default is not None:
        query = query.filter(AppraisalTemplate.is_default == is_default)
    if applicable_department:
        query = query.filter(func.json_contains(AppraisalTemplate.applicable_departments, func.json_quote(applicable_department)))
        
    total = query.count()
    items = query.order_by(AppraisalTemplate.name.asc()).offset((page - 1) * limit).limit(limit).all()
    
    return AppraisalTemplateListResponse(
        success=True,
        message="Appraisal templates retrieved successfully",
        data=items,
        pagination={"total_records": total, "current_page": page, "total_pages": (total + limit - 1) // limit, "page_size": limit}
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


# ============================================================
# RATING SCALES ROUTER & ENDPOINTS
# ============================================================

scales_router = APIRouter()

@scales_router.get("/", response_model=RatingScaleListResponse)
def get_scales(
    is_active: Optional[bool] = None,
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
        
    total = query.count()
    items = query.order_by(RatingScale.name.asc()).offset((page - 1) * limit).limit(limit).all()
    
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

