import hashlib
import time
import random
import requests
from bs4 import BeautifulSoup
from app.tracking.db import insert_job

BASE_URL = "https://www.myjobkenya.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

SEARCH_URLS = [
    f"{BASE_URL}/jobs-in-kenya/data-analyst-jobs-in-kenya",
    f"{BASE_URL}/jobs-in-kenya/software-engineer-jobs-in-kenya",
    f"{BASE_URL}/jobs-in-kenya/software-developer-jobs-in-kenya",
    f"{BASE_URL}/jobs-in-kenya/it-jobs-in-kenya",
]


def make_hash(title, company, url):
    raw = f"{title.lower().strip()}{company.lower().strip()}{url.strip()}"
    return hashlib.sha256(raw.encode()).hexdigest()


def detect_apply_method(jd_text, jd_soup):
    """Detect whether the job is applied via email or web form."""
    import re
    email_pattern = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

    # Check for email address in the JD text
    emails = email_pattern.findall(jd_text or "")
    # Filter out common non-apply emails
    apply_emails = [e for e in emails if not any(
        x in e.lower() for x in ["noreply", "no-reply", "info@myjob"]
    )]
    if apply_emails:
        return "email", f"mailto:{apply_emails[0]}"

    # Check for an external apply button
    if jd_soup:
        apply_btn = jd_soup.find("a", string=lambda s: s and "apply" in s.lower())
        if apply_btn and apply_btn.get("href"):
            href = apply_btn["href"]
            if href.startswith("http") and "myjobkenya" not in href:
                return "form", href

    return "unknown", None


def scrape_job_page(job_url):
    """Fetch a single job page and return (jd_text, apply_method, apply_url, soup)."""
    try:
        resp = requests.get(job_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Extract job description text
        jd_div = (
            soup.find("div", class_="job-description")
            or soup.find("div", class_="description")
            or soup.find("div", {"id": "job-description"})
            or soup.find("article")
        )
        jd_text = jd_div.get_text(separator="\n", strip=True) if jd_div else ""

        apply_method, apply_url = detect_apply_method(jd_text, soup)
        return jd_text, apply_method, apply_url

    except Exception as e:
        print(f"    Error fetching job page {job_url}: {e}")
        return "", "unknown", None


def scrape_listing_page(url):
    """Scrape one listing page and return a list of job dicts."""
    jobs = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Job cards on myjobkenya use article or div with job listing classes
        cards = (
            soup.find_all("div", class_="job-listing")
            or soup.find_all("article", class_=lambda c: c and "job" in c.lower())
            or soup.find_all("div", class_=lambda c: c and "listing" in (c or "").lower())
        )

        for card in cards:
            try:
                # Title
                title_el = (
                    card.find("h2") or card.find("h3")
                    or card.find("a", class_=lambda c: c and "title" in (c or "").lower())
                )
                title = title_el.get_text(strip=True) if title_el else None
                if not title:
                    continue

                # Company
                company_el = card.find(class_=lambda c: c and "company" in (c or "").lower())
                company = company_el.get_text(strip=True) if company_el else "Unknown"

                # Location
                location_el = card.find(class_=lambda c: c and "location" in (c or "").lower())
                location = location_el.get_text(strip=True) if location_el else "Kenya"

                # Job URL
                link_el = card.find("a", href=True)
                job_url = link_el["href"] if link_el else None
                if job_url and not job_url.startswith("http"):
                    job_url = BASE_URL + job_url
                if not job_url:
                    continue

                jobs.append({
                    "title": title,
                    "company": company,
                    "location": location,
                    "jd_url": job_url,
                })
            except Exception as e:
                print(f"    Error parsing card: {e}")
                continue

    except Exception as e:
        print(f"  Error fetching listing page {url}: {e}")

    return jobs


def run():
    """Main entry point — scrape all search URLs and save to DB."""
    print("Starting MyJobKenya scraper...")
    total_new = 0
    total_dupes = 0

    for search_url in SEARCH_URLS:
        print(f"  Scraping: {search_url}")
        jobs = scrape_listing_page(search_url)
        print(f"  Found {len(jobs)} job cards")

        for job in jobs:
            jd_hash = make_hash(job["title"], job["company"], job["jd_url"])

            # Fetch full JD page
            time.sleep(random.uniform(1.5, 3.0))
            jd_text, apply_method, apply_url = scrape_job_page(job["jd_url"])

            job_id = insert_job(
                source="myjobkenya",
                title=job["title"],
                company=job["company"],
                location=job["location"],
                remote_type=None,
                apply_method=apply_method,
                apply_url=apply_url,
                jd_url=job["jd_url"],
                jd_text=jd_text,
                jd_hash=jd_hash,
            )

            if job_id:
                print(f"    + Saved: {job['title']} @ {job['company']}")
                total_new += 1
            else:
                total_dupes += 1

        # Polite pause between search pages
        time.sleep(random.uniform(2.0, 4.0))

    print(f"\nMyJobKenya done: {total_new} new jobs, {total_dupes} duplicates skipped")
    return total_new


if __name__ == "__main__":
    run()
