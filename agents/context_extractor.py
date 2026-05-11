"""
context_extractor.py
Reads the existing codebase and produces a structured style guide JSON.
This is run ONCE and its output is fed to the Generator agent on every invocation.
"""

import json
import re
import os
import ast
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
OUTPUT_PATH = Path(__file__).parent / "codebase_style_guide.json"

# Reference files to extract patterns from
REFERENCE_FILES = {
    "complex_endpoint": BASE_DIR / "app/api/v1/endpoints/leave_applications.py",
    "simple_endpoint":  BASE_DIR / "app/api/v1/endpoints/roles.py",
    "schema_example":   BASE_DIR / "app/schemas/leave.py",
    "deps_file":        BASE_DIR / "app/api/deps.py",
    "permissions_file": BASE_DIR / "app/core/permissions.py",
    "api_router_file":  BASE_DIR / "app/api/v1/api.py",
}


def extract_style_guide() -> dict:
    guide = {
        "auth_pattern": extract_auth_pattern(),
        "schema_pattern": extract_schema_pattern(),
        "endpoint_pattern": extract_endpoint_pattern(),
        "pagination_pattern": extract_pagination_pattern(),
        "error_handling_pattern": extract_error_pattern(),
        "rbac_pattern": extract_rbac_pattern(),
        "naming_conventions": extract_naming_conventions(),
        "response_envelope": extract_response_envelope(),
        "router_registration_example": extract_router_example(),
        "complete_endpoint_reference": read_reference_file("simple_endpoint"),
        "complete_schema_reference":   read_reference_file("schema_example", max_lines=200),
    }
    return guide


def read_reference_file(key: str, max_lines: int = None) -> str:
    path = REFERENCE_FILES.get(key)
    if not path or not path.exists():
        return ""
    lines = path.read_text().splitlines()
    if max_lines:
        lines = lines[:max_lines]
    return "\n".join(lines)


def extract_auth_pattern() -> dict:
    return {
        "imports": [
            "from app.api import deps",
            "from app.models.organization import Organization",
            "from app.models.employee import Employee",
            "from typing import Union",
            "from sqlalchemy.orm import Session",
            "from fastapi import Depends",
        ],
        "db_dependency":      "db: Session = Depends(deps.get_db)",
        "org_dependency":     "current_org: Organization = Depends(deps.get_current_org)",
        "user_dependency":    "current_user: Union[Organization, Employee] = Depends(deps.get_current_user)",
        "org_id_helper": """
def _get_org_id(current_user: Union[Organization, Employee]) -> int:
    if isinstance(current_user, Organization):
        return current_user.id
    return current_user.organization_id
""",
        "permission_helper": """
def _require_permission(db, current_user, code, action_label):
    if isinstance(current_user, Organization):
        return
    if not deps.has_permission(db, current_user, code):
        raise HTTPException(status_code=403,
            detail=f"You do not have permission to {action_label} (requires code: {code})")
""",
        "note": "Organization users are always superusers — bypass all permission checks. "
                "Use get_current_org when you only need the org context (not acting user). "
                "Use get_current_user when you need to know if acting user is Employee or Org.",
    }


def extract_schema_pattern() -> dict:
    return {
        "base_class": "from pydantic import BaseModel, UUID4",
        "config_class": "class Config:\n        from_attributes = True",
        "pattern": {
            "1_base_schema":    "XxxBase(BaseModel) — shared fields between Create and Schema",
            "2_create_schema":  "XxxCreate(XxxBase) — input for POST. NO uuid/id/created_at/updated_at",
            "3_update_schema":  "XxxUpdate(BaseModel) — input for PUT. All fields Optional[...]",
            "4_response_schema":"XxxSchema(BaseModel) — full ORM object. Has uuid, created_at, etc. Has Config.from_attributes=True",
            "5_single_response":"XxxResponse(BaseModel) — {success: bool, message: str, data: Optional[XxxSchema]}",
            "6_list_response":  "XxxListResponse(PaginatedResponse[List[XxxSchema]]) — uses shared PaginatedResponse",
        },
        "paginated_response_import": "from app.schemas.department import PaginatedResponse",
        "paginated_response_def": """
class PaginatedResponse(BaseModel, Generic[T]):
    success: bool
    message: str
    data: T
    pagination: dict
""",
        "uuid_field": "uuid: UUID4",
        "optional_pattern": "field_name: Optional[type] = None",
        "enum_import_note": "Import Enums from the MODEL file, not re-declared in schemas",
        "validator_example": """
@field_validator('some_field', mode='before')
@classmethod
def validate_something(cls, v):
    # transform v if needed
    return v
""",
        "model_validator_example": """
@model_validator(mode='after')
def validate_dates(self) -> 'XxxCreate':
    if self.effective_from and self.effective_to:
        if self.effective_from >= self.effective_to:
            raise ValueError("effective_from must be before effective_to")
    return self
""",
    }


