"""
Naukri Job Scraper
==================
A Python scraper for Naukri.com that mirrors the functionality of the Apify actor.

Modes:
  1. Standard Search Mode  - Fetches job summaries from search results
  2. Detailed Data Mode    - Fetches full job details (search + details API)
  3. Direct Fetch Mode     - Fetches specific jobs by Job ID (no search needed)
"""

import json
import time
import random
import argparse
import sys
from datetime import datetime
from typing import Optional
import requests

from config import (
    SEARCH_API_URL,
    JOB_DETAIL_API_URL,
    SEARCH_HEADERS,
    DETAIL_HEADERS,
    DEFAULT_MAX_JOBS,
    RESULTS_PER_PAGE,
    REQUEST_DELAY_MIN,
    REQUEST_DELAY_MAX,
)
from session import setup_naukri_session
from filters import build_search_params
from utils import (
    save_to_json,
    save_to_csv,
    flatten_job_for_csv,
    print_progress,
    log,
)
from scoring import get_job_relevancy_score


class NaukriScraper:
    def __init__(self):
        # Automatically spins up Playwright to bypass WAF and generate session tokens
        self.session, captured_headers = setup_naukri_session()
        self.nkparam = captured_headers.get("nkparam", "")
        
        # Merge dynamic session token into our base headers
        self.search_headers = dict(SEARCH_HEADERS)
        self.detail_headers = dict(DETAIL_HEADERS)
        if self.nkparam:
            self.search_headers["nkparam"] = self.nkparam
            self.detail_headers["nkparam"] = self.nkparam

    # ─────────────────────────────── CORE FETCHERS ────────────────────────────────

    def fetch_search_page(self, keyword: str, page: int, filters: dict) -> Optional[dict]:
        """Fetch one page of search results from Naukri's internal API."""
        params = build_search_params(keyword=keyword, page=page, filters=filters)
        try:
            resp = self.session.get(
                SEARCH_API_URL,
                headers=self.search_headers,
                params=params,
                timeout=30,
            )
            if resp.status_code != 200:
                log(f"[WARN] API returned HTTP {resp.status_code}")
                # Print response for debugging WAF blocks
                log(f"[WARN] {resp.text[:200]}")
                return None
            return resp.json()
        except requests.exceptions.RequestException as e:
            log(f"[WARN] Error fetching search page {page}: {e}")
            return None

    def fetch_job_details(self, job_id: str) -> Optional[dict]:
        """Fetch full job details using the job-detail API."""
        url = JOB_DETAIL_API_URL.format(jobId=job_id)
        try:
            resp = self.session.get(url, headers=self.detail_headers, timeout=30)
            if resp.status_code != 200:
                log(f"[WARN] API returned HTTP {resp.status_code} for job {job_id}")
                return None
            return resp.json()
        except requests.exceptions.RequestException as e:
            log(f"[WARN] Error fetching job {job_id}: {e}")
            return None

    # ──────────────────────────── DATA EXTRACTION ─────────────────────────────────

    def extract_search_job(self, raw: dict) -> dict:
        """Extract clean fields from a raw search-result job object."""
        salary_detail = raw.get("salaryDetail", {}) or {}
        ambition_box = raw.get("ambitionBoxData", {}) or {}

        return {
            "title": raw.get("title", ""),
            "logoPath": raw.get("logoPath", ""),
            "logoPathV3": raw.get("logoPathV3", raw.get("logoPath", "")),
            "jobId": raw.get("jobId", ""),
            "currency": raw.get("currency", "INR"),
            "footerPlaceholderLabel": raw.get("footerPlaceholderLabel", ""),
            "footerPlaceholderColor": raw.get("footerPlaceholderColor", ""),
            "companyName": raw.get("companyName", ""),
            "isSaved": raw.get("isSaved", False),
            "tagsAndSkills": raw.get("tagsAndSkills", ""),
            "companyId": raw.get("companyId", ""),
            "jdURL": raw.get("jdURL", ""),
            "ambitionBoxData": ambition_box,
            "jobDescription": raw.get("jobDescription", ""),
            "showMultipleApply": raw.get("showMultipleApply", False),
            "groupId": raw.get("groupId", ""),
            "isTopGroup": raw.get("isTopGroup", 0),
            "createdDate": raw.get("createdDate", ""),
            "mode": raw.get("mode", ""),
            "board": raw.get("board", ""),
            "salaryDetail": {
                "minimumSalary": salary_detail.get("minimumSalary", 0),
                "maximumSalary": salary_detail.get("maximumSalary", 0),
                "currency": salary_detail.get("currency", "INR"),
                "hideSalary": salary_detail.get("hideSalary", True),
                "variablePercentage": salary_detail.get("variablePercentage", 0),
            },
            "experienceText": raw.get("experienceText", ""),
            "minimumExperience": raw.get("minimumExperience", ""),
            "maximumExperience": raw.get("maximumExperience", ""),
            "applyByTime": raw.get("applyByTime", ""),
            "segmentedTemplateId": raw.get("segmentedTemplateId", ""),
            "saved": raw.get("saved", False),
            "experience": raw.get("experience", ""),
            "salary": raw.get("salary", "Not disclosed"),
            "location": raw.get("location", ""),
            "companyJobsUrl": raw.get("companyJobsUrl", ""),
            "source": "search"
        }

    def enhance_with_cv_score(self, job: dict, cv_text: Optional[str]) -> dict:
        """Adds a cvMatchScore to the job if cv_text is provided."""
        if cv_text:
            job["cvMatchScore"] = get_job_relevancy_score(cv_text, job)
        else:
            job["cvMatchScore"] = None
        return job

    def extract_detailed_job(self, search_item: dict, detail_resp: dict) -> dict:
        """Merge search-level with detail-level data into one rich record."""
        base = self.extract_search_job(search_item)
        jd = detail_resp.get("jobDetails", {}) or {}
        amb = detail_resp.get("ambitionBoxDetails", {}) or {}
        branding = detail_resp.get("jdBrandingDetails", {}) or {}

        company_detail = jd.get("companyDetail", {}) or {}
        education = jd.get("education", {}) or {}
        salary_d = jd.get("salaryDetail", {}) or {}
        key_skills = jd.get("keySkills", {}) or {}
        locations = jd.get("locations", [])

        base.update({
            "source": "detailed",
            "fullDescription": jd.get("description", ""),
            "shortDescription": jd.get("shortDescription", ""),
            "jobRole": jd.get("jobRole", ""),
            "functionalArea": jd.get("functionalArea", ""),
            "roleCategory": jd.get("roleCategory", ""),
            "industry": jd.get("industry", ""),
            "jobType": jd.get("jobType", ""),
            "employmentType": jd.get("employmentType", ""),
            "wfhLabel": jd.get("wfhLabel", ""),
            "wfhType": jd.get("wfhType", ""),
            "walkIn": jd.get("walkIn", False),
            "vacancy": jd.get("vacancy", 0),
            "applyCount": jd.get("applyCount", 0),
            "viewCount": jd.get("viewCount", 0),
            "createdDate": jd.get("createdDate", base.get("createdDate", "")),
            "staticUrl": jd.get("staticUrl", base.get("jdURL", "")),
            "locations": locations,
            "keySkills": {
                "other": key_skills.get("other", []),
                "preferred": key_skills.get("preferred", []),
            },
            "education": {
                "ug": education.get("ug", []),
                "pg": education.get("pg", []),
                "ppg": education.get("ppg", []),
            },
            "salaryDetail": {
                "minimumSalary": salary_d.get("minimumSalary", 0),
                "maximumSalary": salary_d.get("maximumSalary", 0),
                "currency": salary_d.get("currency", "INR"),
                "hideSalary": salary_d.get("hideSalary", True),
                "label": salary_d.get("label", "Not Disclosed"),
                "variablePercentage": salary_d.get("variablePercentage", 0),
            },
            "companyProfile": {
                "name": company_detail.get("name", ""),
                "about": company_detail.get("details", ""),
                "address": company_detail.get("address", ""),
                "website": company_detail.get("websiteUrl", ""),
            },
            "ambitionBoxDetails": {
                "companyInfo": amb.get("companyInfo", {}),
                "reviews": amb.get("reviews", []),
                "salaries": amb.get("salaries", {}),
                "benefits": amb.get("benefits", {}),
            },
            "brandingDetails": {
                "overallRating": branding.get("overallRating"),
                "followCount": branding.get("followCount"),
                "tags": branding.get("tags", []),
                "overallReviewCount": branding.get("overallReviewCount"),
            },
        })
        return base

    # ─────────────────────────────── SCRAPE MODES ─────────────────────────────────

    def run_search_mode(self, keyword: str, max_jobs: int, filters: dict, cv_text: Optional[str] = None) -> list[dict]:
        log(f"[INFO] Starting STANDARD SEARCH mode | keyword='{keyword}' | max={max_jobs}")
        jobs = []
        page = 1

        while len(jobs) < max_jobs:
            log(f"[INFO] Fetching page {page} ...")
            data = self.fetch_search_page(keyword, page, filters)

            if not data:
                log("[WARN] Empty response. Stopping.")
                break

            raw_jobs = data.get("jobDetails", [])
            if not raw_jobs:
                log("[INFO] No more jobs found. Stopping.")
                break

            total_available = data.get("noOfJobs", 0)
            log(f"[INFO] Total jobs available on Naukri: {total_available}")

            for raw in raw_jobs:
                if len(jobs) >= max_jobs: break
                
                # Extract and score
                job = self.extract_search_job(raw)
                job = self.enhance_with_cv_score(job, cv_text)
                jobs.append(job)

            print_progress(len(jobs), max_jobs, total_available)

            if len(raw_jobs) < RESULTS_PER_PAGE:
                log("[INFO] Reached last page.")
                break

            page += 1
            time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))

        log(f"[DONE] Collected {len(jobs)} job summaries.")
        return jobs

    def run_detailed_mode(self, keyword: str, max_jobs: int, filters: dict, cv_text: Optional[str] = None) -> list[dict]:
        log(f"[INFO] Starting DETAILED mode | keyword='{keyword}' | max={max_jobs}")
        search_results = self.run_search_mode(keyword, max_jobs, filters, cv_text=None)
        jobs = []

        for i, item in enumerate(search_results):
            job_id = item.get("jobId", "")
            log(f"[INFO] Fetching details for job {i+1}/{len(search_results)}: {job_id}")
            detail = self.fetch_job_details(job_id)

            if detail:
                detailed_job = self.extract_detailed_job(item, detail)
                jobs.append(self.enhance_with_cv_score(detailed_job, cv_text))
            else:
                log(f"[WARN] Could not fetch details for {job_id}. Using search data.")
                jobs.append(self.enhance_with_cv_score(item, cv_text))

            print_progress(i + 1, len(search_results), len(search_results))
            time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))

        log(f"[DONE] Fetched detailed data for {len(jobs)} jobs.")
        return jobs

    def run_direct_fetch_mode(self, job_ids: list[str]) -> list[dict]:
        log(f"[INFO] Starting DIRECT FETCH mode | {len(job_ids)} job IDs")
        jobs = []

        for i, job_id in enumerate(job_ids):
            log(f"[INFO] Fetching job {i+1}/{len(job_ids)}: {job_id}")
            detail = self.fetch_job_details(job_id)

            if detail:
                jd = detail.get("jobDetails", {}) or {}
                base_item = {
                    "jobId": job_id,
                    "title": jd.get("title", ""),
                    "companyName": (jd.get("companyDetail") or {}).get("name", ""),
                    "companyId": jd.get("companyId", ""),
                    "groupId": jd.get("groupId", ""),
                    "jdURL": jd.get("staticUrl", ""),
                    "experience": jd.get("experienceText", ""),
                    "salary": (jd.get("salaryDetail") or {}).get("label", "Not disclosed"),
                    "location": ", ".join(loc.get("label", "") for loc in (jd.get("locations") or [])),
                    "tagsAndSkills": "",
                    "createdDate": jd.get("createdDate", ""),
                    "ambitionBoxData": {},
                    "jobDescription": jd.get("description", ""),
                }
                jobs.append(self.extract_detailed_job(base_item, detail))
            else:
                log(f"[WARN] Could not fetch job {job_id}.")

            print_progress(i + 1, len(job_ids), len(job_ids))
            time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))

        log(f"[DONE] Fetched {len(jobs)} jobs via direct fetch.")
        return jobs


