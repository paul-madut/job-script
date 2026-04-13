"""
Tests for LaTeX resume building.
Verifies the template gets filled correctly — no API or pdflatex needed.

Run: pytest tests/test_latex_build.py -v
"""

import pytest

from src.assembler import load_banks, select_content_rule_based, build_latex


@pytest.fixture
def frontend_latex(resume_config):
    """Build a complete LaTeX document for a frontend role."""
    experiences, projects, skills = load_banks()
    selection = select_content_rule_based(
        "Frontend React developer with CSS and UI/UX skills and Next.js",
        "Frontend Developer",
        experiences, projects, resume_config,
    )
    return build_latex(selection, experiences, projects, skills)


@pytest.fixture
def backend_latex(resume_config):
    """Build a complete LaTeX document for a backend role."""
    experiences, projects, skills = load_banks()
    selection = select_content_rule_based(
        "Backend Python Django API database server infrastructure devops engineer",
        "Backend Engineer",
        experiences, projects, resume_config,
    )
    return build_latex(selection, experiences, projects, skills)


class TestLatexStructure:

    def test_is_valid_latex_document(self, frontend_latex):
        assert frontend_latex.startswith("%") or frontend_latex.startswith("\\")
        assert "\\begin{document}" in frontend_latex
        assert "\\end{document}" in frontend_latex

    def test_no_unfilled_placeholders(self, frontend_latex):
        assert "%%EXPERIENCES_BLOCK%%" not in frontend_latex
        assert "%%PROJECTS_BLOCK%%" not in frontend_latex
        assert "%%SKILLS_BLOCK%%" not in frontend_latex

    def test_has_header_info(self, frontend_latex):
        assert "Paul Madut" in frontend_latex
        assert "Carleton University" in frontend_latex

    def test_has_section_headings(self, frontend_latex):
        assert "Work Experience" in frontend_latex
        assert "Projects" in frontend_latex
        assert "Technical Skills" in frontend_latex


class TestLatexContent:

    def test_frontend_includes_always_include_experiences(self, frontend_latex):
        # The always_include companies should appear
        assert "ReInvest Wealth" in frontend_latex
        assert "Fincnx" in frontend_latex
        assert "Tradeful" in frontend_latex

    def test_frontend_includes_webflux(self, frontend_latex):
        assert "WebFlux" in frontend_latex

    def test_backend_includes_parks_canada(self, backend_latex):
        assert "Parks Canada" in backend_latex

    def test_has_skills(self, frontend_latex):
        assert "JavaScript" in frontend_latex
        assert "React" in frontend_latex
        assert "Python" in frontend_latex

    def test_has_resume_commands(self, frontend_latex):
        assert "\\resumeSubheading" in frontend_latex
        assert "\\resumeItemNH" in frontend_latex
        assert "\\resumeSubItem" in frontend_latex


class TestLatexForDifferentRoles:
    """Verify that different role types produce different content."""

    def test_frontend_and_backend_differ(self, frontend_latex, backend_latex):
        # They should have different project selections
        assert frontend_latex != backend_latex

    def test_frontend_has_cro_dashboard(self, frontend_latex):
        assert "CRO" in frontend_latex

    def test_backend_has_neobank_backend(self, backend_latex):
        assert "NeoBank Core Banking Backend" in backend_latex
