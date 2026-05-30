# HRMS – Module 3.5: Performance Management
# Complete API Reference

---

## Overview

| Group | Section | Count |
|---|---|---|
| 1 | Goal Framework | 6 |
| 2 | Organization Goals | 8 |
| 3 | Department Goals | 8 |
| 4 | Employee Goals | 11 |
| 5 | Goal Progress | 6 |
| 6 | Goal Alignment | 5 |
| 7 | Appraisal Cycles | 12 |
| 8 | Rating Scales | 7 |
| 9 | Appraisal Templates | 10 |
| 10 | Appraisal Sections | 7 |
| 11 | Appraisal Questions | 7 |
| 12 | Appraisal Records | 12 |
| 13 | Self-Appraisal | 7 |
| 14 | Manager Appraisal | 7 |
| 15 | Appraisal Answers | 6 |
| 16 | Calibration | 10 |
| 17 | Bell Curve Distribution | 5 |
| 18 | 360 Feedback Questions | 7 |
| 19 | 360 Feedback Requests | 9 |
| 20 | Feedback Providers | 7 |
| 21 | Feedback Responses | 7 |
| 22 | Competency Framework | 8 |
| 23 | Competency Mapping | 6 |
| 24 | Employee Competency | 7 |
| 25 | Skills Gap Analysis | 6 |
| 26 | Continuous Feedback | 9 |
| 27 | 1-on-1 Meetings | 11 |
| 28 | Agenda Items | 8 |
| 29 | Performance Notes | 7 |
| 30 | PIP Plans | 11 |
| 31 | PIP Objectives | 7 |
| 32 | PIP Progress Logs | 6 |
| 33 | Talent Review | 9 |
| 34 | Talent Review Participants | 8 |
| 35 | Succession Plans | 8 |
| 36 | Succession Candidates | 8 |
| 37 | Performance Analytics | 10 |
| 38 | Notifications | 8 |
| 39 | Notification Templates | 6 |
| 40 | Compensation Integration | 8 |
| **TOTAL** | | **~300 APIs** |

---

## Access Roles Legend
- **Super Admin** – Platform-level administration
- **HR Admin** – Full HR module access
- **Manager** – Access to direct reports
- **Employee** – Self-service access
- **HR Viewer** – Read-only HR access
- **Calibrator** – Calibration session participant

---

## 1. GOAL FRAMEWORK

### `GET /api/v1/performance/goal-frameworks`
List all goal frameworks for the organization.
- **Query Params**: `framework_type`, `is_active`, `page`, `limit`
- **Response**: Paginated list of goal frameworks
- **Access**: HR Admin, Manager, Employee

### `POST /api/v1/performance/goal-frameworks`
Create a new goal framework (OKR, SMART, KPI, Custom).
- **Request Body**: `name`, `framework_type`, `description`, `max_objectives_per_employee`, `max_key_results_per_objective`, `goal_weight_enabled`, `default_scoring_method`, OKR/SMART config flags
- **Response**: Created framework object
- **Access**: HR Admin

### `GET /api/v1/performance/goal-frameworks/{framework_id}`
Get details of a specific goal framework.
- **Path Param**: `framework_id`
- **Response**: Framework detail with configuration
- **Access**: HR Admin, Manager, Employee

### `PUT /api/v1/performance/goal-frameworks/{framework_id}`
Update an existing goal framework.
- **Path Param**: `framework_id`
- **Request Body**: Updated framework fields
- **Response**: Updated framework object
- **Access**: HR Admin

### `PATCH /api/v1/performance/goal-frameworks/{framework_id}/set-default`
Mark a framework as the organization default.
- **Path Param**: `framework_id`
- **Response**: Updated framework
- **Access**: HR Admin

### `DELETE /api/v1/performance/goal-frameworks/{framework_id}`
Soft-delete a goal framework (only if no active goals linked).
- **Path Param**: `framework_id`
- **Response**: Success message
- **Access**: HR Admin

---

## 2. ORGANIZATION GOALS

### `GET /api/v1/performance/org-goals`
List all organizational strategic goals.
- **Query Params**: `fiscal_year`, `status`, `framework_type`, `owner_id`, `page`, `limit`
- **Response**: Paginated list of org goals with progress
- **Access**: HR Admin, Manager, Employee (public goals)

### `POST /api/v1/performance/org-goals`
Create a new organizational goal.
- **Request Body**: `title`, `description`, `framework_id`, `start_date`, `end_date`, `fiscal_year`, `measurement_type`, `target_value`, `unit`, `weight`, `owner_id`, `is_public`, `tags`
- **Response**: Created org goal
- **Access**: HR Admin, Super Admin

### `GET /api/v1/performance/org-goals/{goal_id}`
Get details of a specific organizational goal.
- **Path Param**: `goal_id`
- **Response**: Goal detail with progress and alignment tree
- **Access**: HR Admin, Manager, Employee

### `PUT /api/v1/performance/org-goals/{goal_id}`
Update an organizational goal.
- **Path Param**: `goal_id`
- **Request Body**: Updated goal fields
- **Response**: Updated goal
- **Access**: HR Admin, Goal Owner

### `PATCH /api/v1/performance/org-goals/{goal_id}/status`
Update the status of an org goal (Active, Completed, Cancelled).
- **Path Param**: `goal_id`
- **Request Body**: `status`, `notes`
- **Response**: Updated goal
- **Access**: HR Admin, Goal Owner

### `DELETE /api/v1/performance/org-goals/{goal_id}`
Soft-delete an organizational goal.
- **Path Param**: `goal_id`
- **Response**: Success message
- **Access**: HR Admin

### `GET /api/v1/performance/org-goals/{goal_id}/cascade`
View the full cascade tree: org → department → individual goals.
- **Path Param**: `goal_id`
- **Response**: Hierarchical alignment tree with progress at each level
- **Access**: HR Admin, Manager

### `GET /api/v1/performance/org-goals/summary`
Get aggregated goal completion summary for the organization.
- **Query Params**: `fiscal_year`, `framework_type`
- **Response**: `{total, on_track, at_risk, behind, completed}` counts with percentages
- **Access**: HR Admin, Manager

---

## 3. DEPARTMENT GOALS

### `GET /api/v1/performance/department-goals`
List goals for a department or all departments.
- **Query Params**: `department_id`, `fiscal_year`, `status`, `framework_type`, `parent_org_goal_id`, `page`, `limit`
- **Response**: Paginated list of department goals
- **Access**: HR Admin, Manager (own dept), Employee (own dept)

### `POST /api/v1/performance/department-goals`
Create a new department goal, optionally cascaded from an org goal.
- **Request Body**: `department_id`, `framework_id`, `title`, `description`, `start_date`, `end_date`, `fiscal_year`, `measurement_type`, `target_value`, `unit`, `weight`, `owner_id`, `parent_org_goal_id`, `tags`
- **Response**: Created department goal
- **Access**: HR Admin, Department Manager

### `GET /api/v1/performance/department-goals/{goal_id}`
Get details of a department goal.
- **Path Param**: `goal_id`
- **Response**: Goal detail with parent org goal link and individual goal children
- **Access**: HR Admin, Manager, Employee

### `PUT /api/v1/performance/department-goals/{goal_id}`
Update a department goal.
- **Path Param**: `goal_id`
- **Request Body**: Updated goal fields
- **Response**: Updated goal
- **Access**: HR Admin, Department Manager, Goal Owner

### `PATCH /api/v1/performance/department-goals/{goal_id}/status`
Update status of a department goal.
- **Path Param**: `goal_id`
- **Request Body**: `status`, `notes`
- **Response**: Updated goal
- **Access**: HR Admin, Goal Owner

### `DELETE /api/v1/performance/department-goals/{goal_id}`
Soft-delete a department goal.
- **Path Param**: `goal_id`
- **Response**: Success message
- **Access**: HR Admin, Department Manager

### `GET /api/v1/performance/department-goals/{goal_id}/cascade`
View cascade from this department goal to individual employee goals.
- **Path Param**: `goal_id`
- **Response**: Tree structure with individual goal statuses
- **Access**: HR Admin, Manager

### `GET /api/v1/performance/department-goals/summary`
Department-wise goal completion summary.
- **Query Params**: `fiscal_year`, `department_id`
- **Response**: Per-department goal health metrics
- **Access**: HR Admin, Manager

---

## 4. EMPLOYEE GOALS

### `GET /api/v1/performance/employee-goals`
List goals for an employee or across a team.
- **Query Params**: `employee_id`, `manager_id`, `appraisal_cycle_id`, `status`, `framework_type`, `fiscal_year`, `is_stretch_goal`, `page`, `limit`
- **Response**: Paginated list of employee goals with progress
- **Access**: HR Admin, Manager (team), Employee (self)

### `POST /api/v1/performance/employee-goals`
Create a new individual goal for an employee.
- **Request Body**: `employee_id`, `framework_id`, `title`, `description`, `start_date`, `end_date`, `measurement_type`, `target_value`, `baseline_value`, `unit`, `weight`, `parent_dept_goal_id`, `parent_org_goal_id`, `appraisal_cycle_id`, `is_stretch_goal`, `objective_key`, `is_key_result`, `parent_objective_id`, SMART flags, `tags`
- **Response**: Created employee goal
- **Access**: HR Admin, Manager, Employee (self)

### `GET /api/v1/performance/employee-goals/{goal_id}`
Get details of an individual employee goal.
- **Path Param**: `goal_id`
- **Response**: Goal detail with progress history and alignment
- **Access**: HR Admin, Manager, Employee (self)

### `PUT /api/v1/performance/employee-goals/{goal_id}`
Update an employee goal.
- **Path Param**: `goal_id`
- **Request Body**: Updated goal fields
- **Response**: Updated goal
- **Access**: HR Admin, Manager, Employee (self, before approval)

### `PATCH /api/v1/performance/employee-goals/{goal_id}/approve`
Manager approves or rejects an employee goal.
- **Path Param**: `goal_id`
- **Request Body**: `approved` (boolean), `manager_comment`
- **Response**: Updated goal with approval status
- **Access**: Manager, HR Admin

### `PATCH /api/v1/performance/employee-goals/{goal_id}/status`
Update status of an employee goal (Active, On Track, At Risk, Completed).
- **Path Param**: `goal_id`
- **Request Body**: `status`, `notes`
- **Response**: Updated goal
- **Access**: HR Admin, Manager, Employee (self)

### `DELETE /api/v1/performance/employee-goals/{goal_id}`
Soft-delete an employee goal.
- **Path Param**: `goal_id`
- **Response**: Success message
- **Access**: HR Admin, Manager

### `POST /api/v1/performance/employee-goals/bulk-create`
Bulk create goals for multiple employees (e.g., cascade department goal to team).
- **Request Body**: `{employee_ids: [], goal_template: {...}}`
- **Response**: List of created goal IDs with success/failure per employee
- **Access**: HR Admin, Manager

### `GET /api/v1/performance/employee-goals/my-goals`
Get authenticated employee's own goals dashboard.
- **Query Params**: `appraisal_cycle_id`, `status`, `fiscal_year`
- **Response**: Goals grouped by framework type with overall completion %
- **Access**: Employee (self)

### `GET /api/v1/performance/employee-goals/team-goals`
Get all goals for manager's direct reports.
- **Query Params**: `appraisal_cycle_id`, `status`, `employee_id`
- **Response**: Per-employee goal list with health indicators
- **Access**: Manager, HR Admin

### `GET /api/v1/performance/employee-goals/{goal_id}/okr-tree`
Get full OKR tree (Objective + Key Results) rooted at a given goal.
- **Path Param**: `goal_id`
- **Response**: Nested OKR structure with progress per key result
- **Access**: HR Admin, Manager, Employee (self)

