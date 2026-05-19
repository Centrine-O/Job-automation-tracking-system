import hashlib
import requests
from datetime import datetime, timezone, timedelta
from app.tracking.db import insert_job

API_URL = "https://jobicy.com/api/v2/remote-jobs"
_CUTOFF = timedelta(hours=24)

# Each entry is (industry, tag). Tag can be None.
SEARCH_QUERIES = [
    ("engineering", None),
    ("engineering", "python"),
    ("engineering", "machine learning"),
    ("engineering", "automation"),
    ("engineering", "llm"),
    ("engineering", "data"),
]

RELEVANT_KEYWORDS = [
    "python", "data analyst", "data engineer", "software engineer",
    "software developer", "automation", "ai", "machine learning",
    "backend", "full stack", "fullstack", "api", "sql",
    "ai engineer", "artificial intelligence", "agentic", "agent",
    "llm", "large language model", "prompt engineer", "generative ai",
    "gen ai", "genai", "langchain", "langgraph", "openai", "anthropic",
    "mlops", "ai ops", "rpa", "workflow automation", "n8n",
]


def make_hash(title, company, url):
    raw = f"{title.lower().strip()}{company.lower().strip()}{url.strip()}"
    return hashlib.sha256(raw.encode()).hexdigest()


def is_recent(pub_date_str):
    if not pub_date_str:
        return True
    try:
        pub = datetime.fromisoformat(pub_date_str)
        if pub.tzinfo is None:
            pub = pub.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - pub <= _CUTOFF
    except Exception:
        return True


def is_relevant(title, description):
    searchable = (title + " " + description).lower()
    return any(kw in searchable for kw in RELEVANT_KEYWORDS)


def run():
    """Fetch remote jobs from Jobicy API and save to DB."""
    print("Starting Jobicy scraper...")
    total_new = 0
    total_dupes = 0
    total_skipped = 0
    seen_ids = set()

    for industry, tag in SEARCH_QUERIES:
        label = f"{industry}" + (f" / {tag}" if tag else "")
        print(f"  Searching: {label}")
        params = {"count": 50, "industry": industry}
        if tag:
            params["tag"] = tag
        try:
            resp = requests.get(API_URL, params=params, timeout=15)
            resp.raise_for_status()
            jobs_raw = resp.json().get("jobs", [])
            print(f"  Found {len(jobs_raw)} results")
        except Exception as e:
            print(f"  Error fetching '{label}': {e}")
            continue

        for job in jobs_raw:
            job_id_raw = job.get("id")
            if job_id_raw in seen_ids:
                continue
            seen_ids.add(job_id_raw)

            if not is_recent(job.get("pubDate")):
                total_skipped += 1
                continue

            title = (job.get("jobTitle") or "").strip()
            company = (job.get("companyName") or "").strip()
            url = (job.get("url") or "").strip()
            description = (job.get("jobDescription") or "").strip()
            location = (job.get("jobGeo") or "Remote").strip()

            if not title or not company or not url:
                total_skipped += 1
                continue

            if not is_relevant(title, description):
                total_skipped += 1
                continue

            jd_hash = make_hash(title, company, url)

            saved_id = insert_job(
                source="jobicy",
                title=title,
                company=company,
                location=location,
                remote_type="remote",
                apply_method="form",
                apply_url=url,
                jd_url=url,
                jd_text=description,
                jd_hash=jd_hash,
            )

            if saved_id:
                print(f"    + Saved: {title} @ {company}")
                total_new += 1
            else:
                total_dupes += 1

    print(
        f"\nJobicy done: {total_new} new, "
        f"{total_dupes} duplicates skipped, "
        f"{total_skipped} skipped"
    )
    return total_new


if __name__ == "__main__":
    run()
