"""
Resume Assembler Module
=======================
Takes a job description + content banks → produces a tailored LaTeX resume → compiles to PDF.

Uses Claude API to score relevance of each bank item against the job description,
then assembles the best combination into the LaTeX template.
"""

import json
import os
import subprocess
import shutil
import time
from pathlib import Path
from anthropic import Anthropic, APIError, APIConnectionError, RateLimitError

from src.logger import get_logger

log = get_logger("assembler")

# Paths
BASE_DIR = Path(__file__).parent.parent
BANKS_DIR = BASE_DIR / "content_banks"
TEMPLATE_PATH = BASE_DIR / "templates" / "resume_template.tex"
OUTPUT_DIR = BASE_DIR / "output" / "resumes"


def load_banks():
    """Load all content banks from JSON files."""
    with open(BANKS_DIR / "experiences.json") as f:
        experiences = json.load(f)["experiences"]
    with open(BANKS_DIR / "projects.json") as f:
        projects = json.load(f)["projects"]
    with open(BANKS_DIR / "skills.json") as f:
        skills = json.load(f)["skill_categories"]
    return experiences, projects, skills


def select_content_ai(job_description: str, job_title: str, experiences: list, projects: list, config: dict) -> dict:
    """
    Use Claude to pick the most relevant experiences and projects for this job.
    Returns dict with selected experience IDs, project IDs, and reasoning.
    """
    client = Anthropic()

    # Build a summary of available items for the prompt
    exp_summary = []
    for exp in experiences:
        exp_summary.append({
            "id": exp["id"],
            "company": exp["company"],
            "title": exp["title"],
            "tags": exp["tags"],
            "always_include": exp.get("always_include", False),
            "bullet_ids": [b["id"] for b in exp["bullets"]],
            "bullet_tags": [b["tags"] for b in exp["bullets"]]
        })

    proj_summary = []
    for proj in projects:
        proj_summary.append({
            "id": proj["id"],
            "name": proj["name"],
            "tags": proj["tags"]
        })

    max_exp = config.get("max_experiences", 4)
    max_proj = config.get("max_projects", 3)

    prompt = f"""You are a resume optimization expert. Given a job posting, select the most relevant items from the candidate's content banks.

JOB TITLE: {job_title}

JOB DESCRIPTION:
{job_description[:3000]}

AVAILABLE EXPERIENCES:
{json.dumps(exp_summary, indent=2)}

AVAILABLE PROJECTS:
{json.dumps(proj_summary, indent=2)}

RULES:
1. Select exactly {max_exp} experiences. Items with "always_include": true MUST be included.
2. Select exactly {max_proj} projects. Pick the ones most relevant to this specific job.
3. For the NeoBank project, choose EITHER "neobank_fullstack" OR "neobank_backend" depending on the role focus — never both.
4. Order experiences by priority (most relevant first).
5. For each experience, select which bullets are most relevant (max {config.get('max_bullets_per_exp', 3)} per experience).

Respond with ONLY valid JSON in this exact format:
{{
  "experience_ids": ["id1", "id2", "id3", "id4"],
  "experience_bullets": {{
    "id1": ["bullet_id1", "bullet_id2"],
    "id2": ["bullet_id1", "bullet_id2", "bullet_id3"]
  }},
  "project_ids": ["proj1", "proj2", "proj3"],
  "role_type": "frontend|backend|fullstack",
  "reasoning": "Brief explanation of choices"
}}"""

    # Retry with exponential backoff for transient API failures
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.messages.create(
                model=config.get("model", "claude-sonnet-4-20250514"),
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )
            break
        except RateLimitError as e:
            wait = 2 ** (attempt + 2)  # 4s, 8s, 16s
            log.warning(f"API rate limited (attempt {attempt+1}/{max_retries}), waiting {wait}s...")
            time.sleep(wait)
            if attempt == max_retries - 1:
                raise
        except (APIConnectionError, APIError) as e:
            wait = 2 ** (attempt + 1)  # 2s, 4s, 8s
            log.warning(f"API error (attempt {attempt+1}/{max_retries}): {e}, retrying in {wait}s...")
            time.sleep(wait)
            if attempt == max_retries - 1:
                raise

    # Parse the JSON response
    response_text = response.content[0].text
    # Strip markdown code fences if present
    if "```json" in response_text:
        response_text = response_text.split("```json")[1].split("```")[0]
    elif "```" in response_text:
        response_text = response_text.split("```")[1].split("```")[0]

    return json.loads(response_text.strip())


def select_content_rule_based(job_description: str, job_title: str, experiences: list, projects: list, config: dict) -> dict:
    """
    Simple tag-matching fallback that doesn't use API calls.
    Useful for testing or saving API costs.
    """
    job_text = (job_title + " " + job_description).lower()

    # Determine role type from job text
    frontend_signals = ["frontend", "front-end", "react", "ui", "ux", "css", "next.js", "nextjs"]
    backend_signals = ["backend", "back-end", "api", "database", "python", "django", "node", "server", "devops", "infrastructure"]

    frontend_score = sum(1 for s in frontend_signals if s in job_text)
    backend_score = sum(1 for s in backend_signals if s in job_text)

    if frontend_score > backend_score * 1.5:
        role_type = "frontend"
    elif backend_score > frontend_score * 1.5:
        role_type = "backend"
    else:
        role_type = "fullstack"

    # Select experiences: always_include first, then best match for 4th slot
    selected_exp = [e["id"] for e in experiences if e.get("always_include")]

    if role_type == "frontend":
        optional_pick = "webflux"
    elif role_type == "backend":
        optional_pick = "parks_canada"
    else:
        optional_pick = "webflux"  # default to webflux for fullstack

    if optional_pick not in selected_exp:
        selected_exp.append(optional_pick)

    # Select all bullets for each experience (simplified)
    exp_bullets = {}
    for exp in experiences:
        if exp["id"] in selected_exp:
            exp_bullets[exp["id"]] = [b["id"] for b in exp["bullets"]]

    # Select projects based on role type
    if role_type == "frontend":
        project_ids = ["cro_dashboard", "b2lead", "content_creator"]
    elif role_type == "backend":
        project_ids = ["algo_trading_saas", "neobank_backend", "gethub"]
    else:
        project_ids = ["algo_trading_saas", "neobank_fullstack", "content_creator"]

    return {
        "experience_ids": selected_exp[:config.get("max_experiences", 4)],
        "experience_bullets": exp_bullets,
        "project_ids": project_ids[:config.get("max_projects", 3)],
        "role_type": role_type,
        "reasoning": f"Rule-based selection for {role_type} role"
    }


