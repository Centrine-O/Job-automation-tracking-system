import hashlib
import time
import random
import requests
from bs4 import BeautifulSoup
from app.tracking.db import insert_job

BASE_URL = "https://www.myjobmag.co.ke"
LISTINGS_URL = f"{BASE_URL}/jobs"

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


def make_hash(title, company, url):
    raw = f"{title.lower().strip()}{company.lower().strip()}{url.strip()}"
    return hashlib.sha256(raw.encode()).hexdigest()


def is_relevant(title):
    return any(kw in title.lower() for kw in RELEVANT_KEYWORDS)


def parse_title_company(link_text):
    """
    MyJobMag titles are formatted as "Job Title at Company Name".
    Split on the last occurrence of ' at ' to handle titles that contain 'at'.
    """
    sep = " at "
    idx = link_text.rfind(sep)
    if idx == -1:
        return link_text.strip(), "Unknown"
    return link_text[:idx].strip(), link_text[idx + len(sep):].strip()


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
        time.sleep(random.uniform(1, 2))

        items = soup.find_all("li", class_="mag-b")
        print(f"  Found {len(items)} listings")

        for item in items:
            a_tag = item.find("a", href=True)
            if not a_tag:
                continue

            link_text = a_tag.get_text(strip=True)
            title, company = parse_title_company(link_text)

            if not is_relevant(title):
                total_skipped += 1
                continue

            href = a_tag["href"]
            job_url = href if href.startswith("http") else f"{BASE_URL}{href}"
            jd_hash = make_hash(title, company, job_url)

            job_id = insert_job(
                source="myjobmag",
                title=title,
                company=company,
                location="Kenya",
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