---

## 5. GOAL PROGRESS

### `GET /api/v1/performance/employee-goals/{goal_id}/progress`
List all progress check-in entries for a goal.
- **Path Param**: `goal_id`
- **Query Params**: `from_date`, `to_date`, `page`, `limit`
- **Response**: Chronological list of progress updates
- **Access**: HR Admin, Manager, Employee (self)

### `POST /api/v1/performance/employee-goals/{goal_id}/progress`
Submit a new progress check-in update.
- **Path Param**: `goal_id`
- **Request Body**: `check_in_date`, `current_value`, `progress_percentage`, `status`, `update_notes`, `blockers`, `next_steps`, `attachments`
- **Response**: Created progress log
- **Access**: Employee (self), Manager, HR Admin

### `GET /api/v1/performance/employee-goals/{goal_id}/progress/{progress_id}`
Get a specific progress log entry.
- **Path Param**: `goal_id`, `progress_id`
- **Response**: Progress log detail
- **Access**: HR Admin, Manager, Employee (self)

### `PUT /api/v1/performance/employee-goals/{goal_id}/progress/{progress_id}`
Update a progress check-in entry.
- **Path Param**: `goal_id`, `progress_id`
- **Request Body**: Updated progress fields
- **Response**: Updated progress log
- **Access**: Employee (self, within edit window), HR Admin

### `PATCH /api/v1/performance/employee-goals/{goal_id}/progress/{progress_id}/acknowledge`
Manager acknowledges a progress update with optional comment.
- **Path Param**: `goal_id`, `progress_id`
- **Request Body**: `manager_comment`
- **Response**: Acknowledged progress log
- **Access**: Manager, HR Admin

### `DELETE /api/v1/performance/employee-goals/{goal_id}/progress/{progress_id}`
Delete a progress entry.
- **Path Param**: `goal_id`, `progress_id`
- **Response**: Success message
- **Access**: HR Admin

---

## 6. GOAL ALIGNMENT

### `GET /api/v1/performance/goal-alignments`
List goal alignments (parent-child relationships).
- **Query Params**: `parent_goal_type`, `parent_goal_id`, `child_goal_type`, `child_goal_id`
- **Response**: List of alignment mappings
- **Access**: HR Admin, Manager

### `POST /api/v1/performance/goal-alignments`
Create a new goal alignment (link a child goal to a parent).
- **Request Body**: `parent_goal_type`, `parent_goal_id`, `child_goal_type`, `child_goal_id`, `alignment_weight`, `notes`
- **Response**: Created alignment
- **Access**: HR Admin, Manager

### `GET /api/v1/performance/goal-alignments/tree`
Get the full organizational goal alignment tree for a fiscal year.
- **Query Params**: `fiscal_year`, `department_id`
- **Response**: Hierarchical tree from org → dept → individual goals
- **Access**: HR Admin, Manager

### `PUT /api/v1/performance/goal-alignments/{alignment_id}`
Update an alignment's weight or notes.
- **Path Param**: `alignment_id`
- **Request Body**: `alignment_weight`, `notes`
- **Response**: Updated alignment
- **Access**: HR Admin

### `DELETE /api/v1/performance/goal-alignments/{alignment_id}`
Remove a goal alignment link.
- **Path Param**: `alignment_id`
- **Response**: Success message
- **Access**: HR Admin, Manager

---

## 7. APPRAISAL CYCLES

### `GET /api/v1/performance/appraisal-cycles`
List all appraisal cycles for the organization.
- **Query Params**: `status`, `frequency`, `fiscal_year`, `page`, `limit`
- **Response**: Paginated list of cycles with phase dates and status
- **Access**: HR Admin, Manager, Employee

### `POST /api/v1/performance/appraisal-cycles`
Create a new appraisal cycle.
- **Request Body**: `name`, `frequency`, `fiscal_year`, `review_period_start`, `review_period_end`, `goal_setting_start/end`, `self_appraisal_start/end`, `manager_review_start/end`, `calibration_start/end`, `result_publication_date`, `template_id`, `rating_scale_id`, `include_probationary`, `minimum_tenure_days`, `applicable_departments`, `applicable_employee_types`, workflow flags, bell curve config, reminder config
- **Response**: Created cycle
- **Access**: HR Admin

### `GET /api/v1/performance/appraisal-cycles/{cycle_id}`
Get details of an appraisal cycle including all phase windows.
- **Path Param**: `cycle_id`
- **Response**: Full cycle detail with template and rating scale info
- **Access**: HR Admin, Manager, Employee

### `PUT /api/v1/performance/appraisal-cycles/{cycle_id}`
Update an appraisal cycle (only in DRAFT status).
- **Path Param**: `cycle_id`
- **Request Body**: Updated cycle fields
- **Response**: Updated cycle
- **Access**: HR Admin

### `PATCH /api/v1/performance/appraisal-cycles/{cycle_id}/launch`
Launch a cycle — sets status to ACTIVE, generates appraisal records, and sends kick-off notifications.
- **Path Param**: `cycle_id`
- **Response**: Launch summary `{cycle, records_created, notifications_sent}`
- **Access**: HR Admin

### `PATCH /api/v1/performance/appraisal-cycles/{cycle_id}/advance-phase`
Advance cycle to the next phase (Self → Manager → Calibration → Completed).
- **Path Param**: `cycle_id`
- **Request Body**: `force_advance` (boolean), `notes`
- **Response**: Updated cycle with new status
- **Access**: HR Admin

### `PATCH /api/v1/performance/appraisal-cycles/{cycle_id}/publish-results`
Publish final ratings and make them visible to employees.
- **Path Param**: `cycle_id`
- **Request Body**: `publish_all` (boolean), `employee_ids` (for selective publish)
- **Response**: Publish summary
- **Access**: HR Admin

### `GET /api/v1/performance/appraisal-cycles/{cycle_id}/dashboard`
Get cycle-level dashboard: completion stats per phase, department breakdown, pending actions.
- **Path Param**: `cycle_id`
- **Response**: `{total_employees, self_submitted_count, manager_reviewed_count, calibrated_count, pending_list}`
- **Access**: HR Admin

### `GET /api/v1/performance/appraisal-cycles/{cycle_id}/pending`
List employees with pending actions in the current phase.
- **Path Param**: `cycle_id`
- **Query Params**: `phase`, `department_id`, `manager_id`, `page`, `limit`
- **Response**: Paginated list with employee and manager details
- **Access**: HR Admin

### `POST /api/v1/performance/appraisal-cycles/{cycle_id}/send-reminders`
Send bulk reminder notifications for a cycle phase.
- **Path Param**: `cycle_id`
- **Request Body**: `phase`, `recipient_group` (employees/managers/all), `department_ids`, `custom_message`
- **Response**: `{sent_count, failed_count}`
- **Access**: HR Admin

### `DELETE /api/v1/performance/appraisal-cycles/{cycle_id}`
Delete an appraisal cycle (only in DRAFT status).
- **Path Param**: `cycle_id`
- **Response**: Success message
- **Access**: HR Admin

### `GET /api/v1/performance/appraisal-cycles/active`
Get the currently active appraisal cycle for the organization.
- **Response**: Active cycle with current phase context
- **Access**: HR Admin, Manager, Employee

---

## 8. RATING SCALES

### `GET /api/v1/performance/rating-scales`
List all rating scales.
- **Query Params**: `is_active`, `page`, `limit`
- **Response**: Paginated list of rating scales with scale points
- **Access**: HR Admin, Manager, Employee

### `POST /api/v1/performance/rating-scales`
Create a new rating scale.
- **Request Body**: `name`, `description`, `scale_points` (array of `{value, label, description, color, is_passing}`), `min_value`, `max_value`, `is_default`
- **Response**: Created rating scale
- **Access**: HR Admin

### `GET /api/v1/performance/rating-scales/{scale_id}`
Get details of a rating scale.
- **Path Param**: `scale_id`
- **Response**: Rating scale with all scale points
- **Access**: HR Admin, Manager, Employee

### `PUT /api/v1/performance/rating-scales/{scale_id}`
Update a rating scale (only if not used in active cycles).
- **Path Param**: `scale_id`
- **Request Body**: Updated scale fields
- **Response**: Updated scale
- **Access**: HR Admin

### `PATCH /api/v1/performance/rating-scales/{scale_id}/set-default`
Set a rating scale as the organization default.
- **Path Param**: `scale_id`
- **Response**: Updated scale
- **Access**: HR Admin

### `DELETE /api/v1/performance/rating-scales/{scale_id}`
Soft-delete a rating scale.
- **Path Param**: `scale_id`
- **Response**: Success message
- **Access**: HR Admin

### `GET /api/v1/performance/rating-scales/{scale_id}/usage`
Check which templates and cycles are using this rating scale.
- **Path Param**: `scale_id`
- **Response**: `{templates: [], cycles: []}`
- **Access**: HR Admin

---

## 9. APPRAISAL TEMPLATES

### `GET /api/v1/performance/appraisal-templates`
List all appraisal templates.
- **Query Params**: `is_active`, `is_default`, `applicable_department`, `page`, `limit`
- **Response**: Paginated list of templates
- **Access**: HR Admin

### `POST /api/v1/performance/appraisal-templates`
Create a new appraisal template.
- **Request Body**: `name`, `description`, `rating_scale_id`, `applicable_roles`, `applicable_departments`, `applicable_grades`, section weight config, self-appraisal config, manager config, `final_rating_formula`
- **Response**: Created template
- **Access**: HR Admin

### `GET /api/v1/performance/appraisal-templates/{template_id}`
Get full template with sections and questions.
- **Path Param**: `template_id`
- **Response**: Template with nested sections → questions
- **Access**: HR Admin, Manager, Employee

### `PUT /api/v1/performance/appraisal-templates/{template_id}`
Update an appraisal template.
- **Path Param**: `template_id`
- **Request Body**: Updated template fields
- **Response**: Updated template
- **Access**: HR Admin

### `POST /api/v1/performance/appraisal-templates/{template_id}/clone`
Clone an existing template to create a new version.
- **Path Param**: `template_id`
- **Request Body**: `new_name`, `version_notes`
- **Response**: Cloned template
- **Access**: HR Admin

### `PATCH /api/v1/performance/appraisal-templates/{template_id}/set-default`
Mark template as the organization default.
- **Path Param**: `template_id`
- **Response**: Updated template
- **Access**: HR Admin

### `DELETE /api/v1/performance/appraisal-templates/{template_id}`
Soft-delete a template.
- **Path Param**: `template_id`
- **Response**: Success message
- **Access**: HR Admin

### `GET /api/v1/performance/appraisal-templates/{template_id}/preview`
Preview the full rendered template as it would appear to an employee.
- **Path Param**: `template_id`
- **Response**: Rendered form structure with question types and guidance
- **Access**: HR Admin

### `POST /api/v1/performance/appraisal-templates/{template_id}/reorder-sections`
Reorder sections within a template.
- **Path Param**: `template_id`
- **Request Body**: `[{section_id, new_order}]`
- **Response**: Updated section order
- **Access**: HR Admin

### `GET /api/v1/performance/appraisal-templates/{template_id}/usage`
Show which cycles currently use this template.
- **Path Param**: `template_id`
- **Response**: `{cycles: []}`
- **Access**: HR Admin

---

## 10. APPRAISAL SECTIONS

### `GET /api/v1/performance/appraisal-templates/{template_id}/sections`
List all sections in a template.
- **Path Param**: `template_id`
- **Response**: Ordered list of sections with question counts
- **Access**: HR Admin