# ─────────────────────────────────── MAIN ─────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Naukri.com Job Scraper - Mirror of the Apify actor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    # Core params
    parser.add_argument("--keyword", "-k", type=str, help="Search keyword")
    parser.add_argument("--max-jobs", "-n", type=int, default=DEFAULT_MAX_JOBS, help=f"Max jobs to scrape (default: {DEFAULT_MAX_JOBS})")
    parser.add_argument("--job-ids", nargs="+", metavar="ID", help="Specific Job IDs to fetch directly")
    parser.add_argument("--fetch-details", action="store_true", help="Fetch full job details for each search result (slower)")

    # Filters
    parser.add_argument("--freshness", choices=["all", "30", "15", "7", "3", "1"], help="Posting date filter (days)")
    parser.add_argument("--sort-by", choices=["relevance", "date"], default="relevance", help="Sort order")
    parser.add_argument("--work-mode", nargs="+", choices=["office", "temporary_wfh", "remote", "hybrid"], help="Work mode filter")
    parser.add_argument("--experience", type=str, help="Years of experience (e.g. '5')")
    parser.add_argument("--salary-range", nargs="+", metavar="RANGE", help="Salary ranges e.g. '10to15' '15to25'")
    parser.add_argument("--cities", nargs="+", metavar="ID", help="City IDs")
    parser.add_argument("--department", nargs="+", metavar="ID", help="Department IDs")
    parser.add_argument("--company-type", nargs="+", metavar="TYPE", help="Company types e.g. 'Foreign MNC' 'Startup'")
    parser.add_argument("--role-category", nargs="+", metavar="ID", help="Role category IDs")
    parser.add_argument("--industry", nargs="+", metavar="ID", help="Industry IDs")
    parser.add_argument("--posted-by", nargs="+", metavar="ID", help="Who posted: '1' = Company, '2' = Consultant")
    parser.add_argument("--top-companies", nargs="+", metavar="ID", help="Top company IDs")
    parser.add_argument("--ug-course", nargs="+", metavar="ID", help="UG course IDs")
    parser.add_argument("--pg-course", nargs="+", metavar="ID", help="PG course IDs")
    parser.add_argument("--stipend", nargs="+", metavar="RANGE", help="Internship stipend range")
    parser.add_argument("--duration", nargs="+", metavar="MONTHS", help="Internship duration in months")

    # Output
    parser.add_argument("--output", "-o", type=str, default="naukri_jobs", help="Output filename (without extension)")
    parser.add_argument("--output-format", choices=["json", "csv", "both"], default="json", help="Output format (default: json)")
    return parser.parse_args()


