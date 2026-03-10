"""
run.py
======
Alternative entry-point that reads from input.json instead of command-line args.
Mirrors the Apify actor input-schema pattern.

Usage:
  python run.py                          # uses input.json
  python run.py --input my_config.json   # uses a custom config
"""

import json
import sys
import argparse
from datetime import datetime
from scraper import (
    run_search_mode,
    run_detailed_mode,
    run_direct_fetch_mode,
)
from utils import save_to_json, save_to_csv, flatten_job_for_csv, log


def load_input(path="input.json") -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"[ERROR] Input file '{path}' not found.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"[ERROR] Invalid JSON in '{path}': {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Naukri Scraper - JSON config runner")
    parser.add_argument("--input", "-i", default="input.json", help="Path to input JSON config")
    args = parser.parse_args()

    cfg = load_input(args.input)

    keyword = cfg.get("keyword", "")
    max_jobs = cfg.get("maxJobs", 100)
    job_ids = cfg.get("jobIds", [])
    fetch_details = cfg.get("fetchDetails", False)
    output_name = cfg.get("output", "naukri_jobs")
    output_format = cfg.get("outputFormat", "json").lower()

    filters = {
        "freshness": cfg.get("freshness"),
        "sortBy": cfg.get("sortBy", "relevance"),
        "workMode": cfg.get("workMode"),
        "experience": cfg.get("experience"),
        "salaryRange": cfg.get("salaryRange"),
        "cities": cfg.get("cities"),
        "department": cfg.get("department"),
        "companyType": cfg.get("companyType"),
        "roleCategory": cfg.get("roleCategory"),
        "industry": cfg.get("industry"),
        "postedBy": cfg.get("postedBy"),
        "topCompanies": cfg.get("topCompanies"),
        "ugCourse": cfg.get("ugCourse"),
        "pgCourse": cfg.get("pgCourse"),
        "stipend": cfg.get("stipend"),
        "duration": cfg.get("duration"),
    }

    # Validate
    if not job_ids and not keyword:
        print("[ERROR] Provide 'keyword' or 'jobIds' in input.json")
        sys.exit(1)

    start = datetime.now()

    # Choose mode — matches Apify actor logic
    if job_ids:
        log(f"[INFO] Mode: Direct Fetch ({len(job_ids)} job IDs)")
        jobs = run_direct_fetch_mode(job_ids)
    elif fetch_details:
        log(f"[INFO] Mode: Detailed Search | keyword='{keyword}' | max={max_jobs}")
        jobs = run_detailed_mode(keyword, max_jobs, filters)
    else:
        log(f"[INFO] Mode: Standard Search | keyword='{keyword}' | max={max_jobs}")
        jobs = run_search_mode(keyword, max_jobs, filters)

    elapsed = (datetime.now() - start).total_seconds()
    log(f"\n[SUMMARY] Scraped {len(jobs)} jobs in {elapsed:.1f}s")

    if not jobs:
        log("[WARN] No jobs collected.")
        sys.exit(0)

    if output_format in ("json", "both"):
        path = save_to_json(jobs, output_name)
        log(f"[SAVED] JSON → {path}")

    if output_format in ("csv", "both"):
        flat = [flatten_job_for_csv(j) for j in jobs]
        path = save_to_csv(flat, output_name)
        log(f"[SAVED] CSV  → {path}")


if __name__ == "__main__":
    main()
