"""
orchestrator.py — Master controller for the payroll API generation pipeline.

Runs the Generator → Reviewer loop per module.
If a module FAILS, injects the rejection report into the next Generator call.
After max_cycles, escalates to the user.

Usage:
    # Run all modules:
    python agents/orchestrator.py

    # Run a single module:
    python agents/orchestrator.py --module salary_components

    # Dry run (build prompts, no API calls):
    python agents/orchestrator.py --dry-run

    # Skip already-generated modules:
    python agents/orchestrator.py --skip-existing
"""

import json
import sys
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent.parent
AGENTS_DIR = Path(__file__).parent
API_LIST_PATH = BASE_DIR / "payroll_api_list.md"

sys.path.insert(0, str(BASE_DIR))
from agents.business_rules import MODULE_PRIORITY, ROUTE_MAP
from agents.generator_agent import run_generator
from agents.reviewer_agent import run_reviewer

MAX_CYCLES = 3

# ─────────────────────────────────────────────────────
# Utility: extract API list section for a module
# ─────────────────────────────────────────────────────

MODULE_API_SECTIONS = {
    "salary_components":  "## 1. SALARY COMPONENTS",
    "salary_templates":   "## 2. SALARY TEMPLATES",
    "employee_salaries":  "## 3. EMPLOYEE SALARY",
    "payroll_periods":    "## 4. PAYROLL PERIOD",
    "payslips":           "## 5. PAYSLIP",
    "loans":              "## 6. LOAN",
    "reimbursements":     "## 7. REIMBURSEMENT",
    "final_settlements":  "## 8. FINAL SETTLEMENT",
    "arrears_one_time":   "## 9. ARREAR",
    "tax_declarations":   "## 10. TAX DECLARATION",
    "bank_files":         "## 11. BANK FILE",
    "reconciliations":    "## 12. PAYROLL RECONCILIATION",
    "journal_entries":    "## 13. PAYROLL JOURNAL",
    "statutory_forms":    "## 14. STATUTORY FORMS",
    "reports":            "## 15. PAYROLL REPORT",
    "bulk_operations":    "## 16. BULK OPERATION",
    "bank_accounts":      "## 17. BANK ACCOUNT",
    "audit_logs":         "## 18. PAYROLL AUDIT",
}


def extract_api_section(module: str) -> str:
    """Extract the relevant section from payroll_api_list.md."""
    if not API_LIST_PATH.exists():
        return f"No API list found. Generate standard CRUD for {module}."

    content = API_LIST_PATH.read_text()
    sections = content.split("\n## ")
    
    header_keyword = MODULE_API_SECTIONS.get(module, "").replace("## ", "").lower()
    
    for i, section in enumerate(sections):
        if header_keyword.lower() in section.lower()[:50]:
            # Return this section up to next ##
            return "## " + section.strip()
    
    # Fallback: return full content (truncated)
    return content[:3000]


# ─────────────────────────────────────────────────────
# Syntax check generated file
# ─────────────────────────────────────────────────────

def syntax_check(file_path: Path) -> tuple[bool, str]:
    """Quick Python syntax check via py_compile."""
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(file_path)],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        return True, ""
    return False, result.stderr


# ─────────────────────────────────────────────────────
# Write generated files to disk
# ─────────────────────────────────────────────────────

def write_files(module: str, generated: dict) -> tuple[Path, Path]:
    schema_path = BASE_DIR / f"app/schemas/payroll_{module}.py"
    endpoint_path = BASE_DIR / f"app/api/v1/endpoints/payroll_{module}.py"

    schema_path.write_text(generated["schema_file"])
    endpoint_path.write_text(generated["endpoint_file"])

    return schema_path, endpoint_path


# ─────────────────────────────────────────────────────
# Register routers in api.py
# ─────────────────────────────────────────────────────

