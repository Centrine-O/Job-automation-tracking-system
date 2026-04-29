"""Send one test application email to yourself to verify the full email flow."""
import sqlite3
from pathlib import Path

from app.cv.engine import tailor
from app.cv.renderer import render
from app.submission.cover_letter import generate as gen_cover_letter, render_pdf as render_cl_pdf
from app.submission.email_sender import send_application

TEST_TO = "centyanita@gmail.com"

# Use the top qualified job with jd_text available
conn = sqlite3.connect("data/jobs.db")
conn.row_factory = sqlite3.Row
job = conn.execute("""
    SELECT id, title, company, jd_text FROM jobs
    WHERE status = 'qualified' AND jd_text IS NOT NULL AND jd_text != ''
    ORDER BY skill_score DESC LIMIT 1
""").fetchone()
conn.close()

if not job:
    print("No qualified jobs with JD text found.")
    exit()

job = dict(job)
print(f"Using job: {job['title']} @ {job['company']} (ID {job['id']})")
print()

print("Generating tailored CV...")
tailored = tailor(
    job_id=job["id"],
    title=job["title"],
    company=job["company"],
    jd_text=job["jd_text"],
)
paths = render(tailored)
print(f"  CV: {paths['pdf']}")
print(f"  ATS: {tailored['ats_score']}%")

print()
print("Generating cover letter...")
cl_text = gen_cover_letter(
    job_id=job["id"],
    title=job["title"],
    company=job["company"],
    keywords=tailored["keywords"],
)
cl_pdf = render_cl_pdf(
    job_id=job["id"],
    title=job["title"],
    company=job["company"],
    text=cl_text,
)
print()
print("--- COVER LETTER PREVIEW ---")
print(cl_text)
print("----------------------------")
print(f"  Cover letter PDF: {cl_pdf}")

print()
subject = f"[TEST] Application for {job['title']} — Centrine Ong'aria"

print(f"Sending test email to {TEST_TO}...")
print(f"  Attaching: {paths['pdf']}")
print(f"  Attaching: {cl_pdf}")
msg_id = send_application(
    to=TEST_TO,
    subject=subject,
    cv_path=paths["pdf"],
    cover_letter_path=cl_pdf,
)
print(f"✓ Email sent! Message ID: {msg_id}")
print(f"  Check your inbox at {TEST_TO}")
