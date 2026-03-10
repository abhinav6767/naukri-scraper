"""
config.py
=========
Central configuration for the Naukri scraper.
Naukri's internal REST API endpoints and required headers — discovered via
browser network inspection.
"""

# ─────────────────────────────── ENDPOINTS ────────────────────────────────────

# Search results endpoint (returns paginated job summaries)
SEARCH_API_URL = "https://www.naukri.com/jobapi/v3/search"

# Individual job details endpoint (returns full JD, skills, company, AmbitionBox)
JOB_DETAIL_API_URL = "https://www.naukri.com/jobapi/v4/job/{jobId}"

# ──────────────────────────────── HEADERS ─────────────────────────────────────
# These headers mimic the browser's XHR request to Naukri's internal API.
# appid=109  → used for search listings
# appid=121  → used for job detail pages

_COMMON_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.naukri.com/",
    "Origin": "https://www.naukri.com",
    "systemid": "Naukri",
    "clientid": "d3skt0p",
}

SEARCH_HEADERS = {
    **_COMMON_HEADERS,
    "appid": "109",
    "gid": "LOCATION,INDUSTRY,EDUCATION,FAREA_ROLE",
}

DETAIL_HEADERS = {
    **_COMMON_HEADERS,
    "appid": "121",
}

# ─────────────────────────── SCRAPING SETTINGS ────────────────────────────────

DEFAULT_MAX_JOBS = 100
RESULTS_PER_PAGE = 20          # Naukri returns 20 results per page by default

# Polite delay between requests (seconds) to avoid rate-limiting
REQUEST_DELAY_MIN = 0.8
REQUEST_DELAY_MAX = 2.5