def register_routers(completed_modules: list[str]):
    """Append router registrations to api.py."""
    api_path = BASE_DIR / "app/api/v1/api.py"
    content = api_path.read_text()

    # Build import line
    module_imports = ", ".join(f"payroll_{m}" for m in completed_modules)
    import_line = f"from app.api.v1.endpoints import (\n    {module_imports}\n)"

    # Build router lines
    router_lines = []
    for m in completed_modules:
        prefix = ROUTE_MAP.get(m, f"/payroll/{m.replace('_', '-')}")
        router_lines.append(
            f'api_router.include_router(payroll_{m}.router, prefix="{prefix}", tags=["payroll"])'
        )

    payroll_block = f"""
# ── Payroll Module (auto-generated {datetime.now().strftime('%Y-%m-%d')}) ──────────
{import_line}
{''.join(chr(10) + r for r in router_lines)}
"""

    # Avoid duplicate registration
    if "# ── Payroll Module" in content:
        print("  ⚠️  Payroll routers already registered in api.py — skipping.")
        return

    api_path.write_text(content + "\n" + payroll_block)
    print(f"  ✅ Registered {len(completed_modules)} payroll routers in api.py")


# ─────────────────────────────────────────────────────
# Per-module loop
# ─────────────────────────────────────────────────────

def process_module(
    module: str,
    dry_run: bool = False,
    force: bool = False,
) -> dict:
    schema_path = BASE_DIR / f"app/schemas/payroll_{module}.py"
    endpoint_path = BASE_DIR / f"app/api/v1/endpoints/payroll_{module}.py"

    if not force and schema_path.exists() and endpoint_path.exists():
        print(f"\n⏭️  Skipping {module} — files already exist (use --force to regenerate)")
        return {"module": module, "status": "skipped", "cycles": 0}

    api_excerpt = extract_api_section(module)
    rejection_report = None
    result_status = "failed"

    for cycle in range(1, MAX_CYCLES + 1):
        print(f"\n{'='*60}")
        print(f"  Module: {module.upper()} | Cycle: {cycle}/{MAX_CYCLES}")
        print(f"{'='*60}")

        # ── Generate ──────────────────────────────────────────────
        generated = run_generator(
            module=module,
            rejection_report=rejection_report,
            api_list_excerpt=api_excerpt,
            dry_run=dry_run,
        )

        if dry_run:
            return {"module": module, "status": "dry_run", "cycles": cycle}

        # ── Write files ──────────────────────────────────────────
        schema_path, endpoint_path = write_files(module, generated)

        # ── Syntax check ─────────────────────────────────────────
        schema_ok, schema_err = syntax_check(schema_path)
        endpoint_ok, endpoint_err = syntax_check(endpoint_path)

        if not schema_ok or not endpoint_ok:
            print(f"  ❌ Syntax error in generated files:")
            if not schema_ok:
                print(f"     Schema: {schema_err}")
            if not endpoint_ok:
                print(f"     Endpoint: {endpoint_err}")
            rejection_report = {
                "verdict": "FAIL",
                "overall_score": 0,
                "issues": [
                    {"severity": "CRITICAL", "file": "schema", "line_hint": "top",
                     "issue": f"Python syntax error: {schema_err}", "fix": "Fix syntax error"},
                    {"severity": "CRITICAL", "file": "endpoint", "line_hint": "top",
                     "issue": f"Python syntax error: {endpoint_err}", "fix": "Fix syntax error"},
                ],
                "improvement_hints_for_agent": ["Always produce syntactically valid Python"],
                "passed_checks": []
            }
            continue

        # ── Review ──────────────────────────────────────────────
        review = run_reviewer(
            schema_code=generated["schema_file"],
            endpoint_code=generated["endpoint_file"],
            module=module,
            agent_notes=generated.get("agent_notes", ""),
            save_report=(cycle < MAX_CYCLES),
        )

        if review["verdict"] == "PASS":
            result_status = "passed"
            print(f"\n  ✅ PASSED — Score: {review['overall_score']}/10 (cycle {cycle})")
            # Save final score in feedback store
            fb = json.loads((AGENTS_DIR / "feedback_store.json").read_text()) if (AGENTS_DIR / "feedback_store.json").exists() else {}
            fb.setdefault("module_scores", {})[module] = review["overall_score"]
            fb.setdefault("avg_cycles", {})[module] = cycle
            (AGENTS_DIR / "feedback_store.json").write_text(json.dumps(fb, indent=2))
            return {"module": module, "status": "passed", "cycles": cycle, "score": review["overall_score"]}
        else:
            print(f"\n  ❌ FAILED — Score: {review['overall_score']}/10 (cycle {cycle})")
            print(f"     Issues: {len(review.get('issues', []))} "
                  f"(CRITICAL: {sum(1 for i in review.get('issues',[]) if i.get('severity')=='CRITICAL')})")
            rejection_report = review

    # Escalate to human
    print(f"\n  ⚠️  ESCALATING {module} — exceeded {MAX_CYCLES} cycles")
    print(f"  👉 Review: {AGENTS_DIR}/rejection_report_{module}.json")
    print(f"  👉 Files:  {schema_path}")
    print(f"             {endpoint_path}")
    return {"module": module, "status": "escalated", "cycles": MAX_CYCLES}


