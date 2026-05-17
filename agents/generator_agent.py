"""
generator_agent.py
Generates schemas and FastAPI endpoints for a payroll module.

Uses Google Gemini API (via google-generativeai) to produce production-ready code
that matches the project's existing patterns exactly.

Usage:
    python agents/generator_agent.py --module salary_components
    python agents/generator_agent.py --module salary_components --rejection-report agents/rejection_report_salary_components.json
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
FEEDBACK_STORE_PATH = AGENTS_DIR / "feedback_store.json"

# Model file content (read once)
PAYROLL_MODEL_PATH = BASE_DIR / "app/models/payroll.py"

# ─────────────────────────────────────────────
# Load business rules
# ─────────────────────────────────────────────
sys.path.insert(0, str(BASE_DIR))
from agents.business_rules import MODULE_RULES, PERMISSION_CODES, MODULE_PRIORITY, ROUTE_MAP


def load_style_guide() -> dict:
    if not STYLE_GUIDE_PATH.exists():
        print("⚠️  Style guide not found. Running context extractor first...")
        from agents.context_extractor import extract_style_guide
        guide = extract_style_guide()
        STYLE_GUIDE_PATH.write_text(json.dumps(guide, indent=2))
    return json.loads(STYLE_GUIDE_PATH.read_text())


def load_feedback_store() -> dict:
    if not FEEDBACK_STORE_PATH.exists():
        return {"common_mistakes": [], "improvement_hints": [], "module_scores": {}}
    return json.loads(FEEDBACK_STORE_PATH.read_text())


def read_payroll_models() -> str:
    return PAYROLL_MODEL_PATH.read_text()


def build_generator_prompt(
    module: str,
    style_guide: dict,
    feedback_store: dict,
    rejection_report: dict | None,
    api_list_excerpt: str,
) -> str:

    perms = PERMISSION_CODES.get(module, {"READ": "101", "CREATE": "102", "UPDATE": "103", "DELETE": "104"})
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

    prompt = f"""You are an expert FastAPI developer generating production-ready Python code for an HRM system.
Your output will be written directly to source files. DO NOT output markdown or explanation — ONLY raw Python code.

═══════════════════════════════════════════════════
TASK: Generate code for module: **{module.upper()}**
═══════════════════════════════════════════════════

You must produce TWO files:
1. **SCHEMA FILE**: `app/schemas/payroll_{module}.py`
2. **ENDPOINT FILE**: `app/api/v1/endpoints/payroll_{module}.py`

─────────────────────────────────────────────────────────
STYLE GUIDE (match EXACTLY — this is extracted from the existing codebase):
─────────────────────────────────────────────────────────
{json.dumps(style_guide, indent=2)}

─────────────────────────────────────────────────────────
PAYROLL MODELS (your models are in payroll.py):
─────────────────────────────────────────────────────────
{read_payroll_models()}

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
1. EVERY query MUST filter `organization_id == current_org.id` (multi-tenancy)
2. EVERY URL path param MUST use `uuid.UUID` type (never raw int IDs)
3. EVERY list endpoint MUST have pagination (page, limit, total_records, total_pages, page_size)
4. ALL schemas MUST have `class Config: from_attributes = True` 
5. NEVER re-declare Enums in schemas — import from `app.models.payroll`
6. Create schemas MUST NOT have: uuid, id, created_at, updated_at
7. Update schemas MUST have ALL fields as `Optional[...]`
8. EVERY protected endpoint MUST call `_require_permission()` or use `check_permission` dependency
9. EVERY write operation MUST have: `db.add(item); db.commit(); db.refresh(item)`
10. Background task endpoint MUST check `should_proceed_background: bool = Query(False)`
11. ALL API response messages MUST be descriptive and relative to the entity (e.g., "Salary template created successfully" instead of "Created", "Employee salary records retrieved successfully" instead of "Retrieved").
12. TOTAL COMPLETENESS: You MUST implement EVERY SINGLE ENDPOINT listed in the "API ENDPOINTS TO IMPLEMENT" section. Skipping any endpoint is a CRITICAL violation.
13. LOGICAL INTEGRITY: Do not provide "hollow" implementations. You must implement the full business logic described in the rules.
14. ADVANCED LISTING: EVERY list endpoint (GET /) MUST support:
    (a) Global `search` query parameter (searches across name, code, and key string fields).
    (b) Filtering on all relevant boolean and enum fields (is_active, status, type, etc.).
    (c) Multi-column sorting: `sort_by` must accept comma-separated strings (e.g., "created_at,name") and apply them in sequence.
