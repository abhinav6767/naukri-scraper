"""
filters.py
==========
Builds the query-parameter dictionary for Naukri's search API.
Maps user-friendly filter names to Naukri's actual query parameter names.
"""

# Mapping: work-mode label → Naukri's internal ID
WORK_MODE_MAP = {
    "office": "1",
    "temporary_wfh": "2",
    "remote": "3",
    "hybrid": "4",
}

SORT_MAP = {
    "relevance": "r",
    "date": "d",
}


def build_search_params(keyword: str, page: int, filters: dict) -> dict:
    """
    Construct the query parameters for GET /jobapi/v3/search.

    Naukri's API parameters (reverse engineered from browser network traffic):
      keyword       → the search term
      pageNo        → page number (1-indexed)
      noOfResults   → results per page (max 20 observed)
      sort          → 'r' for relevance, 'd' for date
      src           → source identifier (keep as 'jobsearchDesk')
      k             → keyword (duplicate, some versions require this)
      experience    → years of experience as a single integer string
      freshness     → days since posting ('1','3','7','15','30')
      wfhType       → work-from-home type (comma-separated IDs)
      ctcFilter     → salary ranges (e.g. '10to15,15to25')
      lid           → location IDs (comma-separated)
      jt            → job-type / department IDs (comma-separated)
      companyType   → company type (comma-separated)
      atype         → posted-by filter
      rCatId        → role category ID
      industryId    → industry ID
      topGid        → top company group IDs (comma-separated)
      ugType        → UG qualification filter
      pgType        → PG qualification filter
      stipend       → internship stipend range
      dur           → internship duration (months)
    """
    params: dict = {
        "noOfResults": 20,
        "urlType": "search_by_keyword",
        "searchType": "adv",
        "pageNo": page,
        "src": "jobsearchDesk",
        "keyword": keyword,
        "k": keyword,
    }

    # Sort order
    sort_by = filters.get("sortBy", "relevance")
    params["sort"] = SORT_MAP.get(sort_by, "r")

    # Freshness (days)
    if filters.get("freshness") and filters["freshness"] != "all":
        params["freshness"] = filters["freshness"]

    # Work mode (comma-separated IDs)
    work_modes = filters.get("workMode") or []
    if work_modes:
        mode_ids = [WORK_MODE_MAP[m] for m in work_modes if m in WORK_MODE_MAP]
        if mode_ids:
            params["wfhType"] = mode_ids

    # Experience (years)
    if filters.get("experience"):
        params["experience"] = filters["experience"]

    # Salary range (e.g. "10to15,15to25")
    salary_ranges = filters.get("salaryRange") or []
    if salary_ranges:
        params["ctcFilter"] = salary_ranges

    # City IDs
    cities = filters.get("cities") or []
    if cities:
        params["lid"] = [str(c) for c in cities]

    # Department IDs
    departments = filters.get("department") or []
    if departments:
        params["jt"] = [str(d) for d in departments]

    # Company type
    company_types = filters.get("companyType") or []
    if company_types:
        params["companyType"] = company_types

    # Role category
    role_cats = filters.get("roleCategory") or []
    if role_cats:
        params["rCatId"] = [str(r) for r in role_cats]

    # Industry
    industries = filters.get("industry") or []
    if industries:
        params["industryId"] = [str(i) for i in industries]

    # Posted by
    posted_by = filters.get("postedBy") or []
    if posted_by:
        params["atype"] = [str(p) for p in posted_by]

    # Top companies
    top_companies = filters.get("topCompanies") or []
    if top_companies:
        params["topGid"] = [str(t) for t in top_companies]

    # UG course
    ug_courses = filters.get("ugCourse") or []
    if ug_courses:
        params["ugType"] = [str(u) for u in ug_courses]

    # PG course
    pg_courses = filters.get("pgCourse") or []
    if pg_courses:
        params["pgType"] = [str(p) for p in pg_courses]

    # Internship stipend
    stipend = filters.get("stipend") or []
    if stipend:
        params["stipend"] = [str(s) for s in stipend]

    # Internship duration
    duration = filters.get("duration") or []
    if duration:
        params["dur"] = [str(d) for d in duration]

    return params