# Provide global aliases for run.py which previously imported these directly
run_search_mode = None
run_detailed_mode = None
run_direct_fetch_mode = None

# We use a lazy instantiator for run.py so we don't spin up Playwright on import
_scraper_instance = None
def _get_scraper():
    global _scraper_instance
    if not _scraper_instance:
        _scraper_instance = NaukriScraper()
    return _scraper_instance

def global_run_search_mode(keyword, max_jobs, filters):
    return _get_scraper().run_search_mode(keyword, max_jobs, filters)
run_search_mode = global_run_search_mode

def global_run_detailed_mode(keyword, max_jobs, filters):
    return _get_scraper().run_detailed_mode(keyword, max_jobs, filters)
run_detailed_mode = global_run_detailed_mode

def global_run_direct_fetch_mode(job_ids):
    return _get_scraper().run_direct_fetch_mode(job_ids)
run_direct_fetch_mode = global_run_direct_fetch_mode


def main():
    args = parse_args()

    if not args.job_ids and not args.keyword:
        print("[ERROR] Provide --keyword or --job-ids. Use --help for usage.")
        sys.exit(1)

    filters = {
        "freshness": args.freshness,
        "sortBy": args.sort_by,
        "workMode": args.work_mode,
        "experience": args.experience,
        "salaryRange": args.salary_range,
        "cities": args.cities,
        "department": args.department,
        "companyType": args.company_type,
        "roleCategory": args.role_category,
        "industry": args.industry,
        "postedBy": args.posted_by,
        "topCompanies": args.top_companies,
        "ugCourse": args.ug_course,
        "pgCourse": args.pg_course,
        "stipend": args.stipend,
        "duration": args.duration,
    }

    start = datetime.now()
    scraper = NaukriScraper()

    if args.job_ids:
        jobs = scraper.run_direct_fetch_mode(args.job_ids)
    elif args.fetch_details:
        jobs = scraper.run_detailed_mode(args.keyword, args.max_jobs, filters)
    else:
        jobs = scraper.run_search_mode(args.keyword, args.max_jobs, filters)

    elapsed = (datetime.now() - start).total_seconds()
    log(f"\n[SUMMARY] Scraped {len(jobs)} jobs in {elapsed:.1f}s")

    if not jobs:
        log("[WARN] No jobs collected. Exiting.")
        sys.exit(0)

    fmt = args.output_format
    if fmt in ("json", "both"):
        path = save_to_json(jobs, args.output)
        log(f"[SAVED] JSON -> {path}")
    if fmt in ("csv", "both"):
        flat = [flatten_job_for_csv(j) for j in jobs]
        path = save_to_csv(flat, args.output)
        log(f"[SAVED] CSV  -> {path}")


if __name__ == "__main__":
    main()
