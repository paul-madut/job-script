"""
Tests for content bank integrity.
Verifies that experiences.json, projects.json, and skills.json
are well-formed and internally consistent.

Run: pytest tests/test_content_banks.py -v
"""

import json
from pathlib import Path

import pytest

from src.assembler import load_banks

ROOT = Path(__file__).parent.parent
BANKS = ROOT / "content_banks"


class TestContentBankFiles:
    """Verify the JSON files parse and have required structure."""

    def test_experiences_loads(self):
        with open(BANKS / "experiences.json") as f:
            data = json.load(f)
        assert "experiences" in data
        assert len(data["experiences"]) >= 1

    def test_projects_loads(self):
        with open(BANKS / "projects.json") as f:
            data = json.load(f)
        assert "projects" in data
        assert len(data["projects"]) >= 1

    def test_skills_loads(self):
        with open(BANKS / "skills.json") as f:
            data = json.load(f)
        assert "skill_categories" in data
        assert len(data["skill_categories"]) >= 1

    def test_load_banks_returns_three_lists(self):
        experiences, projects, skills = load_banks()
        assert isinstance(experiences, list)
        assert isinstance(projects, list)
        assert isinstance(skills, list)


class TestExperienceSchema:
    """Each experience must have the fields the assembler expects."""

    REQUIRED_FIELDS = ["id", "company", "location", "title", "start_date", "end_date", "tags", "bullets"]

    def test_all_experiences_have_required_fields(self):
        experiences, _, _ = load_banks()
        for exp in experiences:
            for field in self.REQUIRED_FIELDS:
                assert field in exp, f"Experience '{exp.get('id', '?')}' missing field '{field}'"

    def test_all_experience_ids_unique(self):
        experiences, _, _ = load_banks()
        ids = [e["id"] for e in experiences]
        assert len(ids) == len(set(ids)), f"Duplicate experience IDs: {ids}"

    def test_all_bullet_ids_unique(self):
        experiences, _, _ = load_banks()
        all_bullet_ids = []
        for exp in experiences:
            for bullet in exp["bullets"]:
                all_bullet_ids.append(bullet["id"])
        assert len(all_bullet_ids) == len(set(all_bullet_ids)), f"Duplicate bullet IDs found"

    def test_bullets_have_text_and_tags(self):
        experiences, _, _ = load_banks()
        for exp in experiences:
            for bullet in exp["bullets"]:
                assert "text" in bullet, f"Bullet '{bullet.get('id')}' missing 'text'"
                assert "tags" in bullet, f"Bullet '{bullet.get('id')}' missing 'tags'"
                assert len(bullet["text"]) > 0

    def test_at_least_one_always_include(self):
        experiences, _, _ = load_banks()
        always = [e for e in experiences if e.get("always_include")]
        assert len(always) >= 1, "Need at least one always_include experience"


class TestProjectSchema:
    """Each project must have the fields the assembler expects."""

    REQUIRED_FIELDS = ["id", "name", "tags", "description"]

    def test_all_projects_have_required_fields(self):
        _, projects, _ = load_banks()
        for proj in projects:
            for field in self.REQUIRED_FIELDS:
                assert field in proj, f"Project '{proj.get('id', '?')}' missing field '{field}'"

    def test_all_project_ids_unique(self):
        _, projects, _ = load_banks()
        ids = [p["id"] for p in projects]
        assert len(ids) == len(set(ids)), f"Duplicate project IDs: {ids}"

    def test_neobank_variants_exist(self):
        """The assembler prompt says 'choose EITHER neobank_fullstack OR neobank_backend'."""
        _, projects, _ = load_banks()
        ids = {p["id"] for p in projects}
        assert "neobank_fullstack" in ids, "Missing neobank_fullstack project"
        assert "neobank_backend" in ids, "Missing neobank_backend project"


class TestSkillSchema:

    def test_all_categories_have_label_and_items(self):
        _, _, skills = load_banks()
        for cat in skills:
            assert "label" in cat, f"Skill category missing 'label'"
            assert "items" in cat, f"Skill category '{cat.get('label')}' missing 'items'"
            assert len(cat["items"]) >= 1
