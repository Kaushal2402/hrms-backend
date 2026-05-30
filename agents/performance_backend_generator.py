"""
performance_backend_generator.py
Generates schemas and FastAPI endpoints for a performance management module.
Uses Google Gemini API to produce production-ready code.
"""

import json
import os
import sys
import argparse
from pathlib import Path
import re

BASE_DIR = Path(__file__).parent.parent
AGENTS_DIR = Path(__file__).parent
STYLE_GUIDE_PATH = AGENTS_DIR / "codebase_style_guide.json"
FEEDBACK_STORE_PATH = AGENTS_DIR / "performance_feedback_store.json"
PERFORMANCE_MODEL_PATH = BASE_DIR / "app/models/performance.py"

sys.path.insert(0, str(AGENTS_DIR))
from performance_backend_business_rules import MODULE_RULES, PERMISSION_CODES, ROUTE_MAP


def load_style_guide() -> dict:
    if not STYLE_GUIDE_PATH.exists():
        from agents.context_extractor import extract_style_guide
        guide = extract_style_guide()
        STYLE_GUIDE_PATH.write_text(json.dumps(guide, indent=2))
    return json.loads(STYLE_GUIDE_PATH.read_text())


def load_feedback_store() -> dict:
    if not FEEDBACK_STORE_PATH.exists():
        return {"common_mistakes": [], "improvement_hints": [], "module_scores": {}}
    return json.loads(FEEDBACK_STORE_PATH.read_text())


MODULE_KEYWORDS_MAP = {
    "goal_frameworks": ["GoalFramework", "OrganizationGoal", "DepartmentGoal", "EmployeeGoal", "GoalProgress", "GoalAlignment"],
    "appraisal_cycles": ["AppraisalCycle", "AppraisalTemplate", "AppraisalSection", "AppraisalQuestion", "AppraisalQuestionChoice"],
    "appraisals": ["AppraisalRecord", "SelfAppraisal", "ManagerAppraisal", "AppraisalAnswer", "AppraisalCalibration", "AppraisalBellCurve"],
    "feedback_360": ["Feedback360", "FeedbackRequest", "FeedbackProviderType", "Feedback360Request", "Feedback360CompetencyRating", "Feedback360OpenEnded", "Feedback360AnonymousReport"],
    "competencies": ["CompetencyFramework", "CompetencyGroup", "CompetencyElement", "CompetencyRatingScale", "CompetencyBehavioralIndicator", "EmployeeCompetencyAssessment"],
    "one_on_ones": ["OneOnOne"],
    "pip": ["PIP"],
    "talent_reviews": ["TalentReview", "NineBox"],
    "performance_integrations": ["PerformanceIntegration", "PerformanceExternal", "PerformanceApi"]
}

def read_performance_models(module: str) -> str:
    if not PERFORMANCE_MODEL_PATH.exists():
        return ""
    content = PERFORMANCE_MODEL_PATH.read_text()
    blocks = re.split(r'\n(?=class )', content)
    header = blocks[0]
    
    keywords = MODULE_KEYWORDS_MAP.get(module, [])
    selected = []
    
    for b in blocks[1:]:
        name_match = re.match(r'^class (\w+)', b)
        if not name_match:
            continue
        name = name_match.group(1)
        
        is_enum = 'enum.Enum' in b
        is_target = any(k in name for k in keywords)
        
        if is_enum or is_target:
            # Clean up model class
            lines = b.splitlines()
            cleaned_lines = []
            in_docstring = False
            for line in lines:
                stripped = line.strip()
                if stripped.startswith('\"\"\"') or stripped.endswith('\"\"\"'):
                    if stripped.count('\"\"\"') == 1:
                        in_docstring = not in_docstring
                    continue
                if in_docstring:
                    continue
                
                # Skip relationships and table args
                if 'relationship(' in line:
                    continue
                if '__table_args__' in line:
                    continue
                if stripped.startswith('Index(') or stripped.startswith('UniqueConstraint('):
                    continue
                
                cleaned_lines.append(line)
            selected.append('\n'.join(cleaned_lines))
            
    return header + '\n' + '\n\n'.join(selected)


def build_generator_prompt(
    module: str,
    style_guide: dict,
    feedback_store: dict,
    rejection_report: dict | None,
    api_list_excerpt: str,
    target_mode: str = "BOTH",
    generated_schemas_code: str = "",
) -> str:

    perms = PERMISSION_CODES.get(module, {"READ": "201", "CREATE": "202", "UPDATE": "203", "DELETE": "204"})
    rules = MODULE_RULES.get(module, "No special rules. Follow standard CRUD patterns.")
    
    common_mistakes_text = ""
    if feedback_store.get("common_mistakes"):
        mistakes = "\n".join(f"  - {m['pattern']} (seen {m['count']}x)" 
                             for m in feedback_store["common_mistakes"])
        common_mistakes_text = f"""
KNOWN RECURRING MISTAKES (pre-emptively avoid these — they come from previous generation cycles):
{mistakes}
"""

    rejection_text = ""
    if rejection_report:
        issues = rejection_report.get("issues", [])
        hints  = rejection_report.get("improvement_hints_for_agent", [])
        rejection_text = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  PREVIOUS ATTEMPT WAS REJECTED — FIX ALL ISSUES BELOW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Score: {rejection_report.get('overall_score', 'N/A')}/10

