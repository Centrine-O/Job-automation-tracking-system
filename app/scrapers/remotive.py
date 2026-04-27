import hashlib
import requests
from app.tracking.db import insert_job

API_URL = "https://remotive.com/api/remote-jobs"

# Categories relevant to your target roles
CATEGORIES = [
    "software-dev",
    "data",
    "devops-sysadmin",
]

# Keywords to filter for relevant jobs
RELEVANT_KEYWORDS = [
    "python", "data analyst", "data engineer", "software engineer",
    "software developer", "automation", "ai", "machine learning",
    "backend", "full stack", "fullstack", "api", "sql",
]


def make_hash(title, company, url):
    raw = f"{title.lower().strip()}{company.lower().strip()}{url.strip()}"
    return hashlib.sha256(raw.encode()).hexdigest()


def is_relevant(job):
    """Return True if the job matches our target roles."""
    searchable = (
        job.get("title", "") + " " + " ".join(job.get("tags", []))
    ).lower()
    return any(kw in searchable for kw in RELEVANT_KEYWORDS)


def run():
    """Fetch jobs from Remotive API and save to DB."""
    print("Starting Remotive scraper...")
    total_new = 0
    total_dupes = 0
    total_skipped = 0

    for category in CATEGORIES:
        print(f"  Fetching category: {category}")
        try:
            resp = requests.get(
                API_URL,
                params={"category": category},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            jobs = data.get("jobs", [])
            print(f"  Found {len(jobs)} jobs")

        except Exception as e:
            print(f"  Error fetching {category}: {e}")
            continue

        for job in jobs:
            if not is_relevant(job):
                total_skipped += 1
                continue

            title = job.get("title", "").strip()
            company = job.get("company_name", "").strip()
            job_url = job.get("url", "").strip()
            jd_text = job.get("description", "").strip()
            location = job.get("candidate_required_location") or "Remote"
            tags = job.get("tags", [])

            if not title or not company or not job_url:
                continue

            jd_hash = make_hash(title, company, job_url)

            job_id = insert_job(
                source="remotive",
                title=title,
                company=company,
                location=location,
                remote_type="remote",
                apply_method="form",
                apply_url=job_url,
                jd_url=job_url,
                jd_text=jd_text,
                jd_hash=jd_hash,
            )

            if job_id:
                print(f"    + Saved: {title} @ {company}")
                total_new += 1
            else:
                total_dupes += 1

    print(
        f"\nRemotive done: {total_new} new, "
        f"{total_dupes} duplicates skipped, "
        f"{total_skipped} irrelevant skipped"
    )
    return total_new


if __name__ == "__main__":
    run()
