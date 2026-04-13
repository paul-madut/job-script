"""
Job Scraper Module
==================
Scrapes job postings from Indeed (and eventually other boards).
Returns structured job data for the assembler to process.

NOTE: Web scraping is inherently fragile. If Indeed changes their HTML structure,
the selectors in this file will need updating. That's expected maintenance.
"""

import time
import random
import csv
import re
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional

import requests
from bs4 import BeautifulSoup

from src.logger import get_logger

log = get_logger("scraper")
BASE_DIR = Path(__file__).parent.parent


@dataclass
class JobPosting:
    date_found: str
    company: str
    title: str
    location: str
    salary_range: str
    url: str
    job_description_preview: str
    job_description_full: str  # not saved to CSV, used by assembler
    resume_variant: str  # filled after assembly
    resume_file: str  # filled after assembly
    status: str  # new, applied, rejected, interview, offer
    source: str  # indeed, linkedin, etc.


class IndeedScraper:
    """
    Scrapes Indeed job listings using their public search pages.

    Indeed's HTML structure changes frequently, so this uses a resilient
    approach with multiple fallback selectors.
    """

    BASE_URL = "https://ca.indeed.com"  # Canadian Indeed for Ottawa-based search

    def __init__(self, config: dict):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": config.get("user_agent",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })
        self.delay = config.get("delay_between_requests_sec", 2)

    def _get_with_retry(self, url: str, params: dict = None, max_retries: int = 3) -> requests.Response:
        """GET request with exponential backoff on transient failures."""
        for attempt in range(max_retries):
            try:
                resp = self.session.get(url, params=params, timeout=15)
                if resp.status_code == 429:
                    wait = 2 ** (attempt + 2)
                    log.warning(f"Rate limited (attempt {attempt+1}), waiting {wait}s...")
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp
            except requests.ConnectionError as e:
                wait = 2 ** (attempt + 1)
                log.warning(f"Connection error (attempt {attempt+1}): {e}, retrying in {wait}s...")
                time.sleep(wait)
                if attempt == max_retries - 1:
                    raise
        return resp  # return last response even if 429

    def search(self, keyword: str, location: str, max_results: int = 50) -> list[JobPosting]:
        """
        Search Indeed for jobs matching keyword + location.
        Returns list of JobPosting objects.
        """
        jobs = []
        start = 0
        per_page = 10  # Indeed shows 10-15 results per page

        log.info(f"  Searching Indeed: '{keyword}' in '{location}'...")

        while len(jobs) < max_results:
            params = {
                "q": keyword,
                "l": location,
                "start": start,
                "sort": "date",  # most recent first
                "fromage": self.config.get("posted_within_days", 7),
            }

            # Add salary filter if configured
            salary_min = self.config.get("salary_min")
            if salary_min:
                params["salary"] = f"${salary_min}"

            try:
                resp = self._get_with_retry(f"{self.BASE_URL}/jobs", params=params)
            except requests.RequestException as e:
                log.warning(f"Request failed for page {start}: {e}")
                break

            soup = BeautifulSoup(resp.text, "html.parser")

            # Indeed uses various class patterns - try multiple selectors
            job_cards = (
                soup.select("div.job_seen_beacon") or
                soup.select("div.jobsearch-ResultsList > div") or
                soup.select("td.resultContent") or
                soup.select("[data-jk]")  # fallback: any element with job key
            )

            if not job_cards:
                log.info(f"  No more results at offset {start}")
                break

            for card in job_cards:
                job = self._parse_card(card)
                if job:
                    jobs.append(job)

            start += per_page

            # Rate limiting - be respectful
            delay = self.delay + random.uniform(0.5, 1.5)
            time.sleep(delay)

        log.info(f"  Found {len(jobs)} jobs for '{keyword}' in '{location}'")
        return jobs[:max_results]

    def _parse_card(self, card) -> Optional[JobPosting]:
        """Parse a single job card HTML element into a JobPosting."""
        try:
            # Title
            title_el = (
                card.select_one("h2.jobTitle a") or
                card.select_one("a.jcs-JobTitle") or
                card.select_one("[data-jk] a") or
                card.select_one("h2 a")
            )
            if not title_el:
                return None

            title = title_el.get_text(strip=True)
            job_url = title_el.get("href", "")
            if job_url.startswith("/"):
                job_url = f"{self.BASE_URL}{job_url}"

            # Company
            company_el = (
                card.select_one("span[data-testid='company-name']") or
                card.select_one("span.companyName") or
                card.select_one("span.company")
            )
            company = company_el.get_text(strip=True) if company_el else "Unknown"

            # Location
            location_el = (
                card.select_one("div[data-testid='text-location']") or
                card.select_one("div.companyLocation") or
                card.select_one("span.location")
            )
            location = location_el.get_text(strip=True) if location_el else "Unknown"

            # Salary (often not listed)
            salary_el = (
                card.select_one("div.salary-snippet-container") or
                card.select_one("span.estimated-salary") or
                card.select_one("[class*='salary']")
            )
            salary = salary_el.get_text(strip=True) if salary_el else ""

            # Snippet/preview
            snippet_el = (
                card.select_one("div.job-snippet") or
                card.select_one("table.jobCardShelfContainer") or
                card.select_one("[class*='snippet']")
            )
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""

            return JobPosting(
                date_found=datetime.now().strftime("%Y-%m-%d"),
                company=company,
                title=title,
                location=location,
                salary_range=salary,
                url=job_url,
                job_description_preview=snippet[:200],
                job_description_full="",  # fetched separately if needed
                resume_variant="",
                resume_file="",
                status="new",
                source="indeed"
            )

        except Exception as e:
            log.warning(f"Failed to parse job card: {e}")
            return None

    def fetch_full_description(self, job: JobPosting) -> str:
        """
        Fetch the full job description from the job's detail page.
        This is needed for AI-powered resume tailoring.
        """
        if not job.url:
            return ""

        try:
            time.sleep(self.delay + random.uniform(0.5, 1.0))
            resp = self._get_with_retry(job.url)

            soup = BeautifulSoup(resp.text, "html.parser")
            desc_el = (
                soup.select_one("div#jobDescriptionText") or
                soup.select_one("div.jobsearch-jobDescriptionText") or
                soup.select_one("[class*='description']")
            )

            if desc_el:
                return desc_el.get_text(separator="\n", strip=True)

        except Exception as e:
            log.warning(f"Failed to fetch description for {job.url}: {e}")

        return job.job_description_preview  # fallback to snippet