# ─────────────────────────────────────────────────────
# Main orchestrator
# ─────────────────────────────────────────────────────

def run_orchestrator(
    modules: list[str] | None = None,
    dry_run: bool = False,
    force: bool = False,
):
    target_modules = modules or MODULE_PRIORITY
    
    print("\n" + "═" * 60)
    print("  🚀 PAYROLL API AGENT ORCHESTRATOR")
    print(f"  Modules: {len(target_modules)} | Max cycles: {MAX_CYCLES} | Dry run: {dry_run}")
    print("═" * 60)

    # Run context extractor first
    if not (AGENTS_DIR / "codebase_style_guide.json").exists():
        print("\n📋 Extracting codebase style guide...")
        from agents.context_extractor import extract_style_guide
        guide = extract_style_guide()
        (AGENTS_DIR / "codebase_style_guide.json").write_text(json.dumps(guide, indent=2))
        print(f"  ✅ Style guide ready ({len(guide)} sections)")

    results = []
    completed = []

    for module in target_modules:
        result = process_module(module, dry_run=dry_run, force=force)
        results.append(result)
        if result["status"] in ("passed", "skipped"):
            completed.append(module)

    # Register all completed routers at once
    if completed and not dry_run:
        print(f"\n📝 Registering {len(completed)} routers in api.py...")
        register_routers(completed)

    # Final summary
    print("\n" + "═" * 60)
    print("  📊 FINAL SUMMARY")
    print("═" * 60)
    for r in results:
        status_icon = {"passed": "✅", "skipped": "⏭️", "failed": "❌", "escalated": "⚠️", "dry_run": "🔍"}.get(r["status"], "?")
        score = f" | Score: {r.get('score', 'N/A')}/10" if "score" in r else ""
        cycles = f" | Cycles: {r.get('cycles', 0)}" if r.get("cycles", 0) > 0 else ""
        print(f"  {status_icon} {r['module']:<30} {r['status']}{score}{cycles}")

    passed = sum(1 for r in results if r["status"] == "passed")
    print(f"\n  Total: {len(results)} | Passed: {passed} | Escalated: {sum(1 for r in results if r['status']=='escalated')}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Payroll API Orchestrator")
    parser.add_argument("--module", type=str, help="Run only this module")
    parser.add_argument("--dry-run", action="store_true", help="Build prompts only, no API calls")
    parser.add_argument("--force", action="store_true", help="Regenerate even if files exist")
    args = parser.parse_args()

    modules = [args.module] if args.module else None
    run_orchestrator(modules=modules, dry_run=args.dry_run, force=args.force)
