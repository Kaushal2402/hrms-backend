import uuid
from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.department import PaginatedResponse

class LocationMinSchema(BaseModel):
    uuid: uuid.UUID
    location_name: str

class DepartmentMinSchema(BaseModel):
    uuid: uuid.UUID
    department_name: str

class EmployeeMinSchema(BaseModel):
    uuid: uuid.UUID
    full_name: str

class HolidayBase(BaseModel):
    holiday_name: str
    holiday_date: date
    holiday_type: str  # public, restricted, optional, floating
    description: Optional[str] = None
    is_location_specific: bool = False
    location_uuids: Optional[List[uuid.UUID]] = None
    is_department_specific: bool = False
    department_uuids: Optional[List[uuid.UUID]] = None
    is_optional: bool = False
    optional_quota_required: bool = False
    is_restricted: bool = False
    max_employees_allowed: Optional[int] = None
    is_active: bool = True

class HolidayCreate(HolidayBase):
    pass

class HolidayUpdate(BaseModel):
    holiday_name: Optional[str] = None
    holiday_date: Optional[date] = None
    holiday_type: Optional[str] = None
    description: Optional[str] = None
    is_location_specific: Optional[bool] = None
    location_uuids: Optional[List[uuid.UUID]] = None
    is_department_specific: Optional[bool] = None
    department_uuids: Optional[List[uuid.UUID]] = None
    is_optional: Optional[bool] = None
    optional_quota_required: Optional[bool] = None
    is_restricted: Optional[bool] = None
    max_employees_allowed: Optional[int] = None
    is_active: Optional[bool] = None

class HolidaySchema(HolidayBase):
    uuid: uuid.UUID
    employees_applied: int
    created_at: datetime
    updated_at: datetime
    
    locations: Optional[List[LocationMinSchema]] = None
    departments: Optional[List[DepartmentMinSchema]] = None
    applied_employees: Optional[List[EmployeeMinSchema]] = None

    model_config = ConfigDict(from_attributes=True)

class HolidayResponse(BaseModel):
    success: bool
    message: str
    data: Optional[HolidaySchema] = None

class HolidayListResponse(PaginatedResponse[List[HolidaySchema]]):
    pass

class HolidayImportError(BaseModel):
    row: int
    name: Optional[str] = None
    error: str

class HolidayBulkImportResponse(BaseModel):
    success: bool
    message: str
    total_processed: int
    successful_count: int
    failed_count: int
    errors: List[HolidayImportError]

class OptionalHolidaySelect(BaseModel):
    employee_uuid: uuid.UUID
    holiday_uuid: uuid.UUID

class BulkOptionalHolidaySelect(BaseModel):
    employee_uuids: List[uuid.UUID]
    holiday_uuid: uuid.UUID

class OptionalHolidaySelectionSchema(BaseModel):
    id: int
    employee_id: int
    holiday_id: int
    selection_year: int
    selected_at: datetime
    is_availed: bool
    
    model_config = ConfigDict(from_attributes=True)

class OptionalHolidaySelectionDetailSchema(OptionalHolidaySelectionSchema):
    holiday: HolidaySchema

class OptionalHolidaySelectionResponse(BaseModel):
    success: bool
    message: str
    data: Optional[OptionalHolidaySelectionSchema] = None

class BulkOptionalHolidaySelectionResponse(BaseModel):
    success: bool
    message: str
    total_processed: int
    successful_count: int
    failed_count: int
    errors: List[HolidayImportError]

class EmployeeOptionalHolidayListResponse(PaginatedResponse[List[OptionalHolidaySelectionDetailSchema]]):
    pass

class BulkHolidayCreateRequest(BaseModel):
    holidays: List[HolidayCreate]

class HolidayBulkCreateResponse(BaseModel):
    success: bool
    message: str
    total_processed: int
    successful_count: int
    failed_count: int
    errors: List[HolidayImportError]