### `POST /api/v1/performance/appraisal-templates/{template_id}/sections`
Add a new section to a template.
- **Path Param**: `template_id`
- **Request Body**: `title`, `description`, `section_order`, `weight`, `section_type`, `is_required`, `instructions`, `visible_to_employee`, `visible_to_manager`
- **Response**: Created section
- **Access**: HR Admin

### `GET /api/v1/performance/appraisal-sections/{section_id}`
Get a specific section with its questions.
- **Path Param**: `section_id`
- **Response**: Section detail with nested questions
- **Access**: HR Admin

### `PUT /api/v1/performance/appraisal-sections/{section_id}`
Update an appraisal section.
- **Path Param**: `section_id`
- **Request Body**: Updated section fields
- **Response**: Updated section
- **Access**: HR Admin

### `DELETE /api/v1/performance/appraisal-sections/{section_id}`
Delete a section (only if no active appraisals use it).
- **Path Param**: `section_id`
- **Response**: Success message
- **Access**: HR Admin

### `POST /api/v1/performance/appraisal-sections/{section_id}/reorder-questions`
Reorder questions within a section.
- **Path Param**: `section_id`
- **Request Body**: `[{question_id, new_order}]`
- **Response**: Updated question order
- **Access**: HR Admin

### `PATCH /api/v1/performance/appraisal-sections/bulk-weight`
Update weights for all sections in a template in one call.
- **Request Body**: `template_id`, `[{section_id, weight}]`
- **Response**: Validation (must sum to 100%) + updated sections
- **Access**: HR Admin

---

## 11. APPRAISAL QUESTIONS

### `GET /api/v1/performance/appraisal-sections/{section_id}/questions`
List all questions in a section.
- **Path Param**: `section_id`
- **Response**: Ordered list of questions
- **Access**: HR Admin

### `POST /api/v1/performance/appraisal-sections/{section_id}/questions`
Add a question to a section.
- **Path Param**: `section_id`
- **Request Body**: `question_text`, `question_type`, `question_order`, `is_required`, `weight`, `use_section_rating_scale`, `custom_rating_scale_id`, `choices`, `allow_multiple_selection`, `competency_id`, `auto_populate_goals`, `guidance`, `placeholder_text`
- **Response**: Created question
- **Access**: HR Admin

### `GET /api/v1/performance/appraisal-questions/{question_id}`
Get a specific question.
- **Path Param**: `question_id`
- **Response**: Question detail
- **Access**: HR Admin

### `PUT /api/v1/performance/appraisal-questions/{question_id}`
Update a question.
- **Path Param**: `question_id`
- **Request Body**: Updated question fields
- **Response**: Updated question
- **Access**: HR Admin

### `DELETE /api/v1/performance/appraisal-questions/{question_id}`
Delete a question.
- **Path Param**: `question_id`
- **Response**: Success message
- **Access**: HR Admin

### `POST /api/v1/performance/appraisal-questions/bulk-create`
Bulk add multiple questions to a section.
- **Request Body**: `section_id`, `questions: [...]`
- **Response**: List of created questions
- **Access**: HR Admin

### `POST /api/v1/performance/appraisal-questions/{question_id}/duplicate`
Duplicate a question within the same or another section.
- **Path Param**: `question_id`
- **Request Body**: `target_section_id`
- **Response**: Duplicated question
- **Access**: HR Admin

---

## 12. APPRAISAL RECORDS

### `GET /api/v1/performance/appraisal-records`
List appraisal records for a cycle.
- **Query Params**: `appraisal_cycle_id`, `employee_id`, `manager_id`, `department_id`, `status`, `page`, `limit`
- **Response**: Paginated list of appraisal records with status and scores
- **Access**: HR Admin, Manager (team), Employee (self)

### `GET /api/v1/performance/appraisal-records/{record_id}`
Get full appraisal record for an employee.
- **Path Param**: `record_id`
- **Response**: Complete record with self, manager, and final scores
- **Access**: HR Admin, Manager (own team), Employee (self)

### `GET /api/v1/performance/appraisal-records/my-appraisal`
Get the authenticated employee's appraisal record for the active cycle.
- **Query Params**: `appraisal_cycle_id`
- **Response**: Own appraisal record with status and instructions
- **Access**: Employee

### `GET /api/v1/performance/appraisal-records/team-appraisals`
Get all appraisal records for a manager's direct reports.
- **Query Params**: `appraisal_cycle_id`, `status`, `page`, `limit`
- **Response**: Team appraisal status list
- **Access**: Manager, HR Admin

### `PATCH /api/v1/performance/appraisal-records/{record_id}/publish`
Publish an individual appraisal record to the employee.
- **Path Param**: `record_id`
- **Response**: Published record
- **Access**: HR Admin

### `PATCH /api/v1/performance/appraisal-records/{record_id}/acknowledge`
Employee acknowledges their published appraisal.
- **Path Param**: `record_id`
- **Request Body**: `acknowledged` (boolean), `employee_disagreement_reason`
- **Response**: Acknowledged record
- **Access**: Employee (self)

### `PATCH /api/v1/performance/appraisal-records/{record_id}/calibrate`
Apply a calibrated/normalized final score to an appraisal record.
- **Path Param**: `record_id`
- **Request Body**: `calibrated_score`, `final_rating_label`, `calibration_notes`
- **Response**: Updated record with calibrated scores
- **Access**: HR Admin, Calibrator

### `PATCH /api/v1/performance/appraisal-records/{record_id}/recommend-promotion`
Flag promotion recommendation on an appraisal record.
- **Path Param**: `record_id`
- **Request Body**: `promotion_recommended`, `promotion_recommended_to_grade`, `notes`
- **Response**: Updated record
- **Access**: Manager, HR Admin

### `GET /api/v1/performance/appraisal-records/{record_id}/history`
Get status change and audit history for an appraisal record.
- **Path Param**: `record_id`
- **Response**: Timeline of status changes and score updates
- **Access**: HR Admin

### `POST /api/v1/performance/appraisal-records/bulk-publish`
Bulk publish appraisal records for a cycle.
- **Request Body**: `appraisal_cycle_id`, `department_ids`, `rating_labels` (optional filter)
- **Response**: `{published_count, skipped_count}`
- **Access**: HR Admin

### `GET /api/v1/performance/appraisal-records/{record_id}/export`
Export an employee's appraisal record as PDF.
- **Path Param**: `record_id`
- **Response**: PDF file download
- **Access**: HR Admin, Manager, Employee (self, after publish)

### `POST /api/v1/performance/appraisal-cycles/{cycle_id}/generate-records`
Manually trigger record generation for eligible employees in a cycle.
- **Path Param**: `cycle_id`
- **Response**: `{records_created, already_existed, skipped_ineligible}`
- **Access**: HR Admin

---

## 13. SELF-APPRAISAL

### `GET /api/v1/performance/appraisal-records/{record_id}/self-appraisal`
Get the employee's self-appraisal form (pre-populated with questions and existing answers).
- **Path Param**: `record_id`
- **Response**: Form structure with sections, questions, and saved answers
- **Access**: Employee (self), Manager, HR Admin

### `PUT /api/v1/performance/appraisal-records/{record_id}/self-appraisal`
Save (draft) or update self-appraisal progress.
- **Path Param**: `record_id`
- **Request Body**: `achievements_summary`, `challenges_faced`, `learning_development`, `career_aspirations`, `support_needed`, `answers: [{question_id, rating_value, text_answer, goal_id, goal_achievement_percentage}]`
- **Response**: Updated self-appraisal with completion percentage
- **Access**: Employee (self)

### `POST /api/v1/performance/appraisal-records/{record_id}/self-appraisal/submit`
Submit the self-appraisal (locks it for manager review).
- **Path Param**: `record_id`
- **Response**: Submitted self-appraisal and updated appraisal record status
- **Access**: Employee (self)

### `POST /api/v1/performance/appraisal-records/{record_id}/self-appraisal/reopen`
Reopen a submitted self-appraisal (within allowed window).
- **Path Param**: `record_id`
- **Request Body**: `reason`
- **Response**: Reopened self-appraisal
- **Access**: HR Admin

### `GET /api/v1/performance/appraisal-records/{record_id}/self-appraisal/completion`
Get completion percentage and unanswered required questions.
- **Path Param**: `record_id`
- **Response**: `{completion_percentage, answered_count, total_required, pending_questions: []}`
- **Access**: Employee (self), HR Admin

### `GET /api/v1/performance/appraisal-records/{record_id}/self-appraisal/goals`
Get employee goals auto-populated for the self-appraisal form.
- **Path Param**: `record_id`
- **Response**: List of linked goals for rating in the self-appraisal
- **Access**: Employee (self), Manager, HR Admin

### `GET /api/v1/performance/self-appraisals/pending`
Get list of employees whose self-appraisals are pending (for HR/managers).
- **Query Params**: `appraisal_cycle_id`, `department_id`, `manager_id`, `days_to_deadline`
- **Response**: List of pending self-appraisals with employee and deadline info
- **Access**: HR Admin, Manager

---

## 14. MANAGER APPRAISAL

### `GET /api/v1/performance/appraisal-records/{record_id}/manager-appraisal`
Get the manager's evaluation form for a direct report.
- **Path Param**: `record_id`
- **Response**: Form with employee's self-appraisal scores (if configured), questions, and saved answers
- **Access**: Manager (own report), HR Admin

### `PUT /api/v1/performance/appraisal-records/{record_id}/manager-appraisal`
Save (draft) manager evaluation progress.
- **Path Param**: `record_id`
- **Request Body**: `performance_summary`, `strengths`, `areas_for_improvement`, `development_plan`, `promotion_recommendation`, `answers: [...]`
- **Response**: Updated manager appraisal with completion %
- **Access**: Manager, HR Admin

### `POST /api/v1/performance/appraisal-records/{record_id}/manager-appraisal/submit`
Submit the manager's evaluation.
- **Path Param**: `record_id`
- **Response**: Submitted manager appraisal; triggers calibration or publish based on cycle config
- **Access**: Manager, HR Admin

### `POST /api/v1/performance/appraisal-records/{record_id}/manager-appraisal/reopen`
Reopen a submitted manager evaluation.
- **Path Param**: `record_id`
- **Request Body**: `reason`
- **Response**: Reopened evaluation
- **Access**: HR Admin

### `GET /api/v1/performance/manager-appraisals/pending`
Get manager's pending evaluations.
- **Query Params**: `appraisal_cycle_id`, `days_to_deadline`
- **Response**: List of employees awaiting manager review
- **Access**: Manager, HR Admin

### `GET /api/v1/performance/appraisal-records/{record_id}/score-comparison`
Side-by-side comparison of self vs. manager scores per section.
- **Path Param**: `record_id`
- **Response**: `{sections: [{title, self_score, manager_score, delta}]}`
- **Access**: Manager, HR Admin

### `PATCH /api/v1/performance/appraisal-records/{record_id}/manager-appraisal/override-score`
Manager manually overrides a final computed score with justification.
- **Path Param**: `record_id`
- **Request Body**: `manager_overall_score`, `manager_rating_label`, `override_reason`
- **Response**: Updated appraisal record
- **Access**: Manager, HR Admin

---

## 15. APPRAISAL ANSWERS

### `GET /api/v1/performance/appraisal-records/{record_id}/answers`
Get all answers for a record (self and/or manager).
- **Path Param**: `record_id`
- **Query Params**: `respondent_type` (self/manager), `section_id`
- **Response**: List of question answers with ratings and text
- **Access**: Manager, HR Admin, Employee (self answers)