def extract_endpoint_pattern() -> dict:
    return {
        "imports": [
            "import uuid",
            "from typing import List, Optional, Union",
            "from fastapi import APIRouter, Depends, HTTPException, Query, status",
            "from fastapi.responses import JSONResponse",
            "from sqlalchemy.orm import Session, joinedload",
            "from sqlalchemy import or_, and_, func",
        ],
        "router_init": "router = APIRouter()",
        "get_list": {
            "decorator": "@router.get('/', response_model=XxxListResponse)",
            "params": "page: int = Query(1, ge=1), limit: int = Query(10, ge=1, le=100), search: Optional[str] = Query(None)",
            "filter_org": "query = db.query(XxxModel).filter(XxxModel.organization_id == current_org.id)",
            "pagination": """
total_records = query.count()
total_pages = (total_records + limit - 1) // limit if total_records > 0 else 0
items = query.offset((page - 1) * limit).limit(limit).all()
return XxxListResponse(success=True, message='Retrieved successfully',
    data=items, pagination={'total_records': total_records,
    'current_page': page, 'total_pages': total_pages, 'page_size': limit})
""",
        },
        "get_by_uuid": {
            "decorator": "@router.get('/{item_uuid}', response_model=XxxResponse)",
            "lookup": "item = db.query(XxxModel).filter(XxxModel.uuid == item_uuid, XxxModel.organization_id == current_org.id).first()",
            "not_found": "raise HTTPException(status_code=404, detail='Item not found')",
        },
        "create": {
            "decorator": "@router.post('/', response_model=XxxResponse)",
            "uniqueness_check": "if db.query(XxxModel).filter(XxxModel.organization_id == org_id, XxxModel.code == item_in.code).first(): raise HTTPException(400, 'Code already exists')",
            "create_pattern": "item = XxxModel(organization_id=org_id, **item_in.model_dump()); db.add(item); db.commit(); db.refresh(item)",
        },
        "update": {
            "decorator": "@router.put('/{item_uuid}', response_model=XxxResponse)",
            "update_pattern": "for field, value in item_in.model_dump(exclude_unset=True).items(): setattr(item, field, value); db.commit(); db.refresh(item)",
        },
        "delete": {
            "decorator": "@router.delete('/{item_uuid}')",
            "soft_delete": "item.is_active = False; db.commit()",
            "return": "return {'success': True, 'message': 'Deleted successfully'}",
        },
        "action_patch": {
            "decorator": "@router.post('/{item_uuid}/action-name')",
            "pattern": "Verify status, update fields, db.commit(), return updated item",
        },
        "uuid_in_path": "ALWAYS use uuid.UUID type in path params, NEVER use int IDs",
        "background_task": """
from fastapi import BackgroundTasks

@router.post('/periods/{period_uuid}/process')
def process_payroll(
    period_uuid: uuid.UUID,
    should_proceed_background: bool = Query(False),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(deps.get_db),
    ...
):
    if should_proceed_background:
        background_tasks.add_task(process_payroll_task, period.id, db)
        return {'success': True, 'message': 'Processing started in background', 'data': period}
    else:
        result = process_payroll_task(period.id, db)
        return {'success': True, 'message': 'Processing complete', 'data': result}
""",
    }


def extract_pagination_pattern() -> dict:
    return {
        "structure": {
            "total_records": "int — total number of matching records",
            "current_page":  "int — current page number (1-indexed)",
            "total_pages":   "int — ceil(total_records / page_size)",
            "page_size":     "int — items per page (the limit param)",
        },
        "query_params": "page: int = Query(1, ge=1), limit: int = Query(10, ge=1, le=100)",
        "offset_calc":  "skip = (page - 1) * limit",
        "query_apply":  "items = query.offset(skip).limit(limit).all()",
    }


def extract_error_pattern() -> dict:
    return {
        "404_not_found": "raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='X not found')",
        "400_bad_request": "raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='reason')",
        "403_forbidden": "raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Access denied')",
        "json_response_400": "return JSONResponse(status_code=400, content={'success': False, 'message': 'reason', 'data': None})",
        "rule": "Use HTTPException for 404/403 (these are exceptional). Use JSONResponse for 400 business validation errors that return data=None.",
        "consistent_success": "Always return {'success': True, 'message': '...', 'data': ...} on success",
    }


