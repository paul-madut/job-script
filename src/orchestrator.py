#!/usr/bin/env python3
"""
Job Cannon Orchestrator
=======================
Main CLI entry point. Ties together scraping, content selection, and resume generation.

Usage:
    # Full pipeline: scrape jobs + generate resumes
    python -m src.orchestrator run

    # Scrape only (just fill the spreadsheet, no resumes yet)
    python -m src.orchestrator scrape

    # Generate resume for a single job (paste URL or description)
    python -m src.orchestrator single --url "https://indeed.com/viewjob?jk=abc123"
    python -m src.orchestrator single --title "Software Engineer" --company "Shopify" --desc "job_desc.txt"

    # Re-generate resumes for all "new" jobs in the tracker
    python -m src.orchestrator generate

    # Dry run (show what would happen, no API calls)
    python -m src.orchestrator run --dry-run
"""

import argparse
import sys
import yaml
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent.parent

from src.scraper import IndeedScraper, LinkedInPublicScraper, save_to_csv, JobPosting
from src.assembler import assemble_resume, load_banks


def load_config() -> dict:
    """Load settings from config/settings.yaml."""
    config_path = BASE_DIR / "config" / "settings.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def cmd_scrape(config: dict, dry_run: bool = False):
    """Scrape job boards and save results to tracker CSV."""
    search_config = config["search"]
    scraping_config = config.get("scraping", {})
    output_config = config["output"]

    tracker_path = BASE_DIR / output_config["tracker_file"]
    all_jobs = []

    boards = search_config.get("boards", {})
    keywords = search_config["keywords"]
    locations = search_config["locations"]
    max_per_board = scraping_config.get("max_jobs_per_board", 50)

    if dry_run:
        print("\n[DRY RUN] Would scrape:")
        for kw in keywords:
            for loc in locations:
                print(f"  - '{kw}' in '{loc}'")
        print(f"  Boards: {[k for k, v in boards.items() if v]}")
        return []

    # Indeed
    if boards.get("indeed"):
        scraper = IndeedScraper({**scraping_config, **search_config})
        for keyword in keywords:
            for location in locations:
                jobs = scraper.search(keyword, location, max_results=max_per_board)
                all_jobs.extend(jobs)

    # LinkedIn (public)
    if boards.get("linkedin_public"):
        scraper = LinkedInPublicScraper({**scraping_config, **search_config})
        for keyword in keywords:
            for location in locations:
                jobs = scraper.search(keyword, location, max_results=25)
                all_jobs.extend(jobs)

    # Deduplicate by URL
    seen_urls = set()
    unique_jobs = []
    for job in all_jobs:
        if job.url not in seen_urls:
            seen_urls.add(job.url)
            unique_jobs.append(job)

    print(f"\nTotal unique jobs found: {len(unique_jobs)}")

    # Save to tracker
    new_jobs = save_to_csv(unique_jobs, tracker_path)
    return new_jobs


