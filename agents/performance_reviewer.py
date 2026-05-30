"""
performance_reviewer.py
Reviews generated performance schema and endpoint files against checklist.
"""

import json
import os
import sys
import re
import argparse
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
AGENTS_DIR = Path(__file__).parent
FEEDBACK_STORE_PATH = AGENTS_DIR / "performance_feedback_store.json"

sys.path.insert(0, str(BASE_DIR))

PASS_THRESHOLD = 8.0


def static_checks(schema_code: str, endpoint_code: str, module: str) -> list[dict]:
    issues = []

    # ── Multi-tenancy ──────────────────────────────────────────────────────
    if "organization_id" not in endpoint_code:
        issues.append({
            "severity": "CRITICAL",
            "file": f"performance_{module}.py",
            "line_hint": "all query filters",
            "issue": "Missing organization_id filter — data from ALL orgs would be exposed",
            "fix": "Add .filter(XxxModel.organization_id == current_org.id) to every db.query()"
        })

    # ── UUID in paths ──────────────────────────────────────────────────────
    path_int_pattern = re.findall(r'@router\.[a-z]+\(["\'].*?/\{(\w+_id)\}', endpoint_code)
    for param in path_int_pattern:
        if f"{param}: int" in endpoint_code or f"{param}: Integer" in endpoint_code:
            issues.append({
                "severity": "CRITICAL",
                "file": f"performance_{module}.py",
                "line_hint": f"path param {param}",
                "issue": f"Path param '{param}' uses int type — must use uuid.UUID",
                "fix": f"Change '{param}: int' to '{param}: uuid.UUID'"
            })

    # ── Pagination on list endpoints ───────────────────────────────────────
    list_endpoints = re.findall(r"@router\.get\(['\"]\/['\"]", endpoint_code)
    if list_endpoints and "page" not in endpoint_code:
        issues.append({
            "severity": "CRITICAL",
            "file": f"performance_{module}.py",
            "line_hint": "GET / list endpoint",
            "issue": "List endpoint missing pagination params (page, limit)",
            "fix": "Add 'page: int = Query(1, ge=1)' and 'limit: int = Query(10, ge=1, le=100)'"
        })

    if list_endpoints and "total_records" not in endpoint_code:
        issues.append({
            "severity": "CRITICAL",
            "file": f"performance_{module}.py",
            "line_hint": "GET / list endpoint response",
            "issue": "List response missing pagination dict with total_records",
            "fix": "Return pagination={'total_records': N, 'current_page': page, 'total_pages': N, 'page_size': limit}"
        })

    # ── Schema Config ──────────────────────────────────────────────────────
    schema_classes = re.findall(r"class (\w+)\(BaseModel\)", schema_code)
    config_count = schema_code.count("from_attributes = True")
    response_schemas = [c for c in schema_classes if c.endswith("Schema") or c.endswith("Response") or c.endswith("Out")]
    if len(response_schemas) > 0 and config_count == 0:
        issues.append({
            "severity": "MAJOR",
            "file": f"performance_{module}_schema.py",
            "line_hint": "all Schema classes",
            "issue": "No schema has 'from_attributes = True' in Config",
            "fix": "Add 'class Config: from_attributes = True' to all *Schema classes"
        })

    # ── Enum re-declaration ────────────────────────────────────────────────
    performance_enums = [
        'GoalFrameworkType', 'GoalMeasurementType', 'GoalStatus', 'GoalType', 
        'AppraisalStatus', 'CycleFrequency', 'CycleStatus', 'QuestionType', 
        'FeedbackProviderType', 'RespondentType', 'FeedbackRequestStatus', 
        'FeedbackProviderStatus', 'NineBoxPosition', 'TalentReviewStatus', 
        'PipStatus', 'PipObjectiveStatus', 'SuccessionPlanCriticality', 
        'SuccessionCandidateReadiness', 'RetentionRisk'
    ]
    for enum_name in performance_enums:
        if f"class {enum_name}(str, enum.Enum)" in schema_code or f"class {enum_name}(enum.Enum)" in schema_code:
            issues.append({
                "severity": "MAJOR",
                "file": f"performance_{module}_schema.py",
                "line_hint": f"class {enum_name}",
                "issue": f"Enum '{enum_name}' re-declared in schema — must be imported from models",
                "fix": f"Remove the class and add: from app.models.performance import {enum_name}"
            })

    # ── Create schema fields ───────────────────────────────────────────────
    create_schemas = re.findall(r"class (\w+Create)\(.*?\):(.*?)(?=\nclass |\Z)", schema_code, re.DOTALL)
    for name, body in create_schemas:
        for forbidden in ["uuid:", "created_at:", "updated_at:"]:
            if forbidden in body:
                issues.append({
                    "severity": "MAJOR",
                    "file": f"performance_{module}_schema.py",
                    "line_hint": f"class {name}",
                    "issue": f"Create schema '{name}' contains '{forbidden}' which should not be in input schemas",
                    "fix": f"Remove '{forbidden}' field from {name}"
                })

    # ── Update schema Optional ─────────────────────────────────────────────
    update_schemas = re.findall(r"class (\w+Update)\(.*?\):(.*?)(?=\nclass |\Z)", schema_code, re.DOTALL)
    for name, body in update_schemas:
        non_optional = re.findall(r"\n    (\w+): (?!Optional)", body)
        if non_optional:
            issues.append({
                "severity": "MINOR",
                "file": f"performance_{module}_schema.py",
                "line_hint": f"class {name}",
                "issue": f"Update schema '{name}' has non-Optional fields: {non_optional}",
                "fix": f"Make all fields Optional[...] in {name}"
            })

    # ── db.commit() after writes ───────────────────────────────────────────
    write_decorators = re.findall(r"@router\.(post|put|patch|delete)\(", endpoint_code)
    commit_count = endpoint_code.count("db.commit()")
    if write_decorators and commit_count == 0:
        issues.append({
            "severity": "CRITICAL",
            "file": f"performance_{module}.py",
            "line_hint": "all write endpoints",
            "issue": "No db.commit() calls found in write endpoints",
            "fix": "Add db.commit() after every db.add() or update operation"
        })

    # ── RBAC checks ────────────────────────────────────────────────────────
    if "_require_permission" not in endpoint_code and "check_permission" not in endpoint_code:
        issues.append({
            "severity": "MAJOR",
            "file": f"performance_{module}.py",
            "line_hint": "all endpoints",
            "issue": "No RBAC permission checks found",
            "fix": "Add _require_permission(db, current_user, PERMISSION_CODE, 'action') at start of each function"
        })

    return issues


