"""
utils.py
========
Helper functions for output formatting, saving, and progress display.
"""

import json
import csv
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


def log(message: str) -> None:
    """Print a timestamped log message to stderr."""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {message}", file=sys.stderr)


def print_progress(current: int, target: int, total_available: int) -> None:
    """Print a simple progress bar."""
    pct = min(100, int(current / max(target, 1) * 100))
    bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
    log(f"         [{bar}] {current}/{target} jobs scraped (Naukri total: {total_available})")


def save_to_json(jobs: list[dict], filename: str) -> str:
    """Save jobs list to a pretty-printed JSON file."""
    filepath = Path(f"{filename}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)
    return str(filepath.resolve())


def _get_csv_fieldnames(jobs: list[dict]) -> list[str]:
    """Determine a consistent set of column headers for CSV output."""
    # Start with predictable key ordering
    priority_keys = [
        "jobId", "cvMatchScore", "title", "companyName", "experience", "salary",
        "location", "tagsAndSkills", "createdDate", "jdURL",
        "source", "industry", "jobType", "employmentType",
        "functionalArea", "roleCategory", "jobRole",
        "wfhLabel", "vacancy", "applyCount", "viewCount",
        "shortDescription",
    ]
    seen = set(priority_keys)
    extra = []
    for job in jobs:
        for k in job:
            if k not in seen:
                seen.add(k)
                extra.append(k)
    return priority_keys + extra


def flatten_job_for_csv(job: dict) -> dict:
    """
    Flatten nested structures into strings for CSV compatibility.
    Dicts and lists become JSON strings.
    """
    flat = {}
    for key, value in job.items():
        if isinstance(value, (dict, list)):
            flat[key] = json.dumps(value, ensure_ascii=False)
        elif value is None:
            flat[key] = ""
        else:
            flat[key] = value
    return flat


def save_to_csv(flat_jobs: list[dict], filename: str) -> str:
    """Save flattened jobs to a CSV file."""
    if not flat_jobs:
        return ""
    filepath = Path(f"{filename}.csv")
    # Collect all possible field names from all records
    fieldnames: list[str] = []
    seen: set[str] = set()
    priority = [
        "jobId", "cvMatchScore", "title", "companyName", "experience", "salary",
        "location", "tagsAndSkills", "createdDate", "jdURL",
        "source", "industry", "jobType", "employmentType",
    ]
    for k in priority:
        if k not in seen:
            fieldnames.append(k)
            seen.add(k)
    for job in flat_jobs:
        for k in job:
            if k not in seen:
                fieldnames.append(k)
                seen.add(k)

    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(flat_jobs)
    return str(filepath.resolve())
