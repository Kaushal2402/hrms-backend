# Payroll API Agent System

This directory contains a **self-improving dual-agent system** that auto-generates all payroll API schemas and endpoints by learning from the existing codebase.

## Architecture

```
Generator Agent ──generates──► Reviewer Agent ──PASS──► Write to disk
      ▲                               │
      └──────── FAIL + report ────────┘ (max 3 cycles)
                      ↓
              Feedback Store (learns common mistakes)
```

## Files

| File | Purpose |
|------|---------|
| `orchestrator.py` | Master controller — run this |
| `generator_agent.py` | Produces schemas + endpoints using Gemini |
| `reviewer_agent.py` | Reviews code with 10-point checklist |
| `context_extractor.py` | Reads codebase → style guide (run once) |
| `business_rules.py` | Payroll business logic constants |
| `codebase_style_guide.json` | Extracted patterns (auto-generated) |
| `feedback_store.json` | Persistent mistake memory (grows over time) |

## Setup

```bash
# 1. Set your Gemini API key
export GEMINI_API_KEY="your-key-here"

# 2. Install dependency (already done)
./hrmenv/bin/pip install google-generativeai
```

## Usage

```bash
# Run ALL modules end-to-end:
./hrmenv/bin/python agents/orchestrator.py

# Run a SINGLE module:
./hrmenv/bin/python agents/orchestrator.py --module salary_components

# Force regenerate (even if file exists):
./hrmenv/bin/python agents/orchestrator.py --module salary_components --force

# Dry run (build prompts, no API call):
./hrmenv/bin/python agents/orchestrator.py --dry-run

# Skip already-generated modules:
./hrmenv/bin/python agents/orchestrator.py  # auto-skips existing files
```

## Module Priority (order of generation)

1. `salary_components`
2. `salary_templates`
3. `employee_salaries`
4. `payroll_periods`
5. `payslips`
6. `loans`
7. `reimbursements`
8. `final_settlements`
9. `arrears_one_time`
10. `tax_declarations`
11. `bank_files`
12. `reconciliations`
13. `journal_entries`
14. `statutory_forms`
15. `reports`
16. `bulk_operations`
17. `bank_accounts`
18. `audit_logs`

## Generated File Locations

- Schemas: `app/schemas/payroll_{module}.py`
- Endpoints: `app/api/v1/endpoints/payroll_{module}.py`
- Routers registered in: `app/api/v1/api.py`

## Reviewer Checklist (10 items, must average ≥ 8.0 to pass)

1. `pattern_consistency` — Matches project patterns exactly
2. `multi_tenancy` — Every query filters `organization_id`
3. `uuid_path_params` — URL path params use `uuid.UUID`, not int
4. `pagination_correct` — List endpoints have page/limit/total_pages
5. `schema_config` — All schemas have `from_attributes = True`
6. `no_enum_redeclaration` — Enums imported from models
7. `create_update_schema` — Create/Update schemas are correct
8. `rbac_enforced` — Every protected endpoint checks permissions
9. `business_rules` — All module-specific rules implemented
10. `error_handling` — Consistent HTTPException/JSONResponse pattern

## Self-Improvement

The `feedback_store.json` accumulates:
- Common mistakes (with frequency count and which modules)
- Improvement hints from the reviewer
- Per-module quality scores
- Average cycles to pass

On each new generation, the Generator Agent reads this file and pre-emptively avoids known mistakes.

## Permission Codes (101–140)

See `app/core/permissions.py` for the full registry.

| Module | READ | CREATE | UPDATE | APPROVE/PROCESS |
|--------|------|--------|--------|-----------------|
| Salary Components | 101 | 102 | 103 | 104 |
| Employee Salaries | 105 | 106 | 107 | 108 |
| Payroll Periods | 109 | 110 | 111 | 112 |
| Payslips | 113 | 114 | 115 | — |
| Loans | 116 | 117 | — | 118 |
| Reimbursements | 119 | 120 | — | 121 |
| Tax Declarations | 122 | 123 | — | 124 |
| Bank Files | 125 | 126 | — | — |
| Audit Logs | 127 | — | — | — |
| Final Settlements | 128 | 129 | — | 130 |
| Arrears | 131 | 132 | — | 133 |
| Reports | 134 | — | — | — |
| Statutory Forms | 135 | 136 | — | — |
| Reconciliations | 137 | 138 | — | — |
| Journal Entries | 139 | 140 | — | — |