def extract_rbac_pattern() -> dict:
    return {
        "check_in_function": "_require_permission(db, current_user, PayrollXxxPermissions.READ, 'list')",
        "dependency_style":  "dependencies=[Depends(deps.check_permission(PayrollXxxPermissions.READ))]",
        "org_bypass": "Organization users ALWAYS bypass. Only Employee users are checked.",
        "permission_class_pattern": """
class PayrollSalaryComponentPermissions:
    READ   = "101"
    CREATE = "102"
    UPDATE = "103"
    DELETE = "104"
""",
        "permission_class_file": "app/core/permissions.py — append new classes at bottom",
    }


def extract_naming_conventions() -> dict:
    return {
        "table_names":         "plural snake_case — salary_components, payroll_periods",
        "model_class_names":   "PascalCase singular — SalaryComponent, PayrollPeriod",
        "endpoint_file_names": "payroll_{module}.py — payroll_salary_components.py",
        "schema_file":         "app/schemas/payroll.py (single file for all payroll schemas)",
        "endpoint_prefix":     "/payroll/salary-components, /payroll/periods",
        "router_tags":         '["payroll"]',
        "uuid_path_params":    "{component_uuid}, {period_uuid}, {payslip_uuid} — uuid.UUID type",
        "query_filters":       "snake_case Query params matching model field names",
        "response_messages":   "'Salary components retrieved successfully', 'Salary component created successfully'",
    }


def extract_response_envelope() -> dict:
    return {
        "success_single": {"success": True, "message": "str", "data": "XxxSchema | None"},
        "success_list": {"success": True, "message": "str", "data": "List[XxxSchema]", "pagination": "PaginationDict"},
        "error": {"success": False, "message": "str", "data": None},
        "action_success": {"success": True, "message": "str"},
    }


def extract_router_example() -> str:
    return """
# In app/api/v1/api.py — append at the end:
from app.api.v1.endpoints import (
    payroll_salary_components, payroll_salary_templates,
    payroll_employee_salaries, payroll_periods, payroll_payslips,
    payroll_loans, payroll_reimbursements, payroll_final_settlements,
    payroll_arrears, payroll_tax_declarations, payroll_bank_files,
    payroll_reconciliations, payroll_journal_entries,
    payroll_statutory_forms, payroll_reports, payroll_bulk,
    payroll_bank_accounts, payroll_audit_logs
)

# Payroll Module
api_router.include_router(payroll_salary_components.router, prefix="/payroll/salary-components", tags=["payroll"])
api_router.include_router(payroll_salary_templates.router, prefix="/payroll/salary-templates", tags=["payroll"])
api_router.include_router(payroll_employee_salaries.router, prefix="/payroll/employee-salaries", tags=["payroll"])
api_router.include_router(payroll_periods.router, prefix="/payroll/periods", tags=["payroll"])
api_router.include_router(payroll_payslips.router, prefix="/payroll/payslips", tags=["payroll"])
api_router.include_router(payroll_loans.router, prefix="/payroll/loans", tags=["payroll"])
api_router.include_router(payroll_reimbursements.router, prefix="/payroll/reimbursements", tags=["payroll"])
api_router.include_router(payroll_final_settlements.router, prefix="/payroll/final-settlements", tags=["payroll"])
api_router.include_router(payroll_arrears.router, prefix="/payroll/arrears", tags=["payroll"])
api_router.include_router(payroll_tax_declarations.router, prefix="/payroll/tax-declarations", tags=["payroll"])
api_router.include_router(payroll_bank_files.router, prefix="/payroll/bank-files", tags=["payroll"])
api_router.include_router(payroll_reconciliations.router, prefix="/payroll/reconciliations", tags=["payroll"])
api_router.include_router(payroll_journal_entries.router, prefix="/payroll/journal-entries", tags=["payroll"])
api_router.include_router(payroll_statutory_forms.router, prefix="/payroll/statutory-forms", tags=["payroll"])
api_router.include_router(payroll_reports.router, prefix="/payroll/reports", tags=["payroll"])
api_router.include_router(payroll_bulk.router, prefix="/payroll/bulk", tags=["payroll"])
api_router.include_router(payroll_bank_accounts.router, prefix="/payroll/bank-accounts", tags=["payroll"])
api_router.include_router(payroll_audit_logs.router, prefix="/payroll/audit-log", tags=["payroll"])
"""


if __name__ == "__main__":
    guide = extract_style_guide()
    OUTPUT_PATH.write_text(json.dumps(guide, indent=2))
    print(f"✅ Style guide written to {OUTPUT_PATH}")
    print(f"   Keys: {list(guide.keys())}")