def cmd_generate(config: dict, jobs: list = None, dry_run: bool = False):
    """
    Generate tailored resumes for jobs.
    If jobs list is provided, use those. Otherwise, read 'new' jobs from tracker CSV.
    """
    import csv

    resume_config = config["resume"]
    output_config = config["output"]
    tracker_path = BASE_DIR / output_config["tracker_file"]

    if jobs is None:
        # Load 'new' jobs from CSV
        if not tracker_path.exists():
            print("No tracker file found. Run 'scrape' first.")
            return

        jobs = []
        with open(tracker_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("status") == "new" and not row.get("resume_file"):
                    jobs.append(JobPosting(
                        date_found=row["date_found"],
                        company=row["company"],
                        title=row["title"],
                        location=row["location"],
                        salary_range=row.get("salary_range", ""),
                        url=row["url"],
                        job_description_preview=row.get("job_description_preview", ""),
                        job_description_full="",
                        resume_variant="",
                        resume_file="",
                        status="new",
                        source=row.get("source", "unknown")
                    ))

    if not jobs:
        print("No new jobs to generate resumes for.")
        return

    if dry_run:
        print(f"\n[DRY RUN] Would generate {len(jobs)} resumes:")
        for j in jobs[:10]:
            print(f"  - {j.title} @ {j.company}")
        if len(jobs) > 10:
            print(f"  ... and {len(jobs) - 10} more")
        return

    print(f"\nGenerating resumes for {len(jobs)} jobs...")

    # For AI selection, we need full job descriptions
    # Fetch them if we only have previews
    scraper_config = config.get("scraping", {})
    if resume_config.get("selection_strategy") == "ai":
        indeed_scraper = IndeedScraper(scraper_config)
        for job in jobs:
            if not job.job_description_full and job.url:
                print(f"  Fetching full description: {job.company} - {job.title}")
                job.job_description_full = indeed_scraper.fetch_full_description(job)

    # Generate resumes
    results = []
    for i, job in enumerate(jobs):
        print(f"\n[{i+1}/{len(jobs)}] {job.company} - {job.title}")
        try:
            desc = job.job_description_full or job.job_description_preview
            pdf_path, selection = assemble_resume(
                job_description=desc,
                job_title=job.title,
                company=job.company,
                config={**resume_config, "model": config["api"]["model"]}
            )
            job.resume_file = str(pdf_path)
            job.resume_variant = selection.get("role_type", "unknown")
            results.append((job, pdf_path))
        except Exception as e:
            print(f"  [ERROR] Failed to generate resume: {e}")
            results.append((job, None))

    # Update tracker CSV with resume paths
    _update_tracker(tracker_path, results)

    successful = sum(1 for _, p in results if p)
    print(f"\nDone! Generated {successful}/{len(jobs)} resumes.")
    print(f"Resumes saved to: {BASE_DIR / config['output']['resumes_dir']}")
    print(f"Tracker updated: {tracker_path}")


def cmd_single(config: dict, title: str, company: str, description: str):
    """Generate a single resume for a specific job."""
    resume_config = config["resume"]

    print(f"Generating resume for: {title} @ {company}")
    pdf_path, selection = assemble_resume(
        job_description=description,
        job_title=title,
        company=company,
        config={**resume_config, "model": config["api"]["model"]}
    )
    print(f"\nResume saved to: {pdf_path}")
    print(f"Role type: {selection.get('role_type')}")
    print(f"Reasoning: {selection.get('reasoning')}")


def _update_tracker(tracker_path: Path, results: list):
    """Update the tracker CSV with resume file paths and variants."""
    import csv

    if not tracker_path.exists():
        return

    rows = []
    with open(tracker_path) as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    # Build lookup of results by URL
    result_lookup = {}
    for job, pdf_path in results:
        if pdf_path:
            result_lookup[job.url] = {
                "resume_file": str(pdf_path),
                "resume_variant": job.resume_variant,
            }

    # Update rows
    for row in rows:
        if row["url"] in result_lookup:
            row.update(result_lookup[row["url"]])

    with open(tracker_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(
        description="Job Cannon - Automated Resume Assembly Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.orchestrator run              # Full pipeline
  python -m src.orchestrator scrape           # Scrape jobs only
  python -m src.orchestrator generate         # Generate resumes for new jobs
  python -m src.orchestrator single \\
    --title "Software Engineer" \\
    --company "Shopify" \\
    --desc job_description.txt
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Run (full pipeline)
    run_parser = subparsers.add_parser("run", help="Full pipeline: scrape + generate")
    run_parser.add_argument("--dry-run", action="store_true", help="Preview without executing")

    # Scrape only
    scrape_parser = subparsers.add_parser("scrape", help="Scrape job boards only")
    scrape_parser.add_argument("--dry-run", action="store_true")

    # Generate only
    gen_parser = subparsers.add_parser("generate", help="Generate resumes for new tracker entries")
    gen_parser.add_argument("--dry-run", action="store_true")

    # Single job
    single_parser = subparsers.add_parser("single", help="Generate resume for a single job")
    single_parser.add_argument("--title", required=True, help="Job title")
    single_parser.add_argument("--company", required=True, help="Company name")
    single_parser.add_argument("--desc", required=True, help="Path to job description text file, or inline text")
    single_parser.add_argument("--url", help="Job posting URL (optional, for fetching description)")

    args = parser.parse_args()
    config = load_config()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "run":
        jobs = cmd_scrape(config, dry_run=args.dry_run)
        cmd_generate(config, jobs=jobs if not args.dry_run else None, dry_run=args.dry_run)

    elif args.command == "scrape":
        cmd_scrape(config, dry_run=args.dry_run)

    elif args.command == "generate":
        cmd_generate(config, dry_run=args.dry_run)

    elif args.command == "single":
        # Load description from file or use as inline text
        desc_path = Path(args.desc)
        if desc_path.exists():
            description = desc_path.read_text()
        else:
            description = args.desc

        # If URL provided and no file description, try to fetch
        if args.url and not desc_path.exists():
            from src.scraper import IndeedScraper
            scraper = IndeedScraper(config.get("scraping", {}))
            job = JobPosting(
                date_found="", company=args.company, title=args.title,
                location="", salary_range="", url=args.url,
                job_description_preview="", job_description_full="",
                resume_variant="", resume_file="", status="new", source="manual"
            )
            description = scraper.fetch_full_description(job)

        cmd_single(config, title=args.title, company=args.company, description=description)


if __name__ == "__main__":
    main()