def build_latex(selection: dict, experiences: list, projects: list, skills: list) -> str:
    """
    Assemble the final LaTeX document by filling in the template placeholders.
    """
    with open(TEMPLATE_PATH) as f:
        template = f.read()

    # Build experiences block
    exp_lookup = {e["id"]: e for e in experiences}
    experiences_latex = ""
    for exp_id in selection["experience_ids"]:
        exp = exp_lookup[exp_id]
        title_str = exp["title"]
        if exp.get("url"):
            title_str = f'\\href{{{exp["url"]}}}{{{exp["title"]}}}'

        experiences_latex += f"""    \\resumeSubheading
      {{{exp["company"]}}}{{{exp["location"]}}}
      {{{title_str}}}{{{exp["start_date"]} -- {exp["end_date"]}}}
      \\resumeItemListStart
"""
        # Get selected bullets for this experience
        bullet_ids = selection.get("experience_bullets", {}).get(exp_id, [b["id"] for b in exp["bullets"]])
        for bullet in exp["bullets"]:
            if bullet["id"] in bullet_ids:
                experiences_latex += f'        \\resumeItemNH{{{bullet["text"]}}}\n'

        experiences_latex += "      \\resumeItemListEnd\n"

    # Build projects block
    proj_lookup = {p["id"]: p for p in projects}
    projects_latex = ""
    for proj_id in selection["project_ids"]:
        proj = proj_lookup[proj_id]
        projects_latex += f'    \\resumeSubItem{{{proj["name"]}}}\n'
        projects_latex += f'      {{{proj["description"]}}}\n'

    # Build skills block
    skills_latex = ""
    for cat in skills:
        items_str = ", ".join(cat["items"])
        if cat.get("certifications"):
            for cert in cat["certifications"]:
                items_str += f',{{\\href{{{cert["url"]}}}{{{cert["name"]}}}}}'
        skills_latex += f'    \\resumeSubItem{{{cat["label"]}}}\n'
        skills_latex += f'      {{{items_str}}}\n'

    # Fill template
    latex = template.replace("%%EXPERIENCES_BLOCK%%", experiences_latex)
    latex = latex.replace("%%PROJECTS_BLOCK%%", projects_latex)
    latex = latex.replace("%%SKILLS_BLOCK%%", skills_latex)

    return latex


def compile_pdf(latex_content: str, output_name: str) -> Path:
    """
    Compile LaTeX to PDF using pdflatex.
    Returns path to the generated PDF.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Write .tex file
    tex_path = OUTPUT_DIR / f"{output_name}.tex"
    pdf_path = OUTPUT_DIR / f"{output_name}.pdf"

    with open(tex_path, "w") as f:
        f.write(latex_content)

    # Compile with pdflatex (run twice for references)
    for _ in range(2):
        result = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "-output-directory", str(OUTPUT_DIR), str(tex_path)],
            capture_output=True,
            text=True,
            timeout=30
        )

    if not pdf_path.exists():
        raise RuntimeError(f"PDF compilation failed.\nSTDOUT: {result.stdout[-500:]}\nSTDERR: {result.stderr[-500:]}")

    # Clean up auxiliary files
    for ext in [".aux", ".log", ".out"]:
        aux_file = OUTPUT_DIR / f"{output_name}{ext}"
        try:
            if aux_file.exists():
                aux_file.unlink()
        except PermissionError:
            pass  # non-critical, just leftover build artifacts

    return pdf_path


def assemble_resume(job_description: str, job_title: str, company: str, config: dict) -> Path:
    """
    Main entry point: takes a job posting and produces a tailored PDF resume.

    Args:
        job_description: Full text of the job posting
        job_title: Job title
        company: Company name
        config: Resume config from settings.yaml

    Returns:
        Path to the generated PDF
    """
    experiences, projects, skills = load_banks()

    # Select content
    strategy = config.get("selection_strategy", "ai")
    if strategy == "ai":
        selection = select_content_ai(job_description, job_title, experiences, projects, config)
    else:
        selection = select_content_rule_based(job_description, job_title, experiences, projects, config)

    # Build LaTeX
    latex = build_latex(selection, experiences, projects, skills)

    # Compile to PDF
    safe_company = "".join(c for c in company if c.isalnum() or c in "._- ").strip().replace(" ", "_")
    safe_title = "".join(c for c in job_title if c.isalnum() or c in "._- ").strip().replace(" ", "_")
    output_name = f"Paul_Madut__{safe_company}__{safe_title}"

    pdf_path = compile_pdf(latex, output_name)

    log.info(f"  -> Resume generated: {pdf_path}")
    log.info(f"  -> Strategy: {strategy} | Role type: {selection.get('role_type', 'unknown')}")
    log.debug(f"  -> Reasoning: {selection.get('reasoning', 'N/A')}")

    return pdf_path, selection
