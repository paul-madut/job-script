"""
Tests for the CSV job tracker (save, dedup, update).

Run: pytest tests/test_csv_tracker.py -v
"""

import csv
import pytest
from pathlib import Path

from src.scraper import save_to_csv, JobPosting


@pytest.fixture
def tmp_csv(tmp_path):
    return tmp_path / "test_tracker.csv"


def _make_job(title="Dev", company="Co", url="https://example.com/1") -> JobPosting:
    return JobPosting(
        date_found="2026-04-13",
        company=company,
        title=title,
        location="Ottawa",
        salary_range="",
        url=url,
        job_description_preview="A job",
        job_description_full="Full description here",
        resume_variant="",
        resume_file="",
        status="new",
        source="indeed",
    )


class TestSaveToCSV:

    def test_creates_csv_with_header(self, tmp_csv):
        jobs = [_make_job()]
        save_to_csv(jobs, tmp_csv)

        assert tmp_csv.exists()
        with open(tmp_csv) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["title"] == "Dev"
        assert rows[0]["status"] == "new"

    def test_does_not_save_full_description(self, tmp_csv):
        """job_description_full should not be in the CSV."""
        jobs = [_make_job()]
        save_to_csv(jobs, tmp_csv)

        with open(tmp_csv) as f:
            reader = csv.DictReader(f)
            row = next(reader)
        assert "job_description_full" not in row

    def test_deduplicates_by_url(self, tmp_csv):
        jobs = [_make_job(url="https://example.com/1")]
        save_to_csv(jobs, tmp_csv)

        # Save same job again
        more_jobs = [_make_job(url="https://example.com/1")]
        result = save_to_csv(more_jobs, tmp_csv)

        assert len(result) == 0  # nothing new saved

        with open(tmp_csv) as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1  # still just one row

    def test_appends_new_jobs(self, tmp_csv):
        save_to_csv([_make_job(url="https://example.com/1")], tmp_csv)
        save_to_csv([_make_job(url="https://example.com/2", title="Dev2")], tmp_csv)

        with open(tmp_csv) as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 2

    def test_returns_only_new_jobs(self, tmp_csv):
        save_to_csv([_make_job(url="https://example.com/1")], tmp_csv)

        mixed = [
            _make_job(url="https://example.com/1"),  # dup
            _make_job(url="https://example.com/2"),  # new
        ]
        result = save_to_csv(mixed, tmp_csv)
        assert len(result) == 1
        assert result[0].url == "https://example.com/2"