### `POST /api/v1/performance/appraisal-records/{record_id}/answers`
Submit or update an individual answer.
- **Path Param**: `record_id`
- **Request Body**: `question_id`, `respondent_type`, `rating_value`, `text_answer`, `selected_choices`, `goal_id`, `goal_achievement_percentage`, `competency_id`
- **Response**: Saved answer with computed weighted_score
- **Access**: Employee (self), Manager, HR Admin

### `POST /api/v1/performance/appraisal-records/{record_id}/answers/bulk`
Submit multiple answers in one batch request.
- **Path Param**: `record_id`
- **Request Body**: `respondent_type`, `answers: [...]`
- **Response**: `{saved_count, validation_errors}`
- **Access**: Employee (self), Manager, HR Admin

### `GET /api/v1/performance/appraisal-records/{record_id}/answers/scores`
Compute section-wise and overall scores from current answers.
- **Path Param**: `record_id`
- **Query Params**: `respondent_type`
- **Response**: `{sections: [{title, weight, score, weighted_score}], overall_score}`
- **Access**: Manager, HR Admin, Employee (self only)

### `DELETE /api/v1/performance/appraisal-records/{record_id}/answers/{answer_id}`
Delete a specific answer (only in draft state).
- **Path Param**: `record_id`, `answer_id`
- **Response**: Success message
- **Access**: HR Admin

### `GET /api/v1/performance/appraisal-records/{record_id}/answers/export`
Export all answers as a formatted sheet for offline review.
- **Path Param**: `record_id`
- **Response**: Excel/CSV file
- **Access**: Manager, HR Admin

---

## 16. CALIBRATION

### `GET /api/v1/performance/calibrations`
List calibration sessions for a cycle.
- **Query Params**: `appraisal_cycle_id`, `department_id`, `status`, `page`, `limit`
- **Response**: Paginated calibration session list
- **Access**: HR Admin, Calibrator

### `POST /api/v1/performance/calibrations`
Create a new calibration session.
- **Request Body**: `appraisal_cycle_id`, `name`, `department_id`, `scheduled_date`, `facilitator_id`, `target_distribution`
- **Response**: Created calibration session
- **Access**: HR Admin

### `GET /api/v1/performance/calibrations/{calibration_id}`
Get details of a calibration session including participants and distribution.
- **Path Param**: `calibration_id`
- **Response**: Session detail with target vs. actual distribution
- **Access**: HR Admin, Calibrator

### `PUT /api/v1/performance/calibrations/{calibration_id}`
Update calibration session details.
- **Path Param**: `calibration_id`
- **Request Body**: `name`, `scheduled_date`, `facilitator_id`, `target_distribution`, `notes`
- **Response**: Updated session
- **Access**: HR Admin

### `PATCH /api/v1/performance/calibrations/{calibration_id}/start`
Mark calibration session as In Progress.
- **Path Param**: `calibration_id`
- **Request Body**: `conducted_date`
- **Response**: Updated session
- **Access**: HR Admin, Facilitator

### `PATCH /api/v1/performance/calibrations/{calibration_id}/complete`
Complete a calibration session and lock calibrated scores.
- **Path Param**: `calibration_id`
- **Request Body**: `session_notes`, `meeting_minutes`, `actual_distribution`
- **Response**: Completed session with final distribution
- **Access**: HR Admin, Facilitator

### `GET /api/v1/performance/calibrations/{calibration_id}/employees`
Get the list of employees in scope for a calibration session with their current scores.
- **Path Param**: `calibration_id`
- **Response**: Employee list with self, manager, and current calibrated scores
- **Access**: HR Admin, Calibrator

### `GET /api/v1/performance/calibrations/{calibration_id}/distribution`
Get the current rating distribution vs. bell curve target.
- **Path Param**: `calibration_id`
- **Response**: `{label, target_pct, target_count, actual_count, actual_pct, variance}` per rating
- **Access**: HR Admin, Calibrator

### `POST /api/v1/performance/calibrations/{calibration_id}/participants`
Add participants (managers/HR) to a calibration session.
- **Path Param**: `calibration_id`
- **Request Body**: `participants: [{employee_id, role}]`
- **Response**: Updated participant list
- **Access**: HR Admin

### `DELETE /api/v1/performance/calibrations/{calibration_id}`
Cancel and delete a calibration session.
- **Path Param**: `calibration_id`
- **Response**: Success message
- **Access**: HR Admin

---

## 17. BELL CURVE DISTRIBUTION

### `GET /api/v1/performance/appraisal-cycles/{cycle_id}/bell-curve`
Get bell curve distribution for a cycle (org-wide or by department).
- **Path Param**: `cycle_id`
- **Query Params**: `department_id`
- **Response**: Per-rating distribution with target vs. actual counts and variance
- **Access**: HR Admin, Calibrator

### `POST /api/v1/performance/appraisal-cycles/{cycle_id}/bell-curve/compute`
Recompute the actual distribution based on current calibrated scores.
- **Path Param**: `cycle_id`
- **Request Body**: `department_id`
- **Response**: Refreshed distribution
- **Access**: HR Admin

### `PUT /api/v1/performance/appraisal-cycles/{cycle_id}/bell-curve/targets`
Update the target distribution percentages for a cycle.
- **Path Param**: `cycle_id`
- **Request Body**: `department_id`, `distribution: [{rating_label, target_percentage}]`
- **Response**: Updated distribution targets
- **Access**: HR Admin

### `GET /api/v1/performance/appraisal-cycles/{cycle_id}/bell-curve/outliers`
List employees whose scores fall significantly outside the expected distribution.
- **Path Param**: `cycle_id`
- **Query Params**: `department_id`, `threshold_variance`
- **Response**: Employee list with scores and deviation flags
- **Access**: HR Admin

### `GET /api/v1/performance/appraisal-cycles/{cycle_id}/bell-curve/normalization-suggestions`
Generate normalization suggestions to bring distribution within targets.
- **Path Param**: `cycle_id`
- **Query Params**: `department_id`
- **Response**: `{suggested_adjustments: [{employee_id, current_label, suggested_label, delta}]}`
- **Access**: HR Admin

---

## 18. 360 FEEDBACK QUESTIONS

### `GET /api/v1/performance/feedback-questions`
List feedback questions in the question bank.
- **Query Params**: `provider_type`, `question_type`, `competency_id`, `is_active`, `tags`, `page`, `limit`
- **Response**: Paginated list of feedback questions
- **Access**: HR Admin

### `POST /api/v1/performance/feedback-questions`
Add a new question to the 360 feedback question bank.
- **Request Body**: `question_text`, `question_type`, `provider_type`, `is_anonymous_allowed`, `competency_id`, `rating_scale_id`, `choices`, `tags`
- **Response**: Created question
- **Access**: HR Admin

### `GET /api/v1/performance/feedback-questions/{question_id}`
Get a specific feedback question.
- **Path Param**: `question_id`
- **Response**: Question detail
- **Access**: HR Admin

### `PUT /api/v1/performance/feedback-questions/{question_id}`
Update a feedback question.
- **Path Param**: `question_id`
- **Request Body**: Updated fields
- **Response**: Updated question
- **Access**: HR Admin

### `DELETE /api/v1/performance/feedback-questions/{question_id}`
Soft-delete a feedback question.
- **Path Param**: `question_id`
- **Response**: Success message
- **Access**: HR Admin

### `POST /api/v1/performance/feedback-questions/bulk-import`
Import questions from a CSV/Excel template.
- **Request Body**: `file` (multipart), `organization_id`
- **Response**: `{imported_count, failed_rows}`
- **Access**: HR Admin

### `GET /api/v1/performance/feedback-questions/export`
Export the question bank as Excel/CSV.
- **Response**: File download
- **Access**: HR Admin

---

## 19. 360 FEEDBACK REQUESTS

### `GET /api/v1/performance/feedback-requests`
List 360 feedback requests.
- **Query Params**: `appraisal_cycle_id`, `employee_id`, `status`, `page`, `limit`
- **Response**: Paginated list of requests with provider counts
- **Access**: HR Admin, Manager, Employee (self)

### `POST /api/v1/performance/feedback-requests`
Create a 360 feedback request for an employee.
- **Request Body**: `appraisal_cycle_id`, `employee_id`, `due_date`, `initiated_by`, `is_anonymous`, `min_peer_responses`, `min_subordinate_responses`
- **Response**: Created feedback request
- **Access**: HR Admin, Manager, Employee (self-initiate)

### `GET /api/v1/performance/feedback-requests/{request_id}`
Get details of a feedback request including provider statuses.
- **Path Param**: `request_id`
- **Response**: Request detail with provider list and completion counts
- **Access**: HR Admin, Manager, Employee (self)

### `PATCH /api/v1/performance/feedback-requests/{request_id}/close`
Close a feedback request (no more responses accepted).
- **Path Param**: `request_id`
- **Response**: Closed request
- **Access**: HR Admin, Manager

### `GET /api/v1/performance/feedback-requests/{request_id}/summary`
Get aggregated 360 feedback summary for an employee (post-collection).
- **Path Param**: `request_id`
- **Response**: `{avg_rating, per_competency_avg, themes, provider_type_breakdown}`
- **Access**: HR Admin, Manager, Employee (self, after release)

### `POST /api/v1/performance/feedback-requests/{request_id}/send-reminders`
Send reminders to providers who haven't responded.
- **Path Param**: `request_id`
- **Request Body**: `provider_ids` (optional, defaults to all pending)
- **Response**: `{sent_count}`
- **Access**: HR Admin, Manager, Employee (self)

### `GET /api/v1/performance/feedback-requests/pending-for-me`
Get all 360 feedback requests where the logged-in user is a provider.
- **Query Params**: `status`, `page`, `limit`
- **Response**: Pending feedback requests to complete
- **Access**: Employee

### `POST /api/v1/performance/appraisal-cycles/{cycle_id}/feedback-requests/bulk-create`
Bulk create feedback requests for all eligible employees in a cycle.
- **Path Param**: `cycle_id`
- **Request Body**: `is_anonymous`, `due_date`, `min_peer_responses`
- **Response**: `{created_count, already_existed}`
- **Access**: HR Admin

### `DELETE /api/v1/performance/feedback-requests/{request_id}`
Delete a feedback request (only in PENDING status).
- **Path Param**: `request_id`
- **Response**: Success message
- **Access**: HR Admin

---

## 20. FEEDBACK PROVIDERS

### `GET /api/v1/performance/feedback-requests/{request_id}/providers`
List all nominated providers for a feedback request.
- **Path Param**: `request_id`
- **Response**: Provider list with type, approval status, and completion status
- **Access**: HR Admin, Manager, Employee (self)

### `POST /api/v1/performance/feedback-requests/{request_id}/providers`
Nominate providers (peers, subordinates, supervisors) for a feedback request.
- **Path Param**: `request_id`
- **Request Body**: `providers: [{employee_id, provider_type}]`
- **Response**: Added providers with approval pending flag
- **Access**: Employee (self), Manager, HR Admin

### `PATCH /api/v1/performance/feedback-requests/{request_id}/providers/{provider_id}/approve`
Manager approves or rejects a provider nomination.
- **Path Param**: `request_id`, `provider_id`
- **Request Body**: `approved` (boolean), `rejection_reason`
- **Response**: Updated provider record
- **Access**: Manager, HR Admin

### `DELETE /api/v1/performance/feedback-requests/{request_id}/providers/{provider_id}`
Remove a nominated provider.
- **Path Param**: `request_id`, `provider_id`
- **Response**: Success message
- **Access**: Employee (self, before approval), Manager, HR Admin

