import hashlib
import requests
from app.tracking.db import insert_job
from app.config import settings

SERPAPI_URL = "https://serpapi.com/search"

SEARCH_QUERIES = [
    "software engineer Kenya",
    "data analyst Nairobi",
    "python developer Kenya",
    "data engineer remote Kenya",
    "backend engineer Kenya",
    "full stack developer Nairobi",
    "AI engineer Kenya",
    "AI developer Nairobi",
    "automation engineer Kenya",
    "prompt engineer remote",
    "LLM engineer remote",
    "agentic AI developer remote",
    "machine learning engineer Kenya",
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


def is_recent(posted_at):
    """Return True if SerpAPI relative date string is within 24 hours."""
    if not posted_at:
        return True
    s = posted_at.lower().strip()
    if any(x in s for x in ["just now", "minute", "hour", "today", "active"]):
        return True
    if s == "1 day ago":
        return True
    return False


def make_hash(title, company, url):
    raw = f"{title.lower().strip()}{company.lower().strip()}{url.strip()}"
    return hashlib.sha256(raw.encode()).hexdigest()


def is_relevant(title, description):
    searchable = (title + " " + description).lower()
    return any(kw in searchable for kw in RELEVANT_KEYWORDS)


def run():
    """Fetch LinkedIn jobs via SerpAPI and save to DB."""
    if not settings.serpapi_key:
        print("SerpAPI key not set — skipping LinkedIn scraper.")
        return 0

    print("Starting LinkedIn scraper (SerpAPI)...")
    total_new = 0
    total_dupes = 0
    total_skipped = 0

    for query in SEARCH_QUERIES:
        print(f"  Searching: {query}")
        try:
            resp = requests.get(
                SERPAPI_URL,
                params={
                    "engine": "linkedin_jobs",
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
            posted_at = (job.get("detected_extensions") or {}).get("posted_at", "")
            if not is_recent(posted_at):
                total_skipped += 1
                continue

            title = (job.get("title") or "").strip()
            company = (job.get("company_name") or "").strip()
            location = (job.get("location") or "Kenya").strip()
            description = (job.get("description") or "").strip()

            apply_options = job.get("apply_options", [])
            apply_link = apply_options[0].get("link") if apply_options else None
            if apply_link:
                job_url = apply_link
            elif job.get("job_id"):
                job_url = f"https://www.linkedin.com/jobs/view/{job['job_id']}"
            else:
                print(f"    Skipping '{title}' — no apply link or job ID")
                total_skipped += 1
                continue

            if not is_relevant(title, description):
                total_skipped += 1
                continue

            jd_hash = make_hash(title, company, job_url)

            job_id = insert_job(
                source="linkedin",
                title=title,
                company=company,
                location=location,
                remote_type="remote" if "remote" in location.lower() else "onsite",
                apply_method="form",
                apply_url=job_url,
                jd_url=job_url,
                jd_text=description,
                jd_hash=jd_hash,
            )

            if job_id:
                print(f"    + Saved: {title} @ {company}")
                total_new += 1
            else:
                total_dupes += 1

    print(f"\nLinkedIn done: {total_new} new, {total_dupes} dupes, {total_skipped} irrelevant")
    return total_new


if __name__ == "__main__":
    run()
