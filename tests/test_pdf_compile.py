"""
Tests for PDF compilation. Requires pdflatex installed.
Skipped automatically if pdflatex is not available.

Run: pytest tests/test_pdf_compile.py -v
"""

import shutil
import pytest
from pathlib import Path

from src.assembler import load_banks, select_content_rule_based, build_latex, compile_pdf

has_pdflatex = shutil.which("pdflatex") is not None
skip_no_latex = pytest.mark.skipif(not has_pdflatex, reason="pdflatex not installed")


@skip_no_latex
class TestPDFCompile:

    def test_frontend_resume_compiles(self, resume_config, tmp_path, monkeypatch):
        """Build a frontend resume end-to-end and verify PDF is created."""
        experiences, projects, skills = load_banks()
        selection = select_content_rule_based(
            "Frontend React developer with CSS and UI/UX skills",
            "Frontend Developer",
            experiences, projects, resume_config,
        )
        latex = build_latex(selection, experiences, projects, skills)

        # Compile to tmp dir so we don't pollute output/resumes
        import src.assembler as asm
        monkeypatch.setattr(asm, "OUTPUT_DIR", tmp_path)

        pdf_path = compile_pdf(latex, "test_frontend")
        assert pdf_path.exists()
        assert pdf_path.suffix == ".pdf"
        assert pdf_path.stat().st_size > 1000  # should be a real PDF, not empty

    def test_backend_resume_compiles(self, resume_config, tmp_path, monkeypatch):
        """Build a backend resume end-to-end and verify PDF is created."""
        experiences, projects, skills = load_banks()
        selection = select_content_rule_based(
            "Backend Python Django API database server infrastructure devops engineer",
            "Backend Engineer",
            experiences, projects, resume_config,
        )
        latex = build_latex(selection, experiences, projects, skills)

        import src.assembler as asm
        monkeypatch.setattr(asm, "OUTPUT_DIR", tmp_path)

        pdf_path = compile_pdf(latex, "test_backend")
        assert pdf_path.exists()
        assert pdf_path.suffix == ".pdf"

    def test_fullstack_resume_compiles(self, resume_config, tmp_path, monkeypatch):
        """Build a fullstack resume end-to-end."""
        experiences, projects, skills = load_banks()
        selection = select_content_rule_based(
            "Full stack JavaScript React Node.js developer",
            "Full Stack Developer",
            experiences, projects, resume_config,
        )
        latex = build_latex(selection, experiences, projects, skills)

        import src.assembler as asm
        monkeypatch.setattr(asm, "OUTPUT_DIR", tmp_path)

        pdf_path = compile_pdf(latex, "test_fullstack")
        assert pdf_path.exists()

    def test_cleanup_aux_files(self, resume_config, tmp_path, monkeypatch):
        """Verify .aux, .log, .out files are cleaned up after compilation."""
        experiences, projects, skills = load_banks()
        selection = select_content_rule_based(
            "Developer", "Developer",
            experiences, projects, resume_config,
        )
        latex = build_latex(selection, experiences, projects, skills)

        import src.assembler as asm
        monkeypatch.setattr(asm, "OUTPUT_DIR", tmp_path)

        compile_pdf(latex, "test_cleanup")

        assert not (tmp_path / "test_cleanup.aux").exists()
        assert not (tmp_path / "test_cleanup.log").exists()
        assert not (tmp_path / "test_cleanup.out").exists()
        # .tex stays (by design)
        assert (tmp_path / "test_cleanup.tex").exists()
