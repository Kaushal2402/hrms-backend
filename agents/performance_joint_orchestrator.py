"""
performance_joint_orchestrator.py
Coordinates backend API and frontend component generation and review concurrently.
"""

import json
import os
import sys
import time
import threading
from queue import Queue
from pathlib import Path
import re

BASE_DIR = Path(__file__).parent.parent
BACKEND_AGENT_DIR = BASE_DIR / "agents"
ROOT_DIR = BASE_DIR.parent
FRONTEND_DIR = ROOT_DIR / "frontend"
FRONTEND_AGENT_DIR = FRONTEND_DIR / "agents"

sys.path.insert(0, str(BACKEND_AGENT_DIR))
from performance_backend_business_rules import MODULE_PRIORITY, ROUTE_MAP, PERMISSION_CODES, MODULE_RULES

# Queues for pipelined execution
backend_done_queue = Queue()

# Target limits
MAX_RETRY_CYCLES = 3


def extract_api_excerpt(module: str) -> str:
    md_path = BASE_DIR / "performance_management_apis.md"
    if not md_path.exists():
        return f"API definitions for {module}."
    
    content = md_path.read_text()
    
    # Map sub-modules to section numbers
    mapping = {
        "goal_frameworks": [1, 2, 3, 4, 5, 6],
        "appraisal_cycles": [7, 8, 9, 10, 11],
        "appraisals": [12, 13, 14, 15, 16, 17],
        "feedback_360": [18, 19, 20, 21],
        "competencies": [22, 23, 24, 25],
        "one_on_ones": [26, 27, 28, 29],
        "pip": [30, 31, 32],
        "talent_reviews": [33, 34, 35, 36],
        "performance_integrations": [37, 38, 39, 40]
    }
    
    sections = mapping.get(module, [])
    excerpt_lines = []
    
    lines = content.splitlines()
    for sec_num in sections:
        capture = False
        for line in lines:
            if line.startswith(f"## {sec_num}."):
                capture = True
                excerpt_lines.append(line)
                continue
            elif capture and line.startswith("## ") and not line.startswith(f"## {sec_num}."):
                # Check if it's the next section
                next_sec_match = re.match(r"^## (\d+)\.", line)
                if next_sec_match:
                    next_num = int(next_sec_match.group(1))
                    if next_num != sec_num:
                        capture = False
            
            if capture:
                excerpt_lines.append(line)
                
    return "\n".join(excerpt_lines)


# ─────────────────────────────────────────────────────────────
# Backend Registry Helper
# ─────────────────────────────────────────────────────────────
def register_backend_router(module: str):
    api_py_path = BASE_DIR / "app/api/v1/api.py"
    if not api_py_path.exists():
        return
    
    content = api_py_path.read_text()
    import_stmt = f"performance_{module}"
    router_prefix = ROUTE_MAP.get(module, f"/performance/{module}").replace("/performance/", "")
    
    if import_stmt in content:
        return
        
    print(f"  [Backend] Registering router for performance_{module}...")
    
    # Insert Import
    import_anchor = "# ── Payroll Module"
    performance_imports = f"from app.api.v1.endpoints import performance_{module}\n"
    if import_anchor in content:
        content = content.replace(import_anchor, performance_imports + import_anchor)
        
    # Insert Include Router
    include_anchor = "api_router.include_router(payroll_salary_components"
    router_line = f"api_router.include_router(performance_{module}.router, prefix=\"/performance/{router_prefix}\", tags=[\"performance\"])\n"
    if include_anchor in content:
        content = content.replace(include_anchor, router_line + include_anchor)
        
    api_py_path.write_text(content)
    print(f"  [Backend] Router performance_{module} registered successfully.")


