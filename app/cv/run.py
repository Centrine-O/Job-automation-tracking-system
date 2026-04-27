"""Test the CV engine on one qualified job."""
import sqlite3
from app.cv.engine import tailor
from app.cv.renderer import render


def get_one_qualified_job():
    conn = sqlite3.connect("data/jobs.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT id, title, company, location, jd_text
        FROM jobs
        WHERE status = 'qualified' AND jd_text IS NOT NULL AND jd_text != ''
        ORDER BY skill_score DESC
        LIMIT 1
    """)
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def main():
    job = get_one_qualified_job()
    if not job:
        print("No qualified jobs with JD text found.")
        return

    print(f"Generating CV for: {job['title']} @ {job['company']}")
    print(f"Job ID: {job['id']}")
    print()

    tailored = tailor(
        job_id=job["id"],
        title=job["title"],
        company=job["company"],
        jd_text=job["jd_text"],
    )

    print(f"\nRendering DOCX and PDF...")
    paths = render(tailored)

    print(f"\n✓ Done!")
    print(f"  ATS Score : {tailored['ats_score']}%")
    print(f"  DOCX      : {paths['docx']}")
    print(f"  PDF       : {paths['pdf']}")
    print(f"  Keywords  : {', '.join(tailored['keywords'][:10])}...")


if __name__ == "__main__":
    main()
