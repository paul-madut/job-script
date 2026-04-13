"""
Tests for rule-based content selection.
No API calls — verifies the tag-matching logic picks appropriate content.

Run: pytest tests/test_rule_based_selection.py -v
"""

import pytest

from src.assembler import select_content_rule_based, load_banks


@pytest.fixture
def banks():
    return load_banks()  # experiences, projects, skills


class TestRoleDetection:

    def test_detects_frontend(self, banks, resume_config):
        experiences, projects, _ = banks
        result = select_content_rule_based(
            "Looking for a React frontend developer with CSS and UI/UX skills",
            "Frontend Developer",
            experiences, projects, resume_config,
        )
        assert result["role_type"] == "frontend"

    def test_detects_backend(self, banks, resume_config):
        experiences, projects, _ = banks
        result = select_content_rule_based(
            "Backend engineer needed for API development with Python Django and database optimization on server infrastructure",
            "Backend Engineer",
            experiences, projects, resume_config,
        )
        assert result["role_type"] == "backend"

    def test_detects_fullstack(self, banks, resume_config):
        experiences, projects, _ = banks
        result = select_content_rule_based(
            "Full stack developer with React frontend and Node backend API experience",
            "Full Stack Developer",
            experiences, projects, resume_config,
        )
        assert result["role_type"] == "fullstack"


class TestExperienceSelection:

    def test_always_include_items_selected(self, banks, resume_config):
        experiences, projects, _ = banks
        always_ids = {e["id"] for e in experiences if e.get("always_include")}

        result = select_content_rule_based(
            "Any job description here",
            "Software Developer",
            experiences, projects, resume_config,
        )
        selected = set(result["experience_ids"])
        assert always_ids.issubset(selected), (
            f"always_include items {always_ids - selected} were not selected"
        )

    def test_respects_max_experiences(self, banks, resume_config):
        experiences, projects, _ = banks
        resume_config["max_experiences"] = 3
        result = select_content_rule_based(
            "Any description",
            "Developer",
            experiences, projects, resume_config,
        )
        assert len(result["experience_ids"]) <= 3

    def test_frontend_picks_webflux(self, banks, resume_config):
        experiences, projects, _ = banks
        result = select_content_rule_based(
            "Frontend React CSS UI UX design responsive",
            "Frontend Developer",
            experiences, projects, resume_config,
        )
        assert "webflux" in result["experience_ids"]

    def test_backend_picks_parks_canada(self, banks, resume_config):
        experiences, projects, _ = banks
        result = select_content_rule_based(
            "Backend Python API database server Django infrastructure devops",
            "Backend Engineer",
            experiences, projects, resume_config,
        )
        assert "parks_canada" in result["experience_ids"]

    def test_all_selected_ids_are_valid(self, banks, resume_config):
        experiences, projects, _ = banks
        valid_ids = {e["id"] for e in experiences}

        result = select_content_rule_based(
            "Any description",
            "Developer",
            experiences, projects, resume_config,
        )
        for eid in result["experience_ids"]:
            assert eid in valid_ids, f"Selected unknown experience ID: {eid}"


class TestProjectSelection:

    def test_frontend_gets_frontend_projects(self, banks, resume_config):
        experiences, projects, _ = banks
        result = select_content_rule_based(
            "Frontend React CSS UI design",
            "Frontend Developer",
            experiences, projects, resume_config,
        )
        assert "cro_dashboard" in result["project_ids"]

    def test_backend_gets_backend_projects(self, banks, resume_config):
        experiences, projects, _ = banks
        result = select_content_rule_based(
            "Backend Python API database server Django infrastructure devops",
            "Backend Engineer",
            experiences, projects, resume_config,
        )
        assert "neobank_backend" in result["project_ids"]
        assert "neobank_fullstack" not in result["project_ids"]

    def test_respects_max_projects(self, banks, resume_config):
        experiences, projects, _ = banks
        result = select_content_rule_based(
            "Any description",
            "Developer",
            experiences, projects, resume_config,
        )
        assert len(result["project_ids"]) <= resume_config["max_projects"]

    def test_all_selected_project_ids_are_valid(self, banks, resume_config):
        experiences, projects, _ = banks
        valid_ids = {p["id"] for p in projects}

        result = select_content_rule_based(
            "Any description",
            "Developer",
            experiences, projects, resume_config,
        )
        for pid in result["project_ids"]:
            assert pid in valid_ids, f"Selected unknown project ID: {pid}"


class TestSelectionOutput:

    def test_has_all_required_keys(self, banks, resume_config):
        experiences, projects, _ = banks
        result = select_content_rule_based(
            "Any description",
            "Developer",
            experiences, projects, resume_config,
        )
        assert "experience_ids" in result
        assert "experience_bullets" in result
        assert "project_ids" in result
        assert "role_type" in result
        assert "reasoning" in result

    def test_experience_bullets_populated(self, banks, resume_config):
        experiences, projects, _ = banks
        result = select_content_rule_based(
            "Full stack developer",
            "Developer",
            experiences, projects, resume_config,
        )
        for eid in result["experience_ids"]:
            assert eid in result["experience_bullets"], (
                f"No bullets selected for experience '{eid}'"
            )
            assert len(result["experience_bullets"][eid]) >= 1
