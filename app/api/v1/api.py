from fastapi import APIRouter
from app.api.v1.endpoints import (
    system, organizations, auth, departments, locations, job_titles, 
    cost_centers, custom_fields, employees, certifications, 
    organization_chart, documents, shifts, shift_assignments, shift_rosters, attendance,
    overtime, timesheets, timesheet_entries, leave_types, leave_policies, leave_balances,
    leave_applications, leave_calendar, compensatory_offs, holidays, optional_holidays,
    leave_encashments, attendance_policies, geofence_locations, geofence,
    approval_delegations, biometric, leave, reports, analytics, dashboards, roles, permissions, industries, quick_setup,
    clients, projects, tasks, activity_types, timesheet_policies
)

api_router = APIRouter()
api_router.include_router(system.router, prefix="/system", tags=["system"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(organizations.router, prefix="/organizations", tags=["organizations"])
api_router.include_router(departments.router, prefix="/departments", tags=["departments"])
api_router.include_router(locations.router, prefix="/locations", tags=["locations"])
api_router.include_router(job_titles.router, prefix="/job-titles", tags=["job_titles"])
api_router.include_router(cost_centers.router, prefix="/cost-centers", tags=["cost_centers"])
api_router.include_router(custom_fields.router, prefix="/custom-fields", tags=["custom_fields"])
api_router.include_router(employees.router, prefix="/employees", tags=["employees"])
api_router.include_router(certifications.router, prefix="/certifications", tags=["certifications"])
api_router.include_router(organization_chart.router, prefix="/organization-chart", tags=["organization_chart"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(shifts.router, prefix="/shifts", tags=["shifts"])
api_router.include_router(shift_assignments.router, prefix="/shift-assignments", tags=["shift_assignments"])
api_router.include_router(shift_rosters.router, prefix="/shift-roster", tags=["shift_roster"])
api_router.include_router(attendance.router, prefix="/attendance", tags=["attendance"])
api_router.include_router(overtime.router, prefix="/overtime", tags=["overtime"])
api_router.include_router(timesheets.router, prefix="/timesheets", tags=["timesheets"])
api_router.include_router(timesheet_entries.router, prefix="/timesheet-entries", tags=["timesheet_entries"])
api_router.include_router(leave_types.router, prefix="/leave-types", tags=["leave_types"])
api_router.include_router(leave_policies.router, prefix="/leave-policies", tags=["leave_policies"])
api_router.include_router(leave_balances.router, prefix="/leave-balances", tags=["leave_balances"])
api_router.include_router(leave_applications.router, prefix="/leave-applications", tags=["leave_applications"])
api_router.include_router(leave_calendar.router, prefix="/leave-calendar", tags=["leave_calendar"])
api_router.include_router(compensatory_offs.router, prefix="/compensatory-offs", tags=["compensatory_offs"])
api_router.include_router(holidays.router, prefix="/holidays", tags=["holidays"])
api_router.include_router(optional_holidays.router, prefix="/optional-holidays", tags=["optional_holidays"])
api_router.include_router(leave_encashments.router, prefix="/leave-encashments", tags=["leave_encashments"])
api_router.include_router(attendance_policies.router, prefix="/attendance-policies", tags=["attendance_policies"])
api_router.include_router(geofence_locations.router, prefix="/geofence-locations", tags=["geofence_locations"])
api_router.include_router(geofence.router, prefix="/geofence", tags=["geofence"])
api_router.include_router(approval_delegations.router, prefix="/approval-delegations", tags=["approval_delegations"])
api_router.include_router(biometric.router, prefix="/biometric", tags=["biometric"])
api_router.include_router(leave.router, prefix="/leave", tags=["leave"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(dashboards.router, prefix="/dashboards", tags=["dashboards"])
api_router.include_router(roles.router, prefix="/roles", tags=["roles"])
api_router.include_router(permissions.router, prefix="/permissions", tags=["permissions"])
api_router.include_router(industries.router, prefix="/industries", tags=["industries"])
api_router.include_router(quick_setup.router, prefix="/quick-setup", tags=["quick_setup"])

# Project & Task Master (Timesheet)
api_router.include_router(clients.router, prefix="/clients", tags=["clients"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(activity_types.router, prefix="/activity-types", tags=["activity_types"])
api_router.include_router(timesheet_policies.router, prefix="/timesheet-policies", tags=["timesheet_policies"])