# ─────────────────────────────────────────────────────────────
# Frontend Registry Helper
# ─────────────────────────────────────────────────────────────
def register_frontend_ui(module: str, config: dict):
    # Register in types.ts
    types_path = FRONTEND_DIR / "src/features/performance/types.ts"
    types_path.parent.mkdir(parents=True, exist_ok=True)
    if not types_path.exists():
        types_path.write_text("// Performance Types\n")

    # Register in App.tsx
    app_path = FRONTEND_DIR / "src/App.tsx"
    if app_path.exists():
        content = app_path.read_text()
        prefix = config["prefix"]
        route_path = config["route"]
        if f"{prefix}List" not in content:
            # Import
            import_line = f"import {{ {prefix}List }} from './features/performance/{prefix}List';"
            content = content.replace(
                "import { SalaryTemplateList } from './features/payroll/SalaryTemplateList';",
                f"import {{ SalaryTemplateList }} from './features/payroll/SalaryTemplateList';\n{import_line}"
            )
            # Route
            route_line = f'              <Route path="{route_path}" element={{<{prefix}List />}} />'
            content = content.replace(
                f'path="/payroll/salary-templates" element={{<SalaryTemplateList />}} />',
                f'path="/payroll/salary-templates" element={{<SalaryTemplateList />}} />\n{route_line}'
            )
            app_path.write_text(content)
            print(f"  [Frontend] Route registered in App.tsx.")

    # Register in Sidebar.tsx
    sidebar_path = FRONTEND_DIR / "src/components/layout/Sidebar.tsx"
    if sidebar_path.exists():
        content = sidebar_path.read_text()
        display_name = config["display_name"]
        route_path = config["route"]
        
        # Check if Performance Management group exists in sidebar
        if "Performance Management" not in content:
            # Insert Performance section before Security
            perf_group = f"""    {{
      name: 'Performance Management',
      icon: BarChart2,
      children: [
        {{ name: '{display_name}', path: '{route_path}' }},
      ]
    }},"""
            content = content.replace(
                "    {\n      name: 'Payroll Management',",
                perf_group + "\n    {\n      name: 'Payroll Management',"
            )
            # Import BarChart2 icon if needed
            if "BarChart2" not in content:
                content = content.replace(
                    "LayoutDashboard,",
                    "LayoutDashboard,\n  BarChart2,"
                )
            # Add openMenu toggle state
            content = content.replace(
                "'Payroll Management': location.pathname.startsWith('/payroll')",
                "'Payroll Management': location.pathname.startsWith('/payroll'),\n    'Performance Management': location.pathname.startsWith('/performance')"
            )
        else:
            # Performance section exists, append to its children list
            child_line = f"        {{ name: '{display_name}', path: '{route_path}' }},"
            if child_line not in content:
                content = content.replace(
                    "name: 'Performance Management',\n      icon: BarChart2,\n      children: [",
                    f"name: 'Performance Management',\n      icon: BarChart2,\n      children: [\n{child_line}"
                )
        sidebar_path.write_text(content)
        print(f"  [Frontend] Registered in Sidebar.tsx.")


# ─────────────────────────────────────────────────────────────
# Thread Workers
# ─────────────────────────────────────────────────────────────

def backend_worker():
    sys.path.insert(0, str(BACKEND_AGENT_DIR))
    import performance_backend_generator as bg
    import performance_backend_reviewer as br

    print("[Backend Worker] Thread started.")
    
    for module in MODULE_PRIORITY:
        print(f"\n=========================================\n[Backend] Starting Module: {module.upper()}\n=========================================")
        
        schema_path = BASE_DIR / f"app/schemas/performance_{module}.py"
        endpoint_path = BASE_DIR / f"app/api/v1/endpoints/performance_{module}.py"
        if schema_path.exists() and endpoint_path.exists():
            print(f"  [Backend] Module {module} already exists. Skipping generation.")
            register_backend_router(module)
            backend_done_queue.put((module, schema_path.read_text(), endpoint_path.read_text()))
            continue

        excerpt = extract_api_excerpt(module)
        
        rejection_report = None
        for cycle in range(1, MAX_RETRY_CYCLES + 1):
            print(f"  ⚡ Backend Cycle {cycle}/{MAX_RETRY_CYCLES}")
            
            parsed = bg.run_generator(
                module=module,
                rejection_report=rejection_report,
                api_list_excerpt=excerpt
            )
            
            review = br.run_reviewer(
                schema_code=parsed["schema_file"],
                endpoint_code=parsed["endpoint_file"],
                module=module,
                agent_notes=parsed["agent_notes"]
            )
            
            print(f"  📊 Review Score: {review.get('overall_score')}/10 | Verdict: {review.get('verdict')}")
            
            if review.get("verdict") == "PASS":
                # Write files
                schema_path.write_text(parsed["schema_file"])
                endpoint_path.write_text(parsed["endpoint_file"])
                
                print(f"  💾 Saved backend files for performance_{module}.")
                
                # Register in api.py
                register_backend_router(module)
                
                # Queue to frontend thread
                backend_done_queue.put((module, parsed["schema_file"], parsed["endpoint_file"]))
                break
            else:
                rejection_report = review
                if cycle == MAX_RETRY_CYCLES:
                    print(f"  ❌ Backend generation failed for {module} after {MAX_RETRY_CYCLES} attempts.")
                    backend_done_queue.put(None)  # Terminate queue
                    return
                time.sleep(2)
                
    # Signal termination
    backend_done_queue.put(None)
    print("[Backend Worker] Completed all modules.")


