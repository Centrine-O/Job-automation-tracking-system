import hashlib
import requests
from app.tracking.db import insert_job
from app.config import settings

SERPAPI_URL = "https://serpapi.com/search"

# Queries targeting Nairobi/Kenya jobs + global remote
SEARCH_QUERIES = [
    "data analyst jobs in Nairobi Kenya",
    "software engineer jobs in Nairobi Kenya",
    "software developer jobs in Nairobi Kenya",
    "python developer jobs in Nairobi Kenya",
    "data engineer jobs in Nairobi Kenya",
    "remote data analyst jobs Kenya",
    "remote software engineer Kenya",
    "AI engineer jobs Nairobi Kenya",
    "automation engineer jobs Kenya",
    "machine learning engineer Kenya",
    "prompt engineer remote",
    "LLM engineer remote",
    "agentic AI developer remote",
    "AI automation developer remote",
]


def make_hash(title, company, url):
    raw = f"{title.lower().strip()}{company.lower().strip()}{url.strip()}"
    return hashlib.sha256(raw.encode()).hexdigest()


def detect_apply_method(apply_link):
    if not apply_link:
        return "unknown", None
    if apply_link.startswith("mailto:"):
        return "email", apply_link
    if "@" in apply_link and not apply_link.startswith("http"):
        return "email", f"mailto:{apply_link}"
    return "form", apply_link


def run():
    """Fetch jobs from Google Jobs via SerpAPI and save to DB."""
    if not settings.serpapi_key:
        print("SerpAPI key not set — skipping Google Jobs scraper.")
        return 0

    print("Starting Google Jobs scraper (SerpAPI)...")
    total_new = 0
    total_dupes = 0
    total_skipped = 0

    for query in SEARCH_QUERIES:
        print(f"  Searching: {query}")
        try:
            resp = requests.get(
                SERPAPI_URL,
                params={
                    "engine": "google_jobs",
                    "q": query,
                    "api_key": settings.serpapi_key,
                    "num": 10,
                },
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()

            jobs_raw = data.get("jobs_results", [])
            print(f"  Found {len(jobs_raw)} results")

        except Exception as e:
            print(f"  Error fetching '{query}': {e}")
            continue

        for job in jobs_raw:
            title = (job.get("title") or "").strip()
            company = (job.get("company_name") or "").strip()
            location = (job.get("location") or "Kenya").strip()
            description = (job.get("description") or "").strip()

            # SerpAPI nests apply options in apply_options list
            apply_options = job.get("apply_options", [])
            apply_link = apply_options[0].get("link") if apply_options else None

            # Use job_id as URL fallback for hashing uniqueness
            job_id_raw = job.get("job_id", "")
            url = apply_link or f"https://www.google.com/search?q={job_id_raw}"

            if not title or not company:
                total_skipped += 1
                continue

            apply_method, apply_url = detect_apply_method(apply_link)
            jd_hash = make_hash(title, company, url)

            loc_lower = location.lower()
            if "remote" in loc_lower:
                remote_type = "remote"
            elif "hybrid" in loc_lower:
                remote_type = "hybrid"
            else:
                remote_type = "onsite"

            saved_id = insert_job(
                source="google_jobs",
                title=title,
                company=company,
                location=location,
                remote_type=remote_type,
                apply_method=apply_method,
                apply_url=apply_url,
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
        f"\nGoogle Jobs done: {total_new} new, "
        f"{total_dupes} duplicates skipped, "
        f"{total_skipped} skipped (missing data)"
    )
    return total_new


if __name__ == "__main__":
    run()
