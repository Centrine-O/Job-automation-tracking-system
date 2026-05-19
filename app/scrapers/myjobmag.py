import hashlib
import time
import random
import requests
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup
from app.tracking.db import insert_job

_CUTOFF = timedelta(hours=24)

BASE_URL = "https://www.myjobmag.co.ke"
LISTINGS_URL = f"{BASE_URL}/jobs-in-kenya"

RELEVANT_KEYWORDS = [
    "python", "data analyst", "data engineer", "software engineer",
    "software developer", "automation", "ai", "machine learning",
    "backend", "full stack", "fullstack", "api", "sql", "developer",
    "ai engineer", "artificial intelligence", "agentic", "agent",
    "llm", "large language model", "prompt engineer", "generative ai",
    "gen ai", "genai", "langchain", "langgraph", "openai", "anthropic",
    "mlops", "ai ops", "rpa", "workflow automation", "n8n",
]

PAGES = 3


def is_recent(item):
    """
    Try to read a posting date from the listing element.
    Returns True if within 24 hours, or if no date is found (fail-open).
    """
    # <time datetime="2026-05-19T..."> is the most reliable
    time_tag = item.find("time")
    if time_tag:
        dt_str = time_tag.get("datetime") or time_tag.get_text(strip=True)
        try:
            pub = datetime.fromisoformat(dt_str)
            if pub.tzinfo is None:
                pub = pub.replace(tzinfo=timezone.utc)
            return datetime.now(timezone.utc) - pub <= _CUTOFF
        except Exception:
            pass

    # Fallback: look for elements with "date" or "posted" in class/text
    date_tag = item.find(class_=lambda c: c and any(x in str(c).lower() for x in ["date", "posted", "ago"]))
    if date_tag:
        text = date_tag.get_text(strip=True).lower()
        if any(x in text for x in ["just now", "minute", "hour", "today"]):
            return True
        if "1 day" in text:
            return True
        if any(f"{n} day" in text for n in ["2", "3", "4", "5", "6", "7"]):
            return False

    return True  # no date found — don't filter out


def make_hash(title, company, url):
    raw = f"{title.lower().strip()}{company.lower().strip()}{url.strip()}"
    return hashlib.sha256(raw.encode()).hexdigest()


def is_relevant(title):
    return any(kw in title.lower() for kw in RELEVANT_KEYWORDS)


def run():
    """Scrape MyJobMag Kenya and save relevant jobs to DB."""
    print("Starting MyJobMag scraper...")
    total_new = 0
    total_dupes = 0
    total_skipped = 0

    for page in range(1, PAGES + 1):
        url = f"{LISTINGS_URL}?page={page}"
        print(f"  Fetching page {page}: {url}")
        try:
            resp = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
        except Exception as e:
            print(f"  Error fetching page {page}: {e}")
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        time.sleep(random.uniform(1, 3))
        items = soup.select(".job-list-item, .job_listing, article.job_listing")

        if not items:
            items = soup.find_all("li", class_=lambda c: c and "job" in c.lower())

        print(f"  Found {len(items)} listings")

        for item in items:
            title_tag = item.find(["h2", "h3", "h4"]) or item.find(class_=lambda c: c and "title" in str(c).lower())
            if not title_tag:
                continue
            title = title_tag.get_text(strip=True)

            if not is_recent(item):
                total_skipped += 1
                continue

            if not is_relevant(title):
                total_skipped += 1
                continue

            company_tag = item.find(class_=lambda c: c and "company" in str(c).lower())
            company = company_tag.get_text(strip=True) if company_tag else "Unknown"

            location_tag = item.find(class_=lambda c: c and "location" in str(c).lower())
            location = location_tag.get_text(strip=True) if location_tag else "Kenya"

            link_tag = title_tag.find("a", href=True) or item.find("a", href=True)
            if not link_tag:
                continue
            href = link_tag.get("href", "")
            job_url = href if href.startswith("http") else f"{BASE_URL}{href}"

            jd_hash = make_hash(title, company, job_url)

            job_id = insert_job(
                source="myjobmag",
                title=title,
                company=company,
                location=location,
                remote_type="onsite",
                apply_method="form",
                apply_url=job_url,
                jd_url=job_url,
                jd_text="",
                jd_hash=jd_hash,
            )

            if job_id:
                print(f"    + Saved: {title} @ {company}")
                total_new += 1
            else:
                total_dupes += 1

    print(f"\nMyJobMag done: {total_new} new, {total_dupes} dupes, {total_skipped} irrelevant")
    return total_new


if __name__ == "__main__":
    run()
