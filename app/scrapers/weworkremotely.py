import hashlib
import xml.etree.ElementTree as ET
import requests
from app.tracking.db import insert_job

# We Work Remotely RSS feeds — one per category
RSS_FEEDS = [
    "https://weworkremotely.com/categories/remote-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-data-science-jobs.rss",
    "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss",
    "https://weworkremotely.com/categories/remote-full-stack-programming-jobs.rss",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; JobBot/1.0)"
}

RELEVANT_KEYWORDS = [
    "python", "data analyst", "data engineer", "software engineer",
    "software developer", "automation", "ai", "machine learning",
    "backend", "full stack", "fullstack", "api", "sql", "django",
    "flask", "react", "node",
    "ai engineer", "artificial intelligence", "agentic", "agent",
    "llm", "large language model", "prompt engineer", "generative ai",
    "gen ai", "genai", "langchain", "langgraph", "openai", "anthropic",
    "mlops", "ai ops", "rpa", "workflow automation", "n8n",
]


def make_hash(title, company, url):
    raw = f"{title.lower().strip()}{company.lower().strip()}{url.strip()}"
    return hashlib.sha256(raw.encode()).hexdigest()


def is_relevant(title, description):
    searchable = (title + " " + description).lower()
    return any(kw in searchable for kw in RELEVANT_KEYWORDS)


def parse_feed(feed_url):
    """Fetch and parse one RSS feed. Returns list of job dicts."""
    jobs = []
    try:
        resp = requests.get(feed_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()

        root = ET.fromstring(resp.content)
        channel = root.find("channel")
        if channel is None:
            return jobs

        for item in channel.findall("item"):
            title_el = item.find("title")
            link_el = item.find("link")
            desc_el = item.find("description")
            region_el = item.find("region")

            title_raw = title_el.text if title_el is not None else ""
            link = link_el.text if link_el is not None else ""
            description = desc_el.text if desc_el is not None else ""
            region = region_el.text if region_el is not None else "Worldwide"

            # WWR titles are formatted as "Company: Job Title"
            if ": " in title_raw:
                company, title = title_raw.split(": ", 1)
            else:
                company = "Unknown"
                title = title_raw

            title = title.strip()
            company = company.strip()

            if not title or not link:
                continue

            jobs.append({
                "title": title,
                "company": company,
                "location": region.strip() if region else "Worldwide",
                "url": link.strip(),
                "description": description,
            })

    except Exception as e:
        print(f"  Error parsing feed {feed_url}: {e}")

    return jobs


def run():
    """Fetch all WWR RSS feeds and save relevant jobs to DB."""
    print("Starting We Work Remotely scraper...")
    total_new = 0
    total_dupes = 0
    total_skipped = 0

    for feed_url in RSS_FEEDS:
        print(f"  Fetching: {feed_url}")
        jobs = parse_feed(feed_url)
        print(f"  Found {len(jobs)} jobs")

        for job in jobs:
            if not is_relevant(job["title"], job["description"]):
                total_skipped += 1
                continue

            jd_hash = make_hash(job["title"], job["company"], job["url"])

            job_id = insert_job(
                source="weworkremotely",
                title=job["title"],
                company=job["company"],
                location=job["location"],
                remote_type="remote",
                apply_method="form",
                apply_url=job["url"],
                jd_url=job["url"],
                jd_text=job["description"],
                jd_hash=jd_hash,
            )

            if job_id:
                print(f"    + Saved: {job['title']} @ {job['company']}")
                total_new += 1
            else:
                total_dupes += 1

    print(
        f"\nWe Work Remotely done: {total_new} new, "
        f"{total_dupes} duplicates skipped, "
        f"{total_skipped} irrelevant skipped"
    )
    return total_new


if __name__ == "__main__":
    run()
