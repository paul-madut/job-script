"""
Live scraper tests — actually hit Indeed/LinkedIn.
These are slow and may fail due to rate limiting or HTML changes.
Run explicitly when you want to verify scraping still works.

Run: pytest tests/test_scraper_live.py -v --run-live
"""

import pytest

from src.scraper import IndeedScraper, LinkedInPublicScraper


live = pytest.mark.skipif(
    "not config.getoption('--run-live', default=False)",
    reason="Pass --run-live to execute live scraper tests",
)


SCRAPER_CONFIG = {
    "delay_between_requests_sec": 3,
    "posted_within_days": 7,
    "user_agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


@live
class TestIndeedLive:

    def test_search_returns_results(self):
        scraper = IndeedScraper(SCRAPER_CONFIG)
        jobs = scraper.search("software developer", "Ottawa, ON", max_results=5)
        # May return 0 if blocked, but should not crash
        assert isinstance(jobs, list)
        if jobs:
            assert jobs[0].source == "indeed"
            assert jobs[0].title
            assert jobs[0].url

    def test_fetch_description(self):
        scraper = IndeedScraper(SCRAPER_CONFIG)
        jobs = scraper.search("developer", "Toronto, ON", max_results=1)
        if jobs:
            desc = scraper.fetch_full_description(jobs[0])
            assert isinstance(desc, str)
            assert len(desc) > 0


@live
class TestLinkedInLive:

    def test_search_returns_results(self):
        scraper = LinkedInPublicScraper(SCRAPER_CONFIG)
        jobs = scraper.search("software", "Canada", max_results=5)
        assert isinstance(jobs, list)
        if jobs:
            assert jobs[0].source == "linkedin"
            assert jobs[0].title