15. OBJECT ENRICHMENT: Never return raw integer IDs for related entities. Always return a nested object (e.g., `employee`, `template`) containing `uuid`, `name`, and `code`.

═══════════════════════════════════════════════════════
OUTPUT FORMAT — respond with EXACTLY this structure:
═══════════════════════════════════════════════════════
<<<SCHEMA_FILE>>>
# Full content of app/schemas/payroll_{module}.py
<<<END_SCHEMA>>>

<<<ENDPOINT_FILE>>>  
# Full content of app/api/v1/endpoints/payroll_{module}.py
<<<END_ENDPOINT>>>

<<<AGENT_NOTES>>>
# What patterns you followed
# What edge cases you handled  
# What you are uncertain about (the reviewer will check these)
<<<END_NOTES>>>
"""
    return prompt


def call_gemini_api(prompt: str, model_name: str = "gemini-3.1-flash-lite") -> str:
    """Call Google Gemini API."""
    try:
        import google.generativeai as genai
    except ImportError:
        print("❌ google-generativeai not installed. Run: pip install google-generativeai")
        sys.exit(1)
    
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY environment variable not set.")
        sys.exit(1)
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    
    print(f"  🤖 Calling Gemini ({model_name})...")
    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(
            temperature=0.1,      # Low temp for deterministic, pattern-following code
            max_output_tokens=16384,
        )
    )
    return response.text


def parse_generated_output(raw: str) -> dict:
    """Parse the structured output from the generator."""
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
    print(f"\n🔧 Generator Agent — Module: {module}")
    print(f"   Attempt: {'RETRY (rejection report loaded)' if rejection_report else 'First attempt'}")

    style_guide = load_style_guide()
    feedback_store = load_feedback_store()

    prompt = build_generator_prompt(
        module=module,
        style_guide=style_guide,
        feedback_store=feedback_store,
        rejection_report=rejection_report,
        api_list_excerpt=api_list_excerpt,
    )

    if dry_run:
        print("  [DRY RUN] Prompt built. Skipping API call.")
        print(f"  Prompt length: {len(prompt)} chars")
        return {"schema_file": "# DRY RUN", "endpoint_file": "# DRY RUN", "agent_notes": ""}

    raw_output = call_gemini_api(prompt)
    
    # Save raw output for debugging
    raw_path = AGENTS_DIR / f"_raw_output_{module}.txt"
    raw_path.write_text(raw_output)
    print(f"  💾 Raw output saved to {raw_path.name}")

    parsed = parse_generated_output(raw_output)

    if not parsed["schema_file"] or not parsed["endpoint_file"]:
        print("  ⚠️  Failed to parse structured output. Check raw output file.")
        print("  Raw output (first 500 chars):", raw_output[:500])

    return parsed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Payroll API Generator Agent")
    parser.add_argument("--module", required=True, choices=MODULE_PRIORITY, help="Module to generate")
    parser.add_argument("--rejection-report", type=str, help="Path to rejection report JSON")
    parser.add_argument("--api-list", type=str, help="Path to API list markdown (or excerpt)")
    parser.add_argument("--dry-run", action="store_true", help="Build prompt only, no API call")
    args = parser.parse_args()

    rejection = None
    if args.rejection_report and Path(args.rejection_report).exists():
        rejection = json.loads(Path(args.rejection_report).read_text())

    api_excerpt = ""
    if args.api_list and Path(args.api_list).exists():
        api_excerpt = Path(args.api_list).read_text()

    result = run_generator(
        module=args.module,
        rejection_report=rejection,
        api_list_excerpt=api_excerpt,
        dry_run=args.dry_run,
    )

    if result["schema_file"] and result["schema_file"] != "# DRY RUN":
        schema_path = BASE_DIR / f"app/schemas/payroll_{args.module}.py"
        schema_path.write_text(result["schema_file"])
        print(f"  ✅ Schema written to {schema_path}")

    if result["endpoint_file"] and result["endpoint_file"] != "# DRY RUN":
        endpoint_path = BASE_DIR / f"app/api/v1/endpoints/payroll_{args.module}.py"
        endpoint_path.write_text(result["endpoint_file"])
        print(f"  ✅ Endpoint written to {endpoint_path}")