def frontend_worker():
    sys.path.insert(0, str(FRONTEND_AGENT_DIR))
    import performance_frontend_generator as fg
    import performance_frontend_reviewer as fr

    print("[Frontend Worker] Thread started.")
    
    while True:
        item = backend_done_queue.get()
        if item is None:
            break
            
        module, schema_code, endpoint_code = item
        print(f"\n=========================================\n[Frontend] Processing Module: {module.upper()}\n=========================================")
        
        config = fg.MODULE_CONFIG.get(module)
        prefix = config["prefix"]
        feat_dir = FRONTEND_DIR / "src/features/performance"
        list_screen_path = feat_dir / f"{prefix}List.tsx"
        form_modal_path = feat_dir / f"{prefix}FormModal.tsx"
        details_modal_path = feat_dir / f"{prefix}DetailsModal.tsx"
        if list_screen_path.exists() and form_modal_path.exists() and details_modal_path.exists():
            print(f"  [Frontend] Module {module} components already exist. Skipping generation.")
            register_frontend_ui(module, config)
            backend_done_queue.task_done()
            continue

        backend_context = f"--- SCHEMAS ---\n{schema_code}\n\n--- ENDPOINTS ---\n{endpoint_code}"
        
        rejection_report = None
        for cycle in range(1, MAX_RETRY_CYCLES + 1):
            print(f"  ⚡ Frontend Cycle {cycle}/{MAX_RETRY_CYCLES}")
            
            parsed = fg.run_generator(
                module=module,
                backend_context=backend_context,
                rejection_report=rejection_report
            )
            
            review = fr.run_reviewer(
                generated_files=parsed,
                module=module
            )
            
            print(f"  📊 Review Score: {review.get('overall_score')}/10 | Verdict: {review.get('verdict')}")
            
            if review.get("verdict") == "PASS":
                # 1. Append types
                types_path = FRONTEND_DIR / "src/features/performance/types.ts"
                types_path.parent.mkdir(parents=True, exist_ok=True)
                if not types_path.exists():
                    types_path.write_text("// Performance Types\n")
                types_content = types_path.read_text()
                if parsed["TYPES"] not in types_content:
                    types_path.write_text(types_content + "\n\n" + parsed["TYPES"])
                
                # 2. Append service
                service_path = FRONTEND_DIR / "src/features/performance/performanceService.ts"
                service_path.parent.mkdir(parents=True, exist_ok=True)
                if not service_path.exists():
                    service_path.write_text("import { api } from '../../services/api';\nimport * as types from './types';\n\nexport const performanceService = {\n};\n")
                
                service_content = service_path.read_text()
                # Clean up/append methods inside performanceService object
                clean_service_methods = parsed["SERVICE"].strip()
                # Stripping outer object brackets if model generated them
                if clean_service_methods.startswith("export const performanceService = {") or clean_service_methods.startswith("performanceService = {"):
                    # Extract contents between outermost brackets
                    bracket_match = re.search(r"\{\s*(.*)\s*\}", clean_service_methods, re.DOTALL)
                    if bracket_match:
                        clean_service_methods = bracket_match.group(1).strip()
                
                # Add to service
                if clean_service_methods not in service_content:
                    service_content = service_content.replace(
                        "export const performanceService = {",
                        f"export const performanceService = {{\n  {clean_service_methods},"
                    )
                    service_path.write_text(service_content)
                
                # 3. Write components
                feat_dir.mkdir(parents=True, exist_ok=True)
                
                list_screen_path.write_text(parsed["LIST_SCREEN"])
                form_modal_path.write_text(parsed["FORM_MODAL"])
                details_modal_path.write_text(parsed["DETAILS_MODAL"])
                
                print(f"  💾 Saved components for {prefix}.")
                
                # 4. Integrate routes & sidebar
                register_frontend_ui(module, config)
                break
            else:
                rejection_report = review
                if cycle == MAX_RETRY_CYCLES:
                    print(f"  ❌ Frontend generation failed for {module} after {MAX_RETRY_CYCLES} attempts.")
                    return
                time.sleep(2)
                
        backend_done_queue.task_done()
        
    print("[Frontend Worker] Completed all modules.")


def main():
    # Start Backend Worker
    b_thread = threading.Thread(target=backend_worker)
    # Start Frontend Worker
    f_thread = threading.Thread(target=frontend_worker)
    
    b_thread.start()
    f_thread.start()
    
    b_thread.join()
    f_thread.join()
    
    print("\n🎉 Joint Pipelined Generation Complete for Performance Module!")


if __name__ == "__main__":
    main()