class LinkedInPublicScraper:
    """
    Scrapes LinkedIn's public job search (no login required).
    Uses the guest job search endpoint which has limited but usable results.

    NOTE: LinkedIn is aggressive about rate limiting. Use sparingly.
    """

    BASE_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

    def __init__(self, config: dict):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": config.get("user_agent",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36"
            ),
        })
        self.delay = max(config.get("delay_between_requests_sec", 2), 3)  # minimum 3s for LinkedIn

    def search(self, keyword: str, location: str, max_results: int = 25) -> list[JobPosting]:
        """Search LinkedIn public job listings."""
        jobs = []
        start = 0

        log.info(f"  Searching LinkedIn (public): '{keyword}' in '{location}'...")

        while len(jobs) < max_results:
            params = {
                "keywords": keyword,
                "location": location,
                "start": start,
                "f_TPR": "r604800",  # past week
                "f_E": "2",  # entry level
            }

            try:
                resp = self.session.get(self.BASE_URL, params=params, timeout=15)

                if resp.status_code == 429:
                    log.warning("LinkedIn rate limited. Stopping LinkedIn scrape.")
                    break

                resp.raise_for_status()
            except requests.RequestException as e:
                log.warning(f"LinkedIn request failed: {e}")
                break

            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.select("li")

            if not cards:
                break

            for card in cards:
                job = self._parse_linkedin_card(card)
                if job:
                    jobs.append(job)

            start += 25
            time.sleep(self.delay + random.uniform(1.0, 3.0))

        log.info(f"  Found {len(jobs)} jobs from LinkedIn")
        return jobs[:max_results]

    def fetch_full_description(self, job: JobPosting) -> str:
        """Fetch full job description from a LinkedIn job detail page."""
        if not job.url:
            return ""

        try:
            time.sleep(self.delay + random.uniform(1.0, 2.0))
            resp = self.session.get(job.url, timeout=15)

            if resp.status_code == 429:
                log.warning("LinkedIn rate limited during description fetch.")
                return job.job_description_preview

            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            desc_el = (
                soup.select_one("div.show-more-less-html__markup") or
                soup.select_one("div.description__text") or
                soup.select_one("[class*='description']")
            )

            if desc_el:
                return desc_el.get_text(separator="\n", strip=True)

        except Exception as e:
            log.warning(f"Failed to fetch LinkedIn description for {job.url}: {e}")

        return job.job_description_preview

    def _parse_linkedin_card(self, card) -> Optional[JobPosting]:
        """Parse a LinkedIn public job card."""
        try:
            title_el = card.select_one("h3.base-search-card__title")
            company_el = card.select_one("h4.base-search-card__subtitle")
            location_el = card.select_one("span.job-search-card__location")
            link_el = card.select_one("a.base-card__full-link")

            if not title_el:
                return None

            return JobPosting(
                date_found=datetime.now().strftime("%Y-%m-%d"),
                company=company_el.get_text(strip=True) if company_el else "Unknown",
                title=title_el.get_text(strip=True),
                location=location_el.get_text(strip=True) if location_el else "Unknown",
                salary_range="",
                url=link_el.get("href", "") if link_el else "",
                job_description_preview="",
                job_description_full="",
                resume_variant="",
                resume_file="",
                status="new",
                source="linkedin"
            )
        except Exception:
            return None


def filter_jobs(jobs: list[JobPosting], include_keywords: list[str], exclude_keywords: list[str]) -> list[JobPosting]:
    """
    Filter jobs locally. A job is kept if its title or preview matches at least
    one include keyword AND its title matches none of the exclude keywords.
    """
    kept = []
    for job in jobs:
        searchable = (job.title + " " + job.job_description_preview).lower()
        title_lower = job.title.lower()

        has_include = any(kw.lower() in searchable for kw in include_keywords)
        has_exclude = any(kw.lower() in title_lower for kw in exclude_keywords)

        if has_include and not has_exclude:
            kept.append(job)

    filtered_out = len(jobs) - len(kept)
    if filtered_out:
        log.info(f"  Filtered out {filtered_out} irrelevant jobs, kept {len(kept)}")
    return kept


def save_to_csv(jobs: list[JobPosting], filepath: Path):
    """Save or append job postings to the tracker CSV."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    file_exists = filepath.exists()

    # Load existing URLs to avoid duplicates
    existing_urls = set()
    if file_exists:
        with open(filepath, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_urls.add(row.get("url", ""))

    fieldnames = [
        "date_found", "company", "title", "location", "salary_range",
        "url", "job_description_preview", "resume_variant", "resume_file",
        "status", "source"
    ]

    new_jobs = [j for j in jobs if j.url not in existing_urls]

    with open(filepath, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        for job in new_jobs:
            row = asdict(job)
            row.pop("job_description_full", None)  # don't save full desc to CSV
            writer.writerow(row)

    log.info(f"  Saved {len(new_jobs)} new jobs to {filepath} ({len(jobs) - len(new_jobs)} duplicates skipped)")
    return new_jobs