def build_reviewer_prompt(
    schema_code: str,
    endpoint_code: str,
    module: str,
    static_issues: list,
    agent_notes: str,
) -> str:
    return f"""You are a senior FastAPI code reviewer for a production HRM system. 
Review the generated code below and produce a structured JSON verdict.

═══════════════════════════════════════════════════
MODULE UNDER REVIEW: {module.upper()}
═══════════════════════════════════════════════════

SCHEMA FILE (app/schemas/performance_{module}.py):
```python
{schema_code[:15000]}
```

ENDPOINT FILE (app/api/v1/endpoints/performance_{module}.py):
```python
{endpoint_code[:30000]}
```

AGENT'S SELF-NOTES:
{agent_notes}

PRE-COMPUTED STATIC ISSUES (already found, include in your output):
{json.dumps(static_issues, indent=2)}

═══════════════════════════════════════════════════
REVIEW CHECKLIST — Score each item 0-10:
═══════════════════════════════════════════════════
1. pattern_consistency     — Follows existing project patterns exactly (auth, pagination, response envelopes)
2. multi_tenancy           — Every query filters organization_id (data isolation between orgs)  
3. uuid_path_params        — All URL path params use uuid.UUID, not int IDs
4. pagination_correct      — All list endpoints have page/limit with correct pagination dict
5. schema_config           — All response/data schemas have from_attributes = True
6. no_enum_redeclaration   — Enums imported from models, not re-declared in schemas
7. create_update_schema    — Create has no auto-fields; Update has all Optional fields
8. rbac_enforced           — Every protected endpoint has permission check
9. business_rules          — All module-specific business rules are correctly implemented
10. error_handling         — Consistent HTTPException/JSONResponse pattern, correct status codes
11. completeness           — Every endpoint from the provided API list is implemented. No missing functionality.
12. advanced_listing       — List endpoints support search, multiple filters, and multi-column sorting.

PASS THRESHOLD: overall average ≥ {PASS_THRESHOLD}/10

═══════════════════════════════════════════════════
OUTPUT FORMAT: Respond with ONLY valid JSON (no markdown):
═══════════════════════════════════════════════════
{{
  "verdict": "PASS" or "FAIL",
  "overall_score": <float 0-10>,
  "scores": {{
    "pattern_consistency": <0-10>,
    "multi_tenancy": <0-10>,
    "uuid_path_params": <0-10>,
    "pagination_correct": <0-10>,
    "schema_config": <0-10>,
    "no_enum_redeclaration": <0-10>,
    "create_update_schema": <0-10>,
    "rbac_enforced": <0-10>,
    "business_rules": <0-10>,
    "error_handling": <0-10>,
    "completeness": <0-10>,
    "advanced_listing": <0-10>
  }},
  "issues": [
    {{
      "severity": "CRITICAL|MAJOR|MINOR",
      "file": "filename.py",
      "line_hint": "function name or approximate location",
      "issue": "Specific problem description",
      "fix": "Exact fix instruction"
    }}
  ],
  "improvement_hints_for_agent": [
    "Future generations should always X...",
    "Common pattern the agent missed: Y..."
  ],
  "passed_checks": ["List of things done correctly"]
}}
"""