ISSUES TO FIX:
{chr(10).join(f"[{i['severity']}] {i['file']} | {i.get('line_hint','')} | {i['issue']} → FIX: {i['fix']}" for i in issues)}

IMPROVEMENT HINTS FROM REVIEWER:
{chr(10).join(f"  - {h}" for h in hints)}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

    target_mode_desc = ""
    output_format_desc = ""
    if target_mode == "SCHEMAS":
        target_mode_desc = f"TASK: Generate ONLY the Pydantic schemas file (app/schemas/performance_{module}.py) for module: **{module.upper()}**."
        output_format_desc = f"""OUTPUT FORMAT — respond with EXACTLY this structure:
<<<SCHEMA_FILE>>>
# Full content of app/schemas/performance_{module}.py
<<<END_SCHEMA>>>

<<<AGENT_NOTES>>>
# Notes about schema design
<<<END_NOTES>>>"""
    elif target_mode == "ENDPOINTS":
        target_mode_desc = f"""TASK: Generate ONLY the FastAPI endpoints router file (app/api/v1/endpoints/performance_{module}.py) for module: **{module.upper()}**.
You MUST base your endpoint implementation on the following schemas that have already been generated for this module:
{generated_schemas_code}"""
        output_format_desc = f"""OUTPUT FORMAT — respond with EXACTLY this structure:
<<<ENDPOINT_FILE>>>
# Full content of app/api/v1/endpoints/performance_{module}.py
<<<END_ENDPOINT>>>

<<<AGENT_NOTES>>>
# Notes about endpoint design
<<<END_NOTES>>>"""
    else:
        target_mode_desc = f"TASK: Generate BOTH the schemas file and endpoints router file for module: **{module.upper()}**."
        output_format_desc = f"""OUTPUT FORMAT — respond with EXACTLY this structure:
<<<SCHEMA_FILE>>>
# Full content of app/schemas/performance_{module}.py
<<<END_SCHEMA>>>

<<<ENDPOINT_FILE>>>  
# Full content of app/api/v1/endpoints/performance_{module}.py
<<<END_ENDPOINT>>>

<<<AGENT_NOTES>>>
# Notes about both files
<<<END_NOTES>>>"""

    prompt = f"""You are an expert FastAPI developer generating production-ready Python code for an HRM system.
Your output will be written directly to source files. DO NOT output markdown or explanation — ONLY raw Python code.

═══════════════════════════════════════════════════
{target_mode_desc}
═══════════════════════════════════════════════════

─────────────────────────────────────────────────────────
STYLE GUIDE (match EXACTLY — this is extracted from the existing codebase):
─────────────────────────────────────────────────────────
{json.dumps(style_guide, indent=2)}

─────────────────────────────────────────────────────────
PERFORMANCE MODELS (your models are in performance.py):
─────────────────────────────────────────────────────────
{read_performance_models(module)}

─────────────────────────────────────────────────────────
API ENDPOINTS TO IMPLEMENT for {module}:
─────────────────────────────────────────────────────────
{api_list_excerpt}

─────────────────────────────────────────────────────────
PERMISSION CODES for this module:
─────────────────────────────────────────────────────────
{json.dumps(perms, indent=2)}

─────────────────────────────────────────────────────────
BUSINESS RULES (implement ALL of these precisely):
─────────────────────────────────────────────────────────
{rules}

{common_mistakes_text}
{rejection_text}

═══════════════════════════════════════════════════════
MANDATORY RULES (violation = automatic FAIL):
═══════════════════════════════════════════════════════
1. EVERY query MUST enforce multi-tenancy. For models containing `organization_id` (AppraisalRecord, AppraisalCycle, AppraisalCalibration, etc.), filter directly: `Model.organization_id == _get_org_id(current_user)`. For sub-resource models without an `organization_id` column (SelfAppraisal, ManagerAppraisal, AppraisalAnswer, etc.), you MUST join/filter on the parent `AppraisalRecord` table:
   e.g. `db.query(SelfAppraisal).join(AppraisalRecord).filter(AppraisalRecord.organization_id == _get_org_id(current_user), ...)` or validate the parent record first:
   `record = db.query(AppraisalRecord).filter(AppraisalRecord.uuid == record_uuid, AppraisalRecord.organization_id == _get_org_id(current_user)).first()`
   and then load the sub-resource using `record.id`. Never query a sub-resource directly without verifying the parent's organization!
2. EVERY URL path param MUST use `uuid.UUID` type (never raw int IDs).
3. EVERY list endpoint MUST have pagination (page, limit, total_records, total_pages, page_size) returned in the response envelope.
4. ALL schemas MUST have `class Config: from_attributes = True`.
5. NEVER re-declare Enums in schemas — import them from `app.models.performance`.
6. Create schemas MUST NOT have: uuid, id, created_at, updated_at.
7. Update schemas MUST have ALL fields as `Optional[...]`.
8. EVERY single endpoint MUST enforce RBAC permissions by calling `_require_permission(db, current_user, PerformancePermissions.READ or PerformancePermissions.UPDATE, "action_name")` at the start of the handler function.
9. EVERY write/update/delete operation MUST commit changes: `db.add(item); db.commit(); db.refresh(item)` (or `db.delete(item); db.commit()`).
10. Background task endpoints MUST check `should_proceed_background: bool = Query(False)`.
11. ALL API response messages MUST be descriptive and relative to the entity.
12. TOTAL COMPLETENESS: You MUST implement EVERY SINGLE ENDPOINT listed in the "API ENDPOINTS TO IMPLEMENT" section.
13. LOGICAL INTEGRITY: Do not provide hollow or mock implementations. You must implement the full business logic described.
14. ADVANCED LISTING: EVERY list endpoint (GET /) MUST support:
    (a) Global `search` query parameter (search employee first/last name, cycle name, framework name, etc.).
    (b) Filtering on all relevant enum/boolean fields.
    (c) Multi-column sorting: `sort_by` must accept comma-separated strings and apply them in sequence.
15. OBJECT ENRICHMENT: Never return raw integer IDs for related entities. Always return nested objects (e.g. `employee`, `manager`, `appraisal_cycle`, `template`) containing `uuid`, names, and codes if applicable.

═══════════════════════════════════════════════════════
{output_format_desc}
"""
    return prompt


