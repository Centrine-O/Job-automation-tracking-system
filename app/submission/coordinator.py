"""Application submission coordinator — routes qualified jobs to email or form submitter."""
import random
import time
from datetime import datetime

from app.config import settings
from app.cv.engine import tailor, extract_keywords
from app.cv.renderer import render
from app.submission import cover_letter as cl_gen
from app.tracking.db import (
    count_applications_today,
    get_qualified_jobs,
    insert_application,
    get_connection,
)


def _count_source_today(source: str) -> int:
    conn = get_connection()
    row = conn.execute("""
        SELECT COUNT(*) as cnt FROM applications a
        JOIN jobs j ON j.id = a.job_id
        WHERE j.source = ? AND date(a.submitted_at) = date('now')
    """, (source,)).fetchone()
    conn.close()
    return row["cnt"]


def _mark_needs_review(job_id: int, reason: str, screenshots: list[str]):
    conn = get_connection()
    conn.execute(
        "UPDATE jobs SET status='needs_review' WHERE id=?", (job_id,)
    )
    conn.execute("""
        INSERT INTO applications (job_id, submission_method, status, notes, submitted_at)
        VALUES (?, 'form', 'needs_review', ?, ?)
    """, (job_id, f"{reason} | screenshots: {', '.join(screenshots)}",
          datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()


def _save_gmail_message_id(app_id: int, msg_id: str):
    conn = get_connection()
    conn.execute(
        "UPDATE applications SET notes=? WHERE id=?",
        (f"gmail_message_id:{msg_id}", app_id)
    )
    conn.commit()
    conn.close()


def run_batch(max_jobs: int = None, dry_run: bool = None) -> dict:
    """
    Pick top qualified jobs and submit applications.

    Returns summary dict with counts.
    """
    if dry_run is None:
        dry_run = settings.dry_run
    if max_jobs is None:
        max_jobs = settings.max_applications_per_day

    today_count = count_applications_today()
    remaining_slots = max_jobs - today_count
    if remaining_slots <= 0:
        print(f"  Daily cap reached ({today_count}/{max_jobs}). Skipping.")
        return {"submitted": 0, "skipped": 0, "needs_review": 0, "cap_reached": True}

    # Get qualified jobs not yet applied to, sorted by score
    all_qualified = get_qualified_jobs()
    # Filter out already applied / needs_review
    candidates = [j for j in all_qualified if j["status"] == "qualified"]
    # Sort by skill_score desc
    candidates.sort(key=lambda j: j.get("skill_score", 0), reverse=True)
    batch = candidates[:remaining_slots]

    print(f"  {len(candidates)} candidates, processing up to {len(batch)} (slots left: {remaining_slots})")

    submitted = 0
    skipped = 0
    needs_review = 0

    for job in batch:
        job_id = job["id"]
        source = job.get("source", "")
        print(f"\n  [{job_id}] {job['title']} @ {job['company']} ({job['apply_method']})")

        # Per-source cap (max 3/day from same source)
        if _count_source_today(source) >= 3:
            print(f"    Skipped — source cap reached for '{source}'")
            skipped += 1
            continue

        if not job.get("jd_text"):
            print(f"    Skipped — no JD text")
            skipped += 1
            continue

        # Generate CV + cover letter
        print(f"    Generating tailored CV...")
        if not dry_run:
            try:
                tailored = tailor(
                    job_id=job_id,
                    title=job["title"],
                    company=job["company"],
                    jd_text=job["jd_text"],
                )
                paths = render(tailored)
                keywords = tailored["keywords"]
                ats_score = tailored["ats_score"]
            except Exception as e:
                print(f"    CV generation failed: {e}")
                skipped += 1
                continue

            print(f"    Generating cover letter...")
            try:
                cl_text = cl_gen.generate(
                    job_id=job_id,
                    title=job["title"],
                    company=job["company"],
                    keywords=keywords,
                )
                cl_pdf = cl_gen.render_pdf(
                    job_id=job_id,
                    title=job["title"],
                    company=job["company"],
                    text=cl_text,
                )
            except Exception as e:
                print(f"    Cover letter failed: {e}")
                cl_text = ""
                cl_pdf = ""
        else:
            paths = {"docx": f"data/cvs/dry_run_{job_id}.docx", "pdf": f"data/cvs/dry_run_{job_id}.pdf"}
            ats_score = 0
            keywords = []
            cl_text = "[DRY RUN cover letter]"
            cl_pdf = ""

        apply_method = job.get("apply_method", "form")
        apply_url = job.get("apply_url", "")

        if apply_method == "email":
            subject = f"Application for {job['title']} — Centrine Ong'aria"

            if dry_run:
                print(f"    [DRY RUN] Would email → {apply_url}")
                print(f"    Subject: {subject}")
                app_id = insert_application(
                    job_id=job_id,
                    cv_path=paths["pdf"],
                    cover_letter_path=cl_pdf,
                    ats_score=ats_score,
                    submission_method="email_dry_run",
                )
            else:
                from app.submission.email_sender import send_application
                try:
                    msg_id = send_application(
                        to=apply_url,
                        subject=subject,
                        cv_path=paths["pdf"],
                        cover_letter_path=cl_pdf,
                    )
                    app_id = insert_application(
                        job_id=job_id,
                        cv_path=paths["pdf"],
                        cover_letter_path=cl_pdf,
                        ats_score=ats_score,
                        submission_method="email",
                    )
                    _save_gmail_message_id(app_id, msg_id)
                    print(f"    Email sent → {apply_url}")
                except Exception as e:
                    print(f"    Email failed: {e}")
                    skipped += 1
                    continue

            submitted += 1

        else:  # form
            if dry_run:
                print(f"    [DRY RUN] Would open form → {apply_url}")
                insert_application(
                    job_id=job_id,
                    cv_path=paths["pdf"],
                    cover_letter_path="",
                    ats_score=ats_score,
                    submission_method="form_dry_run",
                )
                submitted += 1
            else:
                from app.submission.form_filler import submit
                job_with_keywords = {**job, "keywords": keywords}
                result = submit(
                    job=job_with_keywords,
                    cv_path=paths["pdf"],
                    cover_letter_text=cl_text,
                )
                if result["status"] == "applied":
                    insert_application(
                        job_id=job_id,
                        cv_path=paths["pdf"],
                        cover_letter_path="",
                        ats_score=ats_score,
                        submission_method="form",
                    )
                    print(f"    Form submitted ✓  screenshots: {result['screenshots']}")
                    submitted += 1
                else:
                    _mark_needs_review(job_id, result["reason"], result["screenshots"])
                    print(f"    Needs review: {result['reason']}")
                    needs_review += 1

        # Random delay between submissions (30–90s) to avoid anti-bot detection
        if not dry_run and batch.index(job) < len(batch) - 1:
            delay = random.randint(30, 90)
            print(f"    Waiting {delay}s before next submission...")
            time.sleep(delay)

    print(f"\n  Done: {submitted} submitted, {skipped} skipped, {needs_review} needs review")
    return {
        "submitted": submitted,
        "skipped": skipped,
        "needs_review": needs_review,
        "cap_reached": False,
    }