### `POST /api/v1/performance/feedback-requests/{request_id}/providers/{provider_id}/resend-invite`
Resend invitation to a specific provider.
- **Path Param**: `request_id`, `provider_id`
- **Response**: `{invite_sent_at}`
- **Access**: HR Admin, Manager

### `GET /api/v1/performance/feedback-requests/{request_id}/providers/completion-status`
Get completion status breakdown by provider type.
- **Path Param**: `request_id`
- **Response**: `{peer: {total, completed, pending}, subordinate: {...}, supervisor: {...}}`
- **Access**: HR Admin, Manager

### `POST /api/v1/performance/feedback-requests/{request_id}/providers/bulk-approve`
Bulk approve all pending provider nominations.
- **Path Param**: `request_id`
- **Response**: `{approved_count}`
- **Access**: Manager, HR Admin

---

## 21. FEEDBACK RESPONSES

### `GET /api/v1/performance/feedback-responses/{response_token}`
Get the feedback form for a provider using their anonymous token.
- **Path Param**: `response_token`
- **Response**: Form questions and provider context (without revealing the subject's identity if anonymous)
- **Access**: Public (token-based)

### `PUT /api/v1/performance/feedback-responses/{response_token}`
Save (draft) feedback response via token.
- **Path Param**: `response_token`
- **Request Body**: `answers: [{question_id, rating, text}]`, `overall_comments`, `strengths_observed`, `development_suggestions`, `overall_rating`
- **Response**: Saved draft
- **Access**: Public (token-based)

### `POST /api/v1/performance/feedback-responses/{response_token}/submit`
Submit feedback response (locks it).
- **Path Param**: `response_token`
- **Response**: Submitted confirmation
- **Access**: Public (token-based)

### `GET /api/v1/performance/feedback-requests/{request_id}/responses`
List all submitted responses for a feedback request (anonymized per config).
- **Path Param**: `request_id`
- **Response**: Anonymized responses with ratings and comments
- **Access**: HR Admin, Manager (after collection closed), Employee (self, after release)

### `GET /api/v1/performance/feedback-requests/{request_id}/responses/analytics`
Get aggregated analytics across all responses for a feedback request.
- **Path Param**: `request_id`
- **Response**: `{per_question_avg, per_competency_avg, sentiment_themes, score_distribution}`
- **Access**: HR Admin, Manager

### `DELETE /api/v1/performance/feedback-responses/{response_id}`
Delete a specific response (only in draft state).
- **Path Param**: `response_id`
- **Response**: Success message
- **Access**: HR Admin

### `GET /api/v1/performance/feedback-requests/{request_id}/responses/export`
Export all responses for a feedback request as Excel.
- **Path Param**: `request_id`
- **Response**: Excel file download (anonymized)
- **Access**: HR Admin, Manager

---

## 22. COMPETENCY FRAMEWORK

### `GET /api/v1/performance/competencies`
List all competencies in the framework.
- **Query Params**: `category`, `is_active`, `is_core`, `search`, `tags`, `page`, `limit`
- **Response**: Paginated list of competencies
- **Access**: HR Admin, Manager, Employee

### `POST /api/v1/performance/competencies`
Create a new competency.
- **Request Body**: `name`, `description`, `category`, `is_core`, `proficiency_levels: [{level, label, description}]`, `behavioral_indicators`, `tags`
- **Response**: Created competency
- **Access**: HR Admin

### `GET /api/v1/performance/competencies/{competency_id}`
Get a competency with all proficiency levels and behavioral indicators.
- **Path Param**: `competency_id`
- **Response**: Full competency detail
- **Access**: HR Admin, Manager, Employee

### `PUT /api/v1/performance/competencies/{competency_id}`
Update a competency.
- **Path Param**: `competency_id`
- **Request Body**: Updated fields
- **Response**: Updated competency
- **Access**: HR Admin

### `DELETE /api/v1/performance/competencies/{competency_id}`
Soft-delete a competency.
- **Path Param**: `competency_id`
- **Response**: Success message
- **Access**: HR Admin

### `GET /api/v1/performance/competencies/{competency_id}/mappings`
Get all role/department mappings for a competency.
- **Path Param**: `competency_id`
- **Response**: Mapping list with required proficiency levels
- **Access**: HR Admin

### `GET /api/v1/performance/competencies/for-role/{role_id}`
Get all competencies required for a specific role.
- **Path Param**: `role_id`
- **Response**: Competency list with required proficiency levels
- **Access**: HR Admin, Manager, Employee

### `POST /api/v1/performance/competencies/bulk-import`
Import competencies from a structured Excel/CSV template.
- **Request Body**: `file` (multipart)
- **Response**: `{imported_count, failed_rows}`
- **Access**: HR Admin

---

## 23. COMPETENCY MAPPING

### `GET /api/v1/performance/competency-mappings`
List competency-to-role/department mappings.
- **Query Params**: `role_id`, `department_id`, `competency_id`, `page`, `limit`
- **Response**: Paginated mapping list
- **Access**: HR Admin

### `POST /api/v1/performance/competency-mappings`
Map a competency to a role, department, or grade.
- **Request Body**: `competency_id`, `role_id` OR `department_id` OR `grade_id`, `required_proficiency_level`, `weight`, `is_mandatory`
- **Response**: Created mapping
- **Access**: HR Admin

### `GET /api/v1/performance/competency-mappings/{mapping_id}`
Get a specific mapping detail.
- **Path Param**: `mapping_id`
- **Response**: Mapping with competency and target info
- **Access**: HR Admin

### `PUT /api/v1/performance/competency-mappings/{mapping_id}`
Update a competency mapping.
- **Path Param**: `mapping_id`
- **Request Body**: `required_proficiency_level`, `weight`, `is_mandatory`
- **Response**: Updated mapping
- **Access**: HR Admin

### `DELETE /api/v1/performance/competency-mappings/{mapping_id}`
Delete a competency mapping.
- **Path Param**: `mapping_id`
- **Response**: Success message
- **Access**: HR Admin

### `POST /api/v1/performance/competency-mappings/bulk`
Bulk map multiple competencies to a role/department.
- **Request Body**: `target_type`, `target_id`, `mappings: [{competency_id, required_proficiency_level, weight}]`
- **Response**: `{created_count, updated_count}`
- **Access**: HR Admin

---

## 24. EMPLOYEE COMPETENCY

### `GET /api/v1/performance/employee-competencies`
List competency assessments for an employee.
- **Query Params**: `employee_id`, `appraisal_cycle_id`, `competency_id`, `page`, `limit`
- **Response**: Paginated list with self, manager, and final ratings + gap
- **Access**: HR Admin, Manager (team), Employee (self)

### `POST /api/v1/performance/employee-competencies`
Create or update a competency assessment for an employee.
- **Request Body**: `employee_id`, `competency_id`, `appraisal_cycle_id`, `appraisal_record_id`, `self_rating`, `manager_rating`, `final_rating`, `feedback_360_rating`, `self_comments`, `manager_comments`, `assessed_date`
- **Response**: Saved employee competency record
- **Access**: HR Admin, Manager

### `GET /api/v1/performance/employee-competencies/{competency_record_id}`
Get a specific competency assessment.
- **Path Param**: `competency_record_id`
- **Response**: Assessment detail with gap computation
- **Access**: HR Admin, Manager, Employee (self)

### `PUT /api/v1/performance/employee-competencies/{competency_record_id}`
Update a competency assessment.
- **Path Param**: `competency_record_id`
- **Request Body**: Updated ratings and comments
- **Response**: Updated record
- **Access**: HR Admin, Manager

### `GET /api/v1/performance/employees/{employee_id}/competency-history`
Get historical competency ratings across all appraisal cycles.
- **Path Param**: `employee_id`
- **Response**: Per-competency trend data across cycles
- **Access**: HR Admin, Manager, Employee (self)

### `GET /api/v1/performance/employees/{employee_id}/competency-radar`
Get radar chart data for an employee's competency scores.
- **Path Param**: `employee_id`
- **Query Params**: `appraisal_cycle_id`
- **Response**: `{competencies: [{name, self_rating, manager_rating, required_level, gap}]}`
- **Access**: HR Admin, Manager, Employee (self)

### `POST /api/v1/performance/employee-competencies/bulk`
Bulk submit competency ratings for a team.
- **Request Body**: `appraisal_cycle_id`, `ratings: [{employee_id, competency_id, manager_rating}]`
- **Response**: `{saved_count, errors}`
- **Access**: Manager, HR Admin

---

## 25. SKILLS GAP ANALYSIS

### `GET /api/v1/performance/skills-gap-analyses`
List skills gap analyses.
- **Query Params**: `employee_id`, `appraisal_cycle_id`, `development_priority`, `page`, `limit`
- **Response**: Paginated list of analyses
- **Access**: HR Admin, Manager, Employee (self)

### `POST /api/v1/performance/skills-gap-analyses`
Create a new skills gap analysis for an employee.
- **Request Body**: `employee_id`, `appraisal_cycle_id`, `analysis_date`, `gap_details`, `recommended_training`, `development_priority`, `notes`
- **Response**: Created analysis
- **Access**: HR Admin, Manager

### `GET /api/v1/performance/skills-gap-analyses/{analysis_id}`
Get a specific skills gap analysis.
- **Path Param**: `analysis_id`
- **Response**: Full analysis with per-competency gaps and recommendations
- **Access**: HR Admin, Manager, Employee (self)

### `PUT /api/v1/performance/skills-gap-analyses/{analysis_id}`
Update a skills gap analysis.
- **Path Param**: `analysis_id`
- **Request Body**: Updated gap details and recommendations
- **Response**: Updated analysis
- **Access**: HR Admin, Manager

### `POST /api/v1/performance/skills-gap-analyses/auto-compute`
Auto-compute a skills gap analysis from existing competency assessment data.
- **Request Body**: `employee_id`, `appraisal_cycle_id`
- **Response**: Auto-generated gap analysis
- **Access**: HR Admin, Manager

### `GET /api/v1/performance/skills-gap-analyses/department-summary`
Department-level aggregated skills gap summary.
- **Query Params**: `department_id`, `appraisal_cycle_id`
- **Response**: `{top_gaps: [], average_readiness_score, critical_skills_needed}`
- **Access**: HR Admin, Manager

---

## 26. CONTINUOUS FEEDBACK

### `GET /api/v1/performance/continuous-feedback`
List continuous feedback given or received.
- **Query Params**: `giver_id`, `receiver_id`, `feedback_type`, `competency_id`, `from_date`, `to_date`, `page`, `limit`
- **Response**: Paginated feedback list
- **Access**: HR Admin, Manager, Employee

### `POST /api/v1/performance/continuous-feedback`
Submit real-time feedback for a colleague.
- **Request Body**: `receiver_id`, `feedback_type`, `feedback_text`, `competency_id`, `goal_id`, `is_anonymous`, `is_visible_to_manager`, `tags`
- **Response**: Created feedback
- **Access**: Manager, Employee

### `GET /api/v1/performance/continuous-feedback/{feedback_id}`
Get a specific feedback entry.
- **Path Param**: `feedback_id`
- **Response**: Feedback detail
- **Access**: HR Admin, Giver, Receiver, Receiver's Manager

### `PUT /api/v1/performance/continuous-feedback/{feedback_id}`
Update feedback (only giver, within edit window).
- **Path Param**: `feedback_id`
- **Request Body**: `feedback_text`, `competency_id`, `tags`
- **Response**: Updated feedback
- **Access**: Giver (self)

### `DELETE /api/v1/performance/continuous-feedback/{feedback_id}`
Delete a feedback entry.
- **Path Param**: `feedback_id`
- **Response**: Success message
- **Access**: Giver (self, draft only), HR Admin

### `PATCH /api/v1/performance/continuous-feedback/{feedback_id}/acknowledge`
Receiver acknowledges feedback.
- **Path Param**: `feedback_id`
- **Request Body**: `receiver_reaction` (helpful/not_relevant)
- **Response**: Acknowledged feedback
- **Access**: Receiver (self)

### `GET /api/v1/performance/continuous-feedback/received`
Get all feedback received by the logged-in employee.
- **Query Params**: `feedback_type`, `from_date`, `to_date`, `page`, `limit`
- **Response**: Received feedback list (anonymized where applicable)
- **Access**: Employee (self)

### `GET /api/v1/performance/continuous-feedback/given`
Get all feedback given by the logged-in employee.
- **Query Params**: `feedback_type`, `from_date`, `to_date`, `page`, `limit`
- **Response**: Given feedback list
- **Access**: Employee (self), Manager

### `GET /api/v1/performance/continuous-feedback/team-summary`
Summary of feedback activity for a manager's team.
- **Query Params**: `from_date`, `to_date`
- **Response**: `{employees: [{name, received_count, praise_count, constructive_count}]}`
- **Access**: Manager, HR Admin

---

## 27. ONE-ON-ONE MEETINGS

### `GET /api/v1/performance/one-on-ones`
List 1-on-1 meetings.
- **Query Params**: `manager_id`, `employee_id`, `status`, `meeting_type`, `from_date`, `to_date`, `page`, `limit`
- **Response**: Paginated list of meetings
- **Access**: HR Admin, Manager, Employee (self)

### `POST /api/v1/performance/one-on-ones`
Schedule a new 1-on-1 meeting.
- **Request Body**: `employee_id`, `scheduled_date`, `duration_minutes`, `location`, `meeting_type`, `is_recurring`, `recurrence_pattern`, `recurrence_end_date`, `pre_meeting_notes`, `appraisal_cycle_id`
- **Response**: Created meeting (and series if recurring)
- **Access**: Manager, HR Admin

### `GET /api/v1/performance/one-on-ones/{meeting_id}`
Get details of a 1-on-1 meeting including agenda items.
- **Path Param**: `meeting_id`
- **Response**: Meeting with agenda items and action items
- **Access**: Manager, Employee (self), HR Admin

### `PUT /api/v1/performance/one-on-ones/{meeting_id}`
Update a 1-on-1 meeting.
- **Path Param**: `meeting_id`
- **Request Body**: Updated meeting fields
- **Response**: Updated meeting
- **Access**: Manager, HR Admin

### `PATCH /api/v1/performance/one-on-ones/{meeting_id}/complete`
Mark a meeting as completed and save notes.
- **Path Param**: `meeting_id`
- **Request Body**: `meeting_notes`, `key_decisions`, `completed_at`
- **Response**: Completed meeting
- **Access**: Manager, HR Admin

### `PATCH /api/v1/performance/one-on-ones/{meeting_id}/cancel`
Cancel a 1-on-1 meeting.
- **Path Param**: `meeting_id`
- **Request Body**: `cancelled_reason`
- **Response**: Cancelled meeting
- **Access**: Manager, Employee, HR Admin

### `PATCH /api/v1/performance/one-on-ones/{meeting_id}/reschedule`
Reschedule a meeting to a new time.
- **Path Param**: `meeting_id`
- **Request Body**: `new_scheduled_date`, `reason`
- **Response**: Rescheduled meeting
- **Access**: Manager, Employee, HR Admin

### `DELETE /api/v1/performance/one-on-ones/{meeting_id}`
Delete a meeting (and optionally the series).
- **Path Param**: `meeting_id`
- **Query Params**: `delete_series` (boolean)
- **Response**: Success message
- **Access**: Manager, HR Admin

### `GET /api/v1/performance/one-on-ones/upcoming`
Get upcoming 1-on-1 meetings for the logged-in user.
- **Query Params**: `days_ahead`, `limit`
- **Response**: Sorted list of upcoming meetings
- **Access**: Manager, Employee

### `GET /api/v1/performance/one-on-ones/{meeting_id}/pending-action-items`
Get open/pending action items from a meeting.
- **Path Param**: `meeting_id`
- **Response**: List of incomplete action items with assignees and due dates
- **Access**: Manager, Employee (self)

### `GET /api/v1/performance/one-on-ones/my-meetings`
Get the authenticated user's 1-on-1 history and upcoming meetings.
- **Query Params**: `from_date`, `to_date`, `status`, `page`, `limit`
- **Response**: Meeting list with agenda summary
- **Access**: Employee, Manager

---

## 28. AGENDA ITEMS

### `GET /api/v1/performance/one-on-ones/{meeting_id}/agenda`
Get all agenda and action items for a meeting.
- **Path Param**: `meeting_id`
- **Response**: Ordered list grouped by item_type
- **Access**: Manager, Employee (self)

### `POST /api/v1/performance/one-on-ones/{meeting_id}/agenda`
Add an agenda item or action item to a meeting.
- **Path Param**: `meeting_id`
- **Request Body**: `item_type`, `title`, `description`, `item_order`, `assigned_to`, `due_date`
- **Response**: Created agenda item
- **Access**: Manager, Employee (self)

### `PUT /api/v1/performance/one-on-ones/{meeting_id}/agenda/{item_id}`
Update an agenda item.
- **Path Param**: `meeting_id`, `item_id`
- **Request Body**: Updated item fields
- **Response**: Updated item
- **Access**: Manager, Employee (self)

### `PATCH /api/v1/performance/one-on-ones/{meeting_id}/agenda/{item_id}/complete`
Mark an action item as completed.
- **Path Param**: `meeting_id`, `item_id`
- **Request Body**: `completion_notes`
- **Response**: Completed item
- **Access**: Manager, Employee (self)

### `PATCH /api/v1/performance/one-on-ones/{meeting_id}/agenda/{item_id}/carry-forward`
Carry an open action item forward to the next meeting.
- **Path Param**: `meeting_id`, `item_id`
- **Request Body**: `next_meeting_id`
- **Response**: Carried-forward item in next meeting
- **Access**: Manager

### `DELETE /api/v1/performance/one-on-ones/{meeting_id}/agenda/{item_id}`
Remove an agenda item.
- **Path Param**: `meeting_id`, `item_id`
- **Response**: Success message
- **Access**: Manager, Employee (self)

### `POST /api/v1/performance/one-on-ones/{meeting_id}/agenda/reorder`
Reorder agenda items.
- **Path Param**: `meeting_id`
- **Request Body**: `[{item_id, new_order}]`
- **Response**: Updated order
- **Access**: Manager

### `GET /api/v1/performance/action-items/my-open`
Get all open action items assigned to the logged-in user across all meetings.
- **Query Params**: `overdue_only`, `page`, `limit`
- **Response**: Action items with meeting context and due dates
- **Access**: Manager, Employee

---

## 29. PERFORMANCE NOTES

### `GET /api/v1/performance/performance-notes`
List performance notes.
- **Query Params**: `employee_id`, `manager_id`, `note_type`, `from_date`, `to_date`, `is_private`, `page`, `limit`
- **Response**: Paginated note list
- **Access**: HR Admin, Manager (own team), Employee (shared notes only)

### `POST /api/v1/performance/performance-notes`
Create a performance note.
- **Request Body**: `employee_id`, `note_type`, `note_date`, `title`, `content`, `is_private`, `is_shared_with_employee`, `goal_id`, `competency_id`, `one_on_one_id`, `tags`, `attachments`
- **Response**: Created note
- **Access**: Manager, HR Admin

### `GET /api/v1/performance/performance-notes/{note_id}`
Get a specific performance note.
- **Path Param**: `note_id`
- **Response**: Note detail
- **Access**: HR Admin, Manager (author), Employee (if shared)

### `PUT /api/v1/performance/performance-notes/{note_id}`
Update a performance note.
- **Path Param**: `note_id`
- **Request Body**: Updated note fields
- **Response**: Updated note
- **Access**: Manager (author), HR Admin

### `DELETE /api/v1/performance/performance-notes/{note_id}`
Delete a performance note.
- **Path Param**: `note_id`
- **Response**: Success message
- **Access**: Manager (author), HR Admin

### `PATCH /api/v1/performance/performance-notes/{note_id}/share`
Share a private note with the employee.
- **Path Param**: `note_id`
- **Response**: Updated note
- **Access**: Manager (author)

### `GET /api/v1/performance/employees/{employee_id}/performance-notes/timeline`
Get a chronological timeline of performance notes for an employee.
- **Path Param**: `employee_id`
- **Query Params**: `from_date`, `to_date`, `note_type`
- **Response**: Timeline with grouping by month
- **Access**: HR Admin, Manager

---

## 30. PIP PLANS

### `GET /api/v1/performance/pip-plans`
List PIPs with filters.
- **Query Params**: `employee_id`, `manager_id`, `hr_owner_id`, `status`, `department_id`, `page`, `limit`
- **Response**: Paginated PIP list with current status
- **Access**: HR Admin, Manager (own team), Employee (self)

### `POST /api/v1/performance/pip-plans`
Create a new Performance Improvement Plan.
- **Request Body**: `employee_id`, `manager_id`, `hr_owner_id`, `title`, `reason`, `start_date`, `end_date`, `review_frequency`, `support_resources`, `appraisal_record_id`, `attachments`
- **Response**: Created PIP in DRAFT status
- **Access**: HR Admin, Manager

### `GET /api/v1/performance/pip-plans/{pip_id}`
Get full PIP detail including objectives and progress logs.
- **Path Param**: `pip_id`
- **Response**: PIP with objectives and progress history
- **Access**: HR Admin, Manager, Employee (self)

### `PUT /api/v1/performance/pip-plans/{pip_id}`
Update a PIP (only in DRAFT status).
- **Path Param**: `pip_id`
- **Request Body**: Updated PIP fields
- **Response**: Updated PIP
- **Access**: HR Admin, Manager

### `PATCH /api/v1/performance/pip-plans/{pip_id}/activate`
Activate a PIP (sends it to the employee for acknowledgment).
- **Path Param**: `pip_id`
- **Response**: Activated PIP
- **Access**: HR Admin

### `PATCH /api/v1/performance/pip-plans/{pip_id}/acknowledge`
Employee acknowledges the PIP.
- **Path Param**: `pip_id`
- **Request Body**: `acknowledged` (boolean), `employee_comments`
- **Response**: Acknowledged PIP
- **Access**: Employee (self)

### `PATCH /api/v1/performance/pip-plans/{pip_id}/close`
Close a PIP with outcome (Success/Failure/Withdrawn).
- **Path Param**: `pip_id`
- **Request Body**: `status`, `outcome_notes`, `closed_at`
- **Response**: Closed PIP
- **Access**: HR Admin

### `PATCH /api/v1/performance/pip-plans/{pip_id}/hr-approve`
HR approves a PIP before it is activated.
- **Path Param**: `pip_id`
- **Request Body**: `approved` (boolean), `hr_approval_notes`
- **Response**: Approved/rejected PIP
- **Access**: HR Admin

### `GET /api/v1/performance/pip-plans/{pip_id}/timeline`
Get a full event timeline for a PIP (creation, activation, logs, closure).
- **Path Param**: `pip_id`
- **Response**: Chronological events
- **Access**: HR Admin, Manager, Employee (self)

### `DELETE /api/v1/performance/pip-plans/{pip_id}`
Delete a PIP (only in DRAFT status).
- **Path Param**: `pip_id`
- **Response**: Success message
- **Access**: HR Admin

### `GET /api/v1/performance/pip-plans/active`
Get all currently active PIPs in the organization.
- **Query Params**: `department_id`, `manager_id`
- **Response**: Active PIP list with status summaries
- **Access**: HR Admin

---

## 31. PIP OBJECTIVES

### `GET /api/v1/performance/pip-plans/{pip_id}/objectives`
List all objectives in a PIP.
- **Path Param**: `pip_id`
- **Response**: Ordered list of objectives with progress
- **Access**: HR Admin, Manager, Employee (self)

### `POST /api/v1/performance/pip-plans/{pip_id}/objectives`
Add an objective to a PIP.
- **Path Param**: `pip_id`
- **Request Body**: `title`, `description`, `success_criteria`, `measurement_type`, `target_value`, `unit`, `due_date`, `priority`
- **Response**: Created objective
- **Access**: HR Admin, Manager

### `GET /api/v1/performance/pip-objectives/{objective_id}`
Get a specific PIP objective.
- **Path Param**: `objective_id`
- **Response**: Objective detail with progress history
- **Access**: HR Admin, Manager, Employee (self)

### `PUT /api/v1/performance/pip-objectives/{objective_id}`
Update a PIP objective (in active PIPs with HR approval).
- **Path Param**: `objective_id`
- **Request Body**: Updated objective fields
- **Response**: Updated objective
- **Access**: HR Admin, Manager

### `PATCH /api/v1/performance/pip-objectives/{objective_id}/close`
Close an objective with outcome notes.
- **Path Param**: `objective_id`
- **Request Body**: `status`, `achievement_percentage`, `outcome_notes`
- **Response**: Closed objective
- **Access**: HR Admin, Manager

### `DELETE /api/v1/performance/pip-objectives/{objective_id}`
Delete a PIP objective (only in DRAFT PIP).
- **Path Param**: `objective_id`
- **Response**: Success message
- **Access**: HR Admin, Manager

### `GET /api/v1/performance/pip-plans/{pip_id}/objectives/completion-summary`
Get completion percentage across all objectives in a PIP.
- **Path Param**: `pip_id`
- **Response**: `{overall_completion, objectives: [{title, progress, status}]}`
- **Access**: HR Admin, Manager, Employee (self)

---

## 32. PIP PROGRESS LOGS

### `GET /api/v1/performance/pip-plans/{pip_id}/progress-logs`
List all progress logs for a PIP.
- **Path Param**: `pip_id`
- **Response**: Chronological progress logs
- **Access**: HR Admin, Manager, Employee (self)

### `POST /api/v1/performance/pip-plans/{pip_id}/progress-logs`
Submit a new PIP progress check-in.
- **Path Param**: `pip_id`
- **Request Body**: `log_date`, `objective_updates: [{objective_id, current_value, progress, status, notes}]`, `overall_status`, `observations`, `manager_recommendations`, `support_given`, `next_review_date`, `meeting_held`, `meeting_notes`
- **Response**: Created progress log
- **Access**: Manager, HR Admin

### `GET /api/v1/performance/pip-plans/{pip_id}/progress-logs/{log_id}`
Get a specific progress log entry.
- **Path Param**: `pip_id`, `log_id`
- **Response**: Progress log detail
- **Access**: HR Admin, Manager, Employee (self)

### `PATCH /api/v1/performance/pip-plans/{pip_id}/progress-logs/{log_id}/employee-response`
Employee adds their response to a progress log.
- **Path Param**: `pip_id`, `log_id`
- **Request Body**: `employee_response`
- **Response**: Updated log with employee response
- **Access**: Employee (self)

### `PUT /api/v1/performance/pip-plans/{pip_id}/progress-logs/{log_id}`
Update a progress log.
- **Path Param**: `pip_id`, `log_id`
- **Request Body**: Updated log fields
- **Response**: Updated log
- **Access**: HR Admin, Manager

### `DELETE /api/v1/performance/pip-plans/{pip_id}/progress-logs/{log_id}`
Delete a progress log.
- **Path Param**: `pip_id`, `log_id`
- **Response**: Success message
- **Access**: HR Admin

---

## 33. TALENT REVIEW

### `GET /api/v1/performance/talent-reviews`
List talent review sessions.
- **Query Params**: `appraisal_cycle_id`, `department_id`, `status`, `page`, `limit`
- **Response**: Paginated list of talent review sessions
- **Access**: HR Admin

### `POST /api/v1/performance/talent-reviews`
Create a new talent review session.
- **Request Body**: `name`, `review_date`, `appraisal_cycle_id`, `department_id`, `facilitator_id`, `notes`
- **Response**: Created talent review
- **Access**: HR Admin

### `GET /api/v1/performance/talent-reviews/{review_id}`
Get details of a talent review session with participant summary.
- **Path Param**: `review_id`
- **Response**: Review detail with 9-box distribution
- **Access**: HR Admin

### `PUT /api/v1/performance/talent-reviews/{review_id}`
Update a talent review session.
- **Path Param**: `review_id`
- **Request Body**: Updated fields
- **Response**: Updated review
- **Access**: HR Admin

### `PATCH /api/v1/performance/talent-reviews/{review_id}/status`
Update status of a talent review session.
- **Path Param**: `review_id`
- **Request Body**: `status`, `session_minutes`
- **Response**: Updated review
- **Access**: HR Admin

### `GET /api/v1/performance/talent-reviews/{review_id}/nine-box`
Get 9-box grid data for a talent review session.
- **Path Param**: `review_id`
- **Response**: `{boxes: [{position, employees: [{id, name, performance, potential}]}]}`
- **Access**: HR Admin

### `DELETE /api/v1/performance/talent-reviews/{review_id}`
Delete a talent review (only in DRAFT).
- **Path Param**: `review_id`
- **Response**: Success message
- **Access**: HR Admin

### `GET /api/v1/performance/talent-reviews/{review_id}/export`
Export talent review results as Excel.
- **Path Param**: `review_id`
- **Response**: Excel file download
- **Access**: HR Admin

### `POST /api/v1/performance/talent-reviews/{review_id}/participants/bulk-add`
Bulk add employees from a department/cycle into a talent review.
- **Path Param**: `review_id`
- **Request Body**: `department_id`, `appraisal_cycle_id`, `minimum_tenure_days`
- **Response**: `{added_count, already_existed}`
- **Access**: HR Admin

---

## 34. TALENT REVIEW PARTICIPANTS

### `GET /api/v1/performance/talent-reviews/{review_id}/participants`
List all participants in a talent review.
- **Path Param**: `review_id`
- **Query Params**: `nine_box_position`, `talent_category`, `flight_risk`, `readiness_for_promotion`, `page`, `limit`
- **Response**: Paginated participant list
- **Access**: HR Admin

### `POST /api/v1/performance/talent-reviews/{review_id}/participants`
Add an employee to a talent review.
- **Path Param**: `review_id`
- **Request Body**: `employee_id`, `performance_rating`, `potential_rating`, `nine_box_position`, `talent_category`, `flight_risk`, `flight_risk_reason`, `readiness_for_promotion`, `development_needs`, `retention_priority`, `is_key_talent`, `is_succession_candidate`, `reviewer_comments`
- **Response**: Added participant
- **Access**: HR Admin

### `GET /api/v1/performance/talent-reviews/{review_id}/participants/{participant_id}`
Get a specific participant assessment.
- **Path Param**: `review_id`, `participant_id`
- **Response**: Participant detail
- **Access**: HR Admin

### `PUT /api/v1/performance/talent-reviews/{review_id}/participants/{participant_id}`
Update a participant's talent assessment.
- **Path Param**: `review_id`, `participant_id`
- **Request Body**: Updated assessment fields
- **Response**: Updated participant
- **Access**: HR Admin

### `DELETE /api/v1/performance/talent-reviews/{review_id}/participants/{participant_id}`
Remove a participant from a talent review.
- **Path Param**: `review_id`, `participant_id`
- **Response**: Success message
- **Access**: HR Admin

### `GET /api/v1/performance/talent-reviews/{review_id}/participants/high-potential`
Filter and list high-potential employees from a talent review.
- **Path Param**: `review_id`
- **Response**: Filtered list with development readiness info
- **Access**: HR Admin

### `GET /api/v1/performance/talent-reviews/{review_id}/participants/flight-risk`
List employees flagged as flight risk.
- **Path Param**: `review_id`
- **Query Params**: `risk_level` (HIGH/MEDIUM)
- **Response**: Flight risk list with retention priority
- **Access**: HR Admin

### `PATCH /api/v1/performance/talent-reviews/{review_id}/participants/bulk-update`
Bulk update 9-box positions for multiple participants.
- **Path Param**: `review_id`
- **Request Body**: `updates: [{participant_id, nine_box_position, talent_category}]`
- **Response**: `{updated_count}`
- **Access**: HR Admin

---

## 35. SUCCESSION PLANS

### `GET /api/v1/performance/succession-plans`
List succession plans.
- **Query Params**: `department_id`, `role_id`, `position_criticality`, `is_active`, `page`, `limit`
- **Response**: Paginated plan list with candidate counts
- **Access**: HR Admin

### `POST /api/v1/performance/succession-plans`
Create a new succession plan for a critical role.
- **Request Body**: `position_title`, `department_id`, `role_id`, `incumbent_employee_id`, `position_criticality`, `plan_owner_id`, `review_frequency`, `notes`
- **Response**: Created succession plan
- **Access**: HR Admin

### `GET /api/v1/performance/succession-plans/{plan_id}`
Get succession plan detail with candidates.
- **Path Param**: `plan_id`
- **Response**: Plan with ranked candidates and readiness summary
- **Access**: HR Admin

### `PUT /api/v1/performance/succession-plans/{plan_id}`
Update a succession plan.
- **Path Param**: `plan_id`
- **Request Body**: Updated plan fields
- **Response**: Updated plan
- **Access**: HR Admin

### `PATCH /api/v1/performance/succession-plans/{plan_id}/toggle-active`
Activate or deactivate a succession plan.
- **Path Param**: `plan_id`
- **Response**: Updated plan
- **Access**: HR Admin

### `DELETE /api/v1/performance/succession-plans/{plan_id}`
Delete a succession plan.
- **Path Param**: `plan_id`
- **Response**: Success message
- **Access**: HR Admin

### `GET /api/v1/performance/succession-plans/coverage-report`
Report on roles with and without succession plans.
- **Query Params**: `department_id`, `criticality`
- **Response**: `{covered_roles_count, uncovered_roles_count, uncovered_roles: []}`
- **Access**: HR Admin

### `GET /api/v1/performance/succession-plans/{plan_id}/readiness-summary`
Get candidate readiness overview for a succession plan.
- **Path Param**: `plan_id`
- **Response**: `{ready_now_count, ready_1yr_count, ready_3yr_count, top_candidate}`
- **Access**: HR Admin

---

## 36. SUCCESSION CANDIDATES

### `GET /api/v1/performance/succession-plans/{plan_id}/candidates`
List candidates for a succession plan.
- **Path Param**: `plan_id`
- **Query Params**: `readiness`, `is_primary_candidate`, `is_active`, `page`, `limit`
- **Response**: Ranked candidate list
- **Access**: HR Admin

### `POST /api/v1/performance/succession-plans/{plan_id}/candidates`
Add a candidate to a succession plan.
- **Path Param**: `plan_id`
- **Request Body**: `employee_id`, `readiness`, `readiness_score`, `gap_assessment`, `development_plan`, `is_primary_candidate`, `priority_rank`, `retention_risk`, `notes`
- **Response**: Added candidate
- **Access**: HR Admin

### `GET /api/v1/performance/succession-plans/{plan_id}/candidates/{candidate_id}`
Get a specific succession candidate.
- **Path Param**: `plan_id`, `candidate_id`
- **Response**: Candidate with gap analysis and development plan
- **Access**: HR Admin

### `PUT /api/v1/performance/succession-plans/{plan_id}/candidates/{candidate_id}`
Update a succession candidate's assessment.
- **Path Param**: `plan_id`, `candidate_id`
- **Request Body**: Updated candidate fields
- **Response**: Updated candidate
- **Access**: HR Admin

### `DELETE /api/v1/performance/succession-plans/{plan_id}/candidates/{candidate_id}`
Remove a candidate from a succession plan.
- **Path Param**: `plan_id`, `candidate_id`
- **Response**: Success message
- **Access**: HR Admin

### `PATCH /api/v1/performance/succession-plans/{plan_id}/candidates/rerank`
Reorder candidate priority rankings.
- **Path Param**: `plan_id`
- **Request Body**: `[{candidate_id, priority_rank}]`
- **Response**: Updated rankings
- **Access**: HR Admin

### `GET /api/v1/performance/employees/{employee_id}/succession-plans`
Get all succession plans where an employee is a candidate.
- **Path Param**: `employee_id`
- **Response**: List of succession plans with readiness details
- **Access**: HR Admin

### `GET /api/v1/performance/succession-plans/{plan_id}/candidates/export`
Export candidates list as Excel.
- **Path Param**: `plan_id`
- **Response**: File download
- **Access**: HR Admin

---

## 37. PERFORMANCE ANALYTICS

### `GET /api/v1/performance/analytics/cycle-summary`
Overall cycle-level performance summary dashboard.
- **Query Params**: `appraisal_cycle_id`, `department_id`
- **Response**: `{avg_score, rating_distribution, completion_rates, goal_achievement_avg, top_performers, improvement_needed}`
- **Access**: HR Admin, Manager

### `GET /api/v1/performance/analytics/rating-trends`
Rating trend over multiple appraisal cycles.
- **Query Params**: `employee_id`, `department_id`, `from_cycle_id`, `to_cycle_id`
- **Response**: Per-cycle average scores with trend line data
- **Access**: HR Admin, Manager, Employee (self)

### `GET /api/v1/performance/analytics/goal-completion`
Goal completion analytics.
- **Query Params**: `appraisal_cycle_id`, `department_id`, `framework_type`, `employee_id`
- **Response**: `{overall_completion_rate, on_track_pct, at_risk_pct, behind_pct, per_framework_breakdown}`
- **Access**: HR Admin, Manager, Employee (self)

### `GET /api/v1/performance/analytics/competency-heatmap`
Competency strength/gap heatmap across the organization or department.
- **Query Params**: `appraisal_cycle_id`, `department_id`
- **Response**: `{competencies: [{name, avg_score, required_avg, gap}]}` — suitable for heatmap rendering
- **Access**: HR Admin, Manager

### `GET /api/v1/performance/analytics/nine-box-distribution`
Org-wide or department 9-box talent distribution.
- **Query Params**: `talent_review_id`, `department_id`
- **Response**: Count and percentage per 9-box cell
- **Access**: HR Admin

### `GET /api/v1/performance/analytics/feedback-participation`
360 feedback participation rates by department.
- **Query Params**: `appraisal_cycle_id`, `department_id`
- **Response**: `{response_rate_pct, completed_count, pending_count, by_provider_type}`
- **Access**: HR Admin

### `GET /api/v1/performance/analytics/pip-summary`
Summary of PIP activity and outcomes.
- **Query Params**: `from_date`, `to_date`, `department_id`, `status`
- **Response**: `{active_count, closed_success, closed_failure, withdrawn, avg_duration_days}`
- **Access**: HR Admin

### `GET /api/v1/performance/analytics/employee-report/{employee_id}`
Comprehensive performance report for a single employee across cycles.
- **Path Param**: `employee_id`
- **Response**: Multi-cycle report with goals, competencies, ratings, feedback, and PIP history
- **Access**: HR Admin, Manager (own team), Employee (self)

### `GET /api/v1/performance/analytics/department-report`
Department-level performance summary report.
- **Query Params**: `department_id`, `appraisal_cycle_id`
- **Response**: Department KPIs, top performers, at-risk employees, skill gaps
- **Access**: HR Admin, Manager

### `POST /api/v1/performance/analytics/export`
Export analytics data as Excel/PDF.
- **Request Body**: `report_type`, `appraisal_cycle_id`, `department_ids`, `format`
- **Response**: Downloadable file
- **Access**: HR Admin

---

## 38. NOTIFICATIONS

### `GET /api/v1/performance/notifications`
List performance notifications for the logged-in user.
- **Query Params**: `is_read`, `notification_type`, `appraisal_cycle_id`, `page`, `limit`
- **Response**: Paginated notification list
- **Access**: Employee, Manager, HR Admin

### `PATCH /api/v1/performance/notifications/{notification_id}/read`
Mark a notification as read.
- **Path Param**: `notification_id`
- **Response**: Updated notification
- **Access**: Recipient (self)

### `PATCH /api/v1/performance/notifications/mark-all-read`
Mark all unread notifications as read.
- **Response**: `{updated_count}`
- **Access**: Employee, Manager, HR Admin

### `GET /api/v1/performance/notifications/unread-count`
Get unread notification count for the logged-in user.
- **Response**: `{count}`
- **Access**: Employee, Manager, HR Admin

### `POST /api/v1/performance/notifications/send`
Manually trigger a notification (bulk or individual).
- **Request Body**: `notification_type`, `appraisal_cycle_id`, `recipient_ids`, `channel`, `custom_message`
- **Response**: `{sent_count, failed_count}`
- **Access**: HR Admin

### `DELETE /api/v1/performance/notifications/{notification_id}`
Delete a notification.
- **Path Param**: `notification_id`
- **Response**: Success message
- **Access**: Recipient (self), HR Admin

### `GET /api/v1/performance/notifications/delivery-report`
Get notification delivery statistics for a cycle.
- **Query Params**: `appraisal_cycle_id`, `notification_type`, `from_date`, `to_date`
- **Response**: `{total_sent, delivered, bounced, failed, open_rate}`
- **Access**: HR Admin

### `POST /api/v1/performance/notifications/schedule`
Schedule a future notification batch.
- **Request Body**: `notification_type`, `appraisal_cycle_id`, `send_at`, `recipient_group`, `channel`
- **Response**: Scheduled notification record
- **Access**: HR Admin

---

## 39. NOTIFICATION TEMPLATES

### `GET /api/v1/performance/notification-templates`
List all notification templates.
- **Query Params**: `notification_type`, `channel`, `is_active`, `page`, `limit`
- **Response**: Paginated list
- **Access**: HR Admin

### `POST /api/v1/performance/notification-templates`
Create a new notification template.
- **Request Body**: `name`, `notification_type`, `channel`, `subject`, `body_template`, `is_default`
- **Response**: Created template
- **Access**: HR Admin

### `GET /api/v1/performance/notification-templates/{template_id}`
Get a notification template.
- **Path Param**: `template_id`
- **Response**: Template with available merge variables list
- **Access**: HR Admin

### `PUT /api/v1/performance/notification-templates/{template_id}`
Update a notification template.
- **Path Param**: `template_id`
- **Request Body**: Updated template fields
- **Response**: Updated template
- **Access**: HR Admin

### `POST /api/v1/performance/notification-templates/{template_id}/preview`
Preview a notification template with sample data.
- **Path Param**: `template_id`
- **Request Body**: `sample_data: {employee_name, due_date, cycle_name, ...}`
- **Response**: Rendered subject and body
- **Access**: HR Admin

### `DELETE /api/v1/performance/notification-templates/{template_id}`
Delete a notification template.
- **Path Param**: `template_id`
- **Response**: Success message
- **Access**: HR Admin

---

## 40. COMPENSATION INTEGRATION

### `GET /api/v1/performance/compensation-integrations`
List compensation integration records for a cycle.
- **Query Params**: `appraisal_cycle_id`, `department_id`, `status`, `promotion_recommended`, `page`, `limit`
- **Response**: Paginated list
- **Access**: HR Admin

### `GET /api/v1/performance/compensation-integrations/{integration_id}`
Get a specific compensation integration record.
- **Path Param**: `integration_id`
- **Response**: Full record with appraisal outcome and recommendations
- **Access**: HR Admin

### `PUT /api/v1/performance/compensation-integrations/{integration_id}`
Update compensation recommendation for an appraisal.
- **Path Param**: `integration_id`
- **Request Body**: `merit_increase_recommended`, `merit_increase_percentage`, `bonus_recommended`, `bonus_amount`, `bonus_type`, `promotion_recommended`, `recommended_grade`, `recommended_role_id`
- **Response**: Updated record
- **Access**: HR Admin, Manager

### `PATCH /api/v1/performance/compensation-integrations/{integration_id}/submit`
Submit compensation recommendation to the compensation module.
- **Path Param**: `integration_id`
- **Response**: Submitted record with compensation_action reference
- **Access**: HR Admin

### `POST /api/v1/performance/appraisal-cycles/{cycle_id}/compensation-integrations/bulk-submit`
Bulk submit all compensation recommendations for a cycle.
- **Path Param**: `cycle_id`
- **Request Body**: `department_ids`, `rating_filter`
- **Response**: `{submitted_count, skipped_count}`
- **Access**: HR Admin

### `GET /api/v1/performance/appraisal-cycles/{cycle_id}/compensation-integrations/summary`
Compensation recommendation summary for a cycle.
- **Path Param**: `cycle_id`
- **Query Params**: `department_id`
- **Response**: `{merit_increase_count, avg_increase_pct, bonus_count, total_bonus_amount, promotion_count}`
- **Access**: HR Admin

### `GET /api/v1/performance/compensation-integrations/promotions`
List all promotion recommendations for a cycle.
- **Query Params**: `appraisal_cycle_id`, `department_id`, `status`
- **Response**: Promotion recommendations with recommended grade and role
- **Access**: HR Admin

### `GET /api/v1/performance/compensation-integrations/export`
Export compensation recommendations as Excel for upload to payroll.
- **Query Params**: `appraisal_cycle_id`, `department_id`
- **Response**: Excel file download
- **Access**: HR Admin

---

## API Summary

| Group | API Count |
|---|---|
| Goal Framework | 6 |
| Organization Goals | 8 |
| Department Goals | 8 |
| Employee Goals | 11 |
| Goal Progress | 6 |
| Goal Alignment | 5 |
| Appraisal Cycles | 12 |
| Rating Scales | 7 |
| Appraisal Templates | 10 |
| Appraisal Sections | 7 |
| Appraisal Questions | 7 |
| Appraisal Records | 12 |
| Self-Appraisal | 7 |
| Manager Appraisal | 7 |
| Appraisal Answers | 6 |
| Calibration | 10 |
| Bell Curve | 5 |
| 360 Feedback Questions | 7 |
| 360 Feedback Requests | 9 |
| Feedback Providers | 7 |
| Feedback Responses | 7 |
| Competency Framework | 8 |
| Competency Mapping | 6 |
| Employee Competency | 7 |
| Skills Gap Analysis | 6 |
| Continuous Feedback | 9 |
| 1-on-1 Meetings | 11 |
| Agenda Items | 8 |
| Performance Notes | 7 |
| PIP Plans | 11 |
| PIP Objectives | 7 |
| PIP Progress Logs | 6 |
| Talent Review | 9 |
| Talent Review Participants | 8 |
| Succession Plans | 8 |
| Succession Candidates | 8 |
| Performance Analytics | 10 |
| Notifications | 8 |
| Notification Templates | 6 |
| Compensation Integration | 8 |
| **GRAND TOTAL** | **~300 APIs** |
