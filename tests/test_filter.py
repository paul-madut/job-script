"""
Tests for the job filtering logic.
Verifies include/exclude keyword matching works correctly.

Run: pytest tests/test_filter.py -v
"""

from src.scraper import filter_jobs, JobPosting


def _make_job(title: str, preview: str = "", source: str = "indeed") -> JobPosting:
    return JobPosting(
        date_found="2026-04-13",
        company="TestCo",
        title=title,
        location="Ottawa, ON",
        salary_range="",
        url=f"https://example.com/{title.replace(' ', '-')}",
        job_description_preview=preview,
        job_description_full="",
        resume_variant="",
        resume_file="",
        status="new",
        source=source,
    )


class TestFilterInclude:

    def test_keeps_matching_title(self):
        jobs = [_make_job("Junior Software Developer")]
        result = filter_jobs(jobs, include_keywords=["software"], exclude_keywords=[])
        assert len(result) == 1

    def test_keeps_matching_preview(self):
        jobs = [_make_job("Some Role", preview="We use React and Node.js")]
        result = filter_jobs(jobs, include_keywords=["react"], exclude_keywords=[])
        assert len(result) == 1

    def test_drops_non_matching(self):
        jobs = [_make_job("Mechanical Engineer")]
        result = filter_jobs(jobs, include_keywords=["software", "developer"], exclude_keywords=[])
        assert len(result) == 0

    def test_case_insensitive(self):
        jobs = [_make_job("FRONTEND DEVELOPER")]
        result = filter_jobs(jobs, include_keywords=["frontend"], exclude_keywords=[])
        assert len(result) == 1


class TestFilterExclude:

    def test_excludes_senior(self):
        jobs = [_make_job("Senior Software Engineer")]
        result = filter_jobs(jobs, include_keywords=["software"], exclude_keywords=["senior"])
        assert len(result) == 0

    def test_excludes_by_title_not_preview(self):
        """Exclude keywords only match on title, not preview."""
        jobs = [_make_job("Software Developer", preview="report to senior manager")]
        result = filter_jobs(jobs, include_keywords=["software"], exclude_keywords=["senior"])
        assert len(result) == 1, "Should not exclude based on preview content"

    def test_excludes_multiple_keywords(self):
        jobs = [
            _make_job("Staff Engineer"),
            _make_job("Principal Developer"),
            _make_job("Junior Developer"),
        ]
        result = filter_jobs(
            jobs,
            include_keywords=["engineer", "developer"],
            exclude_keywords=["staff", "principal"],
        )
        assert len(result) == 1
        assert result[0].title == "Junior Developer"


class TestFilterCombined:

    def test_realistic_batch(self):
        """Simulate a realistic scrape with mixed relevant/irrelevant results."""
        jobs = [
            _make_job("Full Stack Developer"),
            _make_job("Senior Backend Engineer"),
            _make_job("Junior React Developer"),
            _make_job("Mechanical Engineer"),
            _make_job("Director of Engineering"),
            _make_job("DevOps Engineer"),
            _make_job("Data Entry Clerk", preview="No coding required"),
            _make_job("QA Analyst", preview="Testing web applications with Selenium"),
        ]

        include = ["developer", "engineer", "devops", "QA", "react"]
        exclude = ["senior", "director", "mechanical"]

        result = filter_jobs(jobs, include, exclude)
        titles = [j.title for j in result]

        assert "Full Stack Developer" in titles
        assert "Junior React Developer" in titles
        assert "DevOps Engineer" in titles
        assert "QA Analyst" in titles
        assert "Senior Backend Engineer" not in titles
        assert "Director of Engineering" not in titles
        assert "Mechanical Engineer" not in titles
        assert "Data Entry Clerk" not in titles

    def test_empty_filters_keeps_all(self):
        jobs = [_make_job("Anything"), _make_job("Whatever")]
        result = filter_jobs(jobs, include_keywords=[], exclude_keywords=[])
        assert len(result) == 0, "Empty include list means nothing matches"
