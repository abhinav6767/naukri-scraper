# Naukri Job Scraper 🔍

A production-ready Python scraper for **Naukri.com** that mirrors the functionality of the popular Apify actor. Built using Naukri's internal REST APIs (reverse-engineered from browser network traffic).

---

## Features

- 🔍 **3 Operating Modes**: Standard Search, Detailed Fetch, Direct Job ID Fetch
- ⚡ **Advanced Filters**: Freshness, Work Mode, Experience, Salary, City, Department, Company Type, Role Category, Industry
- 📄 **Smart Pagination**: Automatically traverses multiple pages
- 📊 **Dual Output**: JSON and/or CSV formats
- 🧪 **No Browser / Selenium needed**: Pure `requests` — hits Naukri's internal JSON API directly
- 🐌 **Polite Rate Limiting**: Random delays to avoid blocking

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Run using command-line (recommended)

```bash
# Standard search – fast, summaries only
python scraper.py --keyword "software developer" --max-jobs 100

# Detailed mode – full descriptions, skills, company info, AmbitionBox
python scraper.py --keyword "data analyst" --max-jobs 50 --fetch-details

# Direct fetch – specific job IDs, no search
python scraper.py --job-ids 220126040161 170424007054
```

### 3. Run using input.json (Apify-style)

Edit `input.json` then run:

```bash
python run.py
```

---

## Operating Modes

### 1. Standard Search Mode (Fast)
- **Trigger**: Provide `--keyword`, no `--fetch-details`
- **What you get**: Title, Company, Location, Salary, Experience, URL, Skills, AmbitionBox summary
- **Use case**: Market trend analysis, salary aggregation, building job URL lists

### 2. Detailed Data Mode (Rich)
- **Trigger**: Provide `--keyword` **+** `--fetch-details`
- **What you get**: Everything above + Full HTML description, Key skills, Education requirements, Company profile, AmbitionBox reviews & salaries & benefits
- **Use case**: Full content archiving, skills extraction, company analysis

### 3. Direct Fetch Mode (Targeted)
- **Trigger**: Provide `--job-ids`
- **What you get**: Full detail data for each specified job ID
- **Use case**: Efficient targeted data collection for known job IDs

---

## All Command-Line Options

```
usage: scraper.py [-h] [--keyword KEYWORD] [--max-jobs N] [--job-ids ID [ID ...]]
                  [--fetch-details] [--freshness {all,30,15,7,3,1}]
                  [--sort-by {relevance,date}]
                  [--work-mode {office,temporary_wfh,remote,hybrid} [...]]
                  [--experience EXP] [--salary-range RANGE [RANGE ...]]
                  [--cities ID [ID ...]] [--department ID [ID ...]]
                  [--company-type TYPE [TYPE ...]] [--role-category ID [ID ...]]
                  [--industry ID [ID ...]] [--posted-by ID [ID ...]]
                  [--output OUTPUT] [--output-format {json,csv,both}]
```

### Filter Examples

```bash
# Remote Python developer jobs posted in last 7 days, salary ₹10-25L
python scraper.py \
  --keyword "python developer" \
  --max-jobs 200 \
  --freshness 7 \
  --work-mode remote hybrid \
  --experience 3 \
  --salary-range 10to15 15to25 \
  --sort-by date \
  --output-format both \
  --output python_jobs

# Jobs in Bangalore and Hyderabad
python scraper.py --keyword "data scientist" --cities 17 97

# Company posted jobs only (not consultants)
python scraper.py --keyword "java developer" --posted-by 1
```

---

## Input JSON Schema (for `run.py`)

```json
{
  "keyword": "software developer",
  "maxJobs": 100,
  "fetchDetails": false,
  "jobIds": [],
  "freshness": "7",
  "sortBy": "relevance",
  "workMode": ["remote", "hybrid"],
  "experience": "5",
  "salaryRange": ["10to15", "15to25"],
  "cities": ["17", "97"],
  "department": [],
  "companyType": [],
  "roleCategory": [],
  "industry": [],
  "postedBy": [],
  "output": "naukri_jobs",
  "outputFormat": "json"
}
```

---

## Output Fields

### Standard Search Output
| Field | Description |
|-------|-------------|
| `jobId` | Naukri Job ID |
| `title` | Job title |
| `companyName` | Company name |
| `experience` | Experience required |
| `salary` | Salary display text |
| `salaryDetail` | Min/max salary in INR |
| `location` | Job location |
| `tagsAndSkills` | Skills (comma-separated) |
| `createdDate` | When the job was posted |
| `jdURL` | Direct link to job posting |
| `ambitionBoxData` | Company rating & review count |
| `jobDescription` | Job description (HTML) |

### Additional Fields in Detailed Mode
| Field | Description |
|-------|-------------|
| `fullDescription` | Complete HTML job description |
| `keySkills` | Structured skills list (preferred / other) |
| `education` | UG/PG requirements |
| `functionalArea` | Functional area category |
| `roleCategory` | Role category |
| `industry` | Industry type |
| `employmentType` | Full Time / Contract etc. |
| `wfhLabel` | Remote / Hybrid / Office |
| `companyProfile` | Company about, address, website |
| `ambitionBoxDetails` | Reviews, salaries, benefits (full) |
| `brandingDetails` | Company ratings, tags, follower count |

---

## Common City IDs

| City | ID |
|------|----|
| Mumbai | 17 |
| Bangalore | 11 |
| Delhi / NCR | 9 |
| Hyderabad | 97 |
| Chennai | 21 |
| Pune | 63 |
| Kolkata | 10 |
| Ahmedabad | 3 |
| Remote | - |

---

## File Structure

```
naukri_scraper/
├── scraper.py        # Main scraper (all 3 modes)
├── run.py            # JSON-config entry point (Apify-style)
├── config.py         # API endpoints & headers
├── filters.py        # Query parameter builder
├── utils.py          # Logging, progress, file output
├── input.json        # Example input config
├── requirements.txt  # Dependencies
└── README.md         # This file
```

---

## Notes

- **No authentication required** — uses Naukri's public-facing internal API
- **Rate limiting**: Built-in random delays (0.8–2.5s) between requests
- **Pagination**: Automatically handles multiple pages (20 jobs/page)
- **Encoding**: UTF-8 output with proper Hindi/regional character support

---

## Legal

This tool is for **educational and research purposes only**. Use responsibly and respect Naukri's Terms of Service. Do not use for commercial purposes without permission.
