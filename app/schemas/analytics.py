from typing import List, Optional, Dict
from pydantic import BaseModel, UUID4
from datetime import date

class AttendanceMetricData(BaseModel):
    label: str
    value: float
    change_percentage: Optional[float] = None
    trend_data: Optional[List[float]] = None

class AttendanceKPIs(BaseModel):
    attendance_rate: float
    absenteeism_rate: float
    late_arrival_rate: float
    early_departure_rate: float
    overtime_utilization: float

class AttendanceMetricsResponse(BaseModel):
    success: bool
    message: str
    from_date: date
    to_date: date
    metric_type: str
    kpis: AttendanceKPIs
    detailed_metrics: List[AttendanceMetricData]

class LeaveKPIs(BaseModel):
    total_leave_days: float
    approval_rate: float
    rejection_rate: float
    avg_leave_duration: float
    utilization_rate: float

class LeaveMetricsResponse(BaseModel):
    success: bool
    message: str
    from_date: date
    to_date: date
    metric_type: str
    kpis: LeaveKPIs
    detailed_metrics: List[AttendanceMetricData]

class ProductivityKPIs(BaseModel):
    total_work_hours: float
    avg_work_hours_per_day: float
    total_overtime_hours: float
    overtime_to_work_ratio: float # (Overtime / Total Work) * 100
    efficiency_score: float # Percentage based on expected vs actual work hours

class ProductivityMetricsResponse(BaseModel):
    success: bool
    message: str
    from_date: date
    to_date: date
    kpis: ProductivityKPIs
    detailed_metrics: List[AttendanceMetricData]