def call_gemini_api(prompt: str) -> str:
    try:
        import google.generativeai as genai
    except ImportError:
        print("Model library missing.")
        sys.exit(1)

    api_key = os.environ.get("GEMINI_API_KEY")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-3.1-flash-lite")
    
    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(
            temperature=0.05,
            max_output_tokens=4096,
        )
    )
    return response.text


def update_feedback_store(review: dict, module: str):
    store = json.loads(FEEDBACK_STORE_PATH.read_text()) if FEEDBACK_STORE_PATH.exists() else {
        "common_mistakes": [], "improvement_hints": [], "module_scores": {}, "total_cycles_used": 0
    }

    store["module_scores"][module] = review.get("overall_score", 0)
    store["total_cycles_used"] = store.get("total_cycles_used", 0) + 1

    existing_hints = set(store.get("improvement_hints", []))
    for hint in review.get("improvement_hints_for_agent", []):
        if hint not in existing_hints:
            store["improvement_hints"].append(hint)
            existing_hints.add(hint)

    for issue in review.get("issues", []):
        pattern = issue.get("issue", "")[:80]
        found = next((m for m in store["common_mistakes"] if m["pattern"] == pattern), None)
        if found:
            found["count"] += 1
            if module not in found.get("modules", []):
                found.setdefault("modules", []).append(module)
        else:
            store["common_mistakes"].append({
                "pattern": pattern,
                "count": 1,
                "modules": [module],
                "severity": issue.get("severity", "MINOR")
            })

    FEEDBACK_STORE_PATH.write_text(json.dumps(store, indent=2))


def run_reviewer(
    schema_code: str,
    endpoint_code: str,
    module: str,
    agent_notes: str = "",
    save_report: bool = True,
) -> dict:
    static_issues = static_checks(schema_code, endpoint_code, module)
    prompt = build_reviewer_prompt(schema_code, endpoint_code, module, static_issues, agent_notes)
    raw = call_gemini_api(prompt)

    review = {}
    try:
        clean = re.sub(r"```json\s*|\s*```", "", raw).strip()
        review = json.loads(clean)
    except json.JSONDecodeError:
        static_score = max(0.0, 10.0 - (len(static_issues) * 1.5))
        review = {
            "verdict": "FAIL" if static_issues else "PASS",
            "overall_score": static_score,
            "scores": {},
            "issues": static_issues,
            "improvement_hints_for_agent": ["Reviewer returned invalid JSON"],
            "passed_checks": []
        }

    existing_issues = {i.get("issue", "") for i in review.get("issues", [])}
    for si in static_issues:
        if si["issue"] not in existing_issues:
            review.setdefault("issues", []).append(si)

    critical_issues = [i for i in review.get("issues", []) if i.get("severity") == "CRITICAL"]
    if critical_issues:
        review["verdict"] = "FAIL"
        review["overall_score"] = min(review.get("overall_score", 10), 5.0)

    if review.get("verdict") == "FAIL":
        update_feedback_store(review, module)

    if save_report:
        report_path = AGENTS_DIR / f"rejection_report_performance_{module}.json"
        report_path.write_text(json.dumps(review, indent=2))

    return review
