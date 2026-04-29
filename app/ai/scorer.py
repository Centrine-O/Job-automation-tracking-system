"""Score jobs against Centrine's CV using AI."""
import json
import re
import time
from pathlib import Path
from app.ai.client import ask_ai
from app.tracking.db import get_unscored_jobs, update_job_scores

CV_PATH = Path("data/master_cv.json")

SCORE_PROMPT = """You are a job-fit evaluator. Given a candidate's profile and a job description, return ONLY a JSON object with two integer scores (0-100). No explanation, no markdown, no extra text.

Scoring guide:
- skill_score: How well the candidate's skills and experience match the job requirements.
- hire_score: Overall hiring likelihood considering skills, experience level, and role fit.

Return exactly this format:
{{"skill_score": 75, "hire_score": 70}}

--- CANDIDATE PROFILE ---
{cv_summary}

--- JOB DESCRIPTION ---
Title: {title}
Company: {company}
Location: {location}
{jd_text}

Return ONLY the JSON object now:"""


def _build_cv_summary(cv: dict) -> str:
    lines = []

    # Skills
    skills = cv.get("skills", {})
    all_skills = []
    for category_skills in skills.values():
        all_skills.extend(category_skills)
    lines.append(f"Skills: {', '.join(all_skills)}")

    # Experience (last 4 roles to keep prompt short)
    experience = cv.get("experience", [])[:4]
    lines.append("\nRecent Experience:")
    for role in experience:
        lines.append(
            f"  - {role.get('title')} at {role.get('company')} "
            f"({role.get('start_date')} – {role.get('end_date')})"
        )
        bullets = role.get("bullets", [])[:2]
        for b in bullets:
            lines.append(f"      • {b}")

    # Education
    education = cv.get("education", [])
    if education:
        edu = education[0]
        lines.append(
            f"\nEducation: {edu.get('degree')} in {edu.get('field')}, "
            f"{edu.get('institution')} ({edu.get('graduation_year')})"
        )

    return "\n".join(lines)


def _parse_scores(text: str) -> tuple[int, int] | None:
    """Extract skill_score and hire_score from AI response."""
    try:
        # Strip markdown code fences if present
        cleaned = re.sub(r"```[a-z]*", "", text).strip().strip("`").strip()
        data = json.loads(cleaned)
        skill = int(data["skill_score"])
        hire = int(data["hire_score"])
        return skill, hire
    except Exception:
        # Try regex fallback
        skill_match = re.search(r'"skill_score"\s*:\s*(\d+)', text)
        hire_match = re.search(r'"hire_score"\s*:\s*(\d+)', text)
        if skill_match and hire_match:
            return int(skill_match.group(1)), int(hire_match.group(1))
        return None


def score_all():
    """Alias used by scheduler."""
    return run()


def run():
    """Score all unscored jobs in the DB."""
    if not CV_PATH.exists():
        print("master_cv.json not found — run CV setup first.")
        return

    cv = json.loads(CV_PATH.read_text())
    cv_summary = _build_cv_summary(cv)

    jobs = get_unscored_jobs()
    print(f"Scoring {len(jobs)} unscored jobs...")

    scored = 0
    failed = 0

    for job in jobs:
        job_id = job["id"]
        title = job["title"]
        company = job["company"]
        location = job["location"]
        jd_text = job["jd_text"]
        jd_snippet = (jd_text or "")[:2000]

        prompt = SCORE_PROMPT.format(
            cv_summary=cv_summary,
            title=title,
            company=company,
            location=location or "",
            jd_text=jd_snippet,
        )

        success = False
        for attempt in range(2):
            try:
                response = ask_ai(prompt)
                scores = _parse_scores(response)
                if scores is None:
                    print(f"  [!] Could not parse scores for: {title} @ {company}")
                    failed += 1
                    success = True
                    break

                skill_score, hire_score = scores
                update_job_scores(job_id, skill_score, hire_score)
                status = "qualified" if skill_score >= 65 and hire_score >= 60 else "skipped"
                print(
                    f"  {'✓' if status == 'qualified' else '·'} "
                    f"{title[:40]:<40} skill={skill_score} hire={hire_score} [{status}]"
                )
                scored += 1
                success = True
                break

            except Exception as e:
                msg = str(e)
                if attempt == 0:
                    wait = 30 if "NameResolution" in msg or "SSL" in msg else 300
                    print(f"  [retry] waiting {wait}s...")
                    time.sleep(wait)
                else:
                    print(f"  [!] Skipping {title}: {e}")
                    failed += 1

        time.sleep(30)

    print(f"\nDone: {scored} scored, {failed} failed")


if __name__ == "__main__":
    run()