def call_gemini_api(prompt: str, model_name: str = "gemini-3.5-flash") -> str:
    import time
    try:
        import google.generativeai as genai
    except ImportError:
        print("Model library missing.")
        sys.exit(1)
    
    api_key = os.environ.get("GEMINI_API_KEY")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    
    for attempt in range(15):
        try:
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1,
                    max_output_tokens=16384,
                )
            )
            return response.text
        except Exception as e:
            if "429" in str(e) or "ResourceExhausted" in type(e).__name__ or "quota" in str(e).lower():
                wait_time = 30 + 15 * attempt
                print(f"  ⚠️ [API] 429 Quota limit hit. Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
            else:
                raise e
    raise RuntimeError("API calls failed after 15 retries.")


def parse_generated_output(raw: str) -> dict:
    result = {"schema_file": "", "endpoint_file": "", "agent_notes": ""}
    schema_match = re.search(r"<<<SCHEMA_FILE>>>(.*?)<<<END_SCHEMA>>>", raw, re.DOTALL)
    endpoint_match = re.search(r"<<<ENDPOINT_FILE>>>(.*?)<<<END_ENDPOINT>>>", raw, re.DOTALL)
    notes_match = re.search(r"<<<AGENT_NOTES>>>(.*?)<<<END_NOTES>>>", raw, re.DOTALL)

    if schema_match:
        result["schema_file"] = schema_match.group(1).strip()
    if endpoint_match:
        result["endpoint_file"] = endpoint_match.group(1).strip()
    if notes_match:
        result["agent_notes"] = notes_match.group(1).strip()

    return result


def run_generator(
    module: str,
    rejection_report: dict | None = None,
    api_list_excerpt: str = "",
    dry_run: bool = False,
) -> dict:
    style_guide = load_style_guide()
    feedback_store = load_feedback_store()

    if dry_run:
        return {"schema_file": "# DRY RUN", "endpoint_file": "# DRY RUN", "agent_notes": ""}

    # 1. Generate Schemas
    print(f"  [Backend] Generating Schemas for {module}...")
    schema_prompt = build_generator_prompt(
        module=module,
        style_guide=style_guide,
        feedback_store=feedback_store,
        rejection_report=rejection_report,
        api_list_excerpt=api_list_excerpt,
        target_mode="SCHEMAS",
    )
    raw_schemas = call_gemini_api(schema_prompt)
    parsed_schemas = parse_generated_output(raw_schemas)
    schema_code = parsed_schemas.get("schema_file", "").strip()

    # 2. Generate Endpoints
    print(f"  [Backend] Generating Endpoints for {module}...")
    endpoint_prompt = build_generator_prompt(
        module=module,
        style_guide=style_guide,
        feedback_store=feedback_store,
        rejection_report=rejection_report,
        api_list_excerpt=api_list_excerpt,
        target_mode="ENDPOINTS",
        generated_schemas_code=schema_code,
    )
    raw_endpoints = call_gemini_api(endpoint_prompt)
    parsed_endpoints = parse_generated_output(raw_endpoints)
    endpoint_code = parsed_endpoints.get("endpoint_file", "").strip()

    # Save raw outputs concatenated for debug logs
    raw_path = AGENTS_DIR / f"_raw_output_performance_{module}.txt"
    raw_path.write_text(f"<<<SCHEMAS_RAW>>>\n{raw_schemas}\n\n<<<ENDPOINTS_RAW>>>\n{raw_endpoints}")

    return {
        "schema_file": schema_code,
        "endpoint_file": endpoint_code,
        "agent_notes": parsed_schemas.get("agent_notes", "") + "\n" + parsed_endpoints.get("agent_notes", ""),
    }
