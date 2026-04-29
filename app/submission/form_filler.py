"""Playwright + AI form filler — fully automated job application form submission."""
import json
import re
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from app.ai.client import ask_ai

SCREENSHOT_DIR = Path("data/screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

# Fields we can fill from profile without AI
STANDARD_FIELD_PATTERNS = {
    "name":         ["full name", "your name", "first and last", "applicant name"],
    "first_name":   ["first name", "given name", "forename"],
    "last_name":    ["last name", "surname", "family name"],
    "email":        ["email", "e-mail", "email address"],
    "phone":        ["phone", "mobile", "telephone", "contact number"],
    "location":     ["location", "city", "where are you based", "current location"],
    "linkedin":     ["linkedin", "linkedin url", "linkedin profile"],
    "github":       ["github", "github url", "github profile"],
    "portfolio":    ["portfolio", "website", "personal website"],
    "cover_letter": ["cover letter", "covering letter", "why do you want", "why this role",
                     "why are you interested", "tell us about yourself"],
}

AI_ANSWER_PROMPT = """You are filling in a job application form on behalf of a candidate. Answer the following form question concisely and professionally.

Question: {question}

Candidate profile:
Name: {name}
Title/Background: {background}
Key skills: {skills}
Recent experience: {experience}
Notable projects: {projects}

Job being applied for:
Title: {job_title}
Company: {company}
Key requirements: {keywords}

Rules:
- Answer only the question asked
- Be specific and honest — only reference real skills and experience the candidate has
- For salary questions: give a range appropriate for {job_title} in {location} market (research typical rates)
- For "how would you approach X" questions: give a concrete 3-4 sentence answer referencing actual tools/methods
- For yes/no eligibility questions: answer "Yes" if the candidate qualifies
- Keep answers under 150 words unless a longer answer is clearly expected
- Plain text only, no bullet points unless listing items

Answer:"""


def _slug(s: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in s)[:30]


def _load_profile() -> dict:
    cv = json.loads(Path("data/master_cv.json").read_text())
    personal = cv["personal"]
    skills = []
    for items in cv["skills"].values():
        skills.extend(items[:4])
    recent = [f"{r['title']} at {r['company']}" for r in cv["work_experience"][:3]]
    projects = [p["name"] for p in cv.get("copycat_projects", [])[:3]]
    return {
        "name": personal["name"],
        "first_name": personal["name"].split()[0],
        "last_name": " ".join(personal["name"].split()[1:]),
        "email": personal["email"],
        "phone": personal["phone"],
        "location": personal["location"],
        "linkedin": personal.get("linkedin", ""),
        "github": personal.get("github", ""),
        "portfolio": personal.get("portfolio", ""),
        "skills": ", ".join(skills[:20]),
        "experience": ", ".join(recent),
        "projects": ", ".join(projects),
    }


def _match_standard_field(label: str) -> str | None:
    label_lower = label.lower()
    for field_key, patterns in STANDARD_FIELD_PATTERNS.items():
        for pattern in patterns:
            if pattern in label_lower:
                return field_key
    return None


def _ai_answer(question: str, job: dict, profile: dict) -> str:
    prompt = AI_ANSWER_PROMPT.format(
        question=question,
        name=profile["name"],
        background=profile["experience"],
        skills=profile["skills"],
        experience=profile["experience"],
        projects=profile["projects"],
        job_title=job["title"],
        company=job["company"],
        keywords=", ".join(job.get("keywords", [])[:15]),
        location=profile["location"],
    )
    return ask_ai(prompt).strip()


def submit(job: dict, cv_path: str, cover_letter_text: str) -> dict:
    """
    Attempt to fill and submit a job application form.

    Returns:
        {
            "success": bool,
            "status": "applied" | "needs_review",
            "reason": str,          # if needs_review
            "screenshots": [str],   # paths to screenshots taken
        }
    """
    profile = _load_profile()
    apply_url = job["apply_url"]
    job_slug = f"{job['id']}_{_slug(job['company'])}"
    screenshots = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()

        def screenshot(label: str) -> str:
            ts = datetime.now().strftime("%H%M%S")
            path = str(SCREENSHOT_DIR / f"{job_slug}_{label}_{ts}.png")
            page.screenshot(path=path, full_page=True)
            screenshots.append(path)
            return path

        try:
            page.goto(apply_url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            screenshot("01_loaded")

            # Detect login wall
            page_text = page.content().lower()
            if any(x in page_text for x in ["sign in to apply", "log in to apply", "create an account to apply"]):
                screenshot("blocked_login")
                browser.close()
                return {
                    "success": False,
                    "status": "needs_review",
                    "reason": "Login wall — requires account",
                    "screenshots": screenshots,
                }

            # Detect captcha
            if any(x in page_text for x in ["recaptcha", "hcaptcha", "cf-challenge"]):
                screenshot("blocked_captcha")
                browser.close()
                return {
                    "success": False,
                    "status": "needs_review",
                    "reason": "CAPTCHA detected",
                    "screenshots": screenshots,
                }

            # Collect all visible form fields
            inputs = page.query_selector_all("input:not([type='hidden']):not([type='submit']):not([type='button']), textarea, select")

            filled = 0
            for el in inputs:
                try:
                    input_type = (el.get_attribute("type") or "text").lower()
                    label_text = ""

                    # Try to find label via id/aria
                    el_id = el.get_attribute("id")
                    if el_id:
                        label_el = page.query_selector(f"label[for='{el_id}']")
                        if label_el:
                            label_text = label_el.inner_text().strip()

                    # Fallback: placeholder or name attribute
                    if not label_text:
                        label_text = el.get_attribute("placeholder") or el.get_attribute("name") or ""

                    if not label_text:
                        continue

                    # File upload
                    if input_type == "file":
                        label_lower = label_text.lower()
                        if any(x in label_lower for x in ["cv", "resume", "curriculum"]):
                            el.set_input_files(cv_path)
                            filled += 1
                        elif any(x in label_lower for x in ["cover", "letter"]):
                            # Save cover letter as txt for upload fallback
                            cl_txt = Path("data/cvs") / f"cover_{job['id']}.txt"
                            cl_txt.write_text(cover_letter_text)
                            el.set_input_files(str(cl_txt))
                            filled += 1
                        continue

                    # Checkbox / radio
                    if input_type in ("checkbox", "radio"):
                        label_lower = label_text.lower()
                        if any(x in label_lower for x in ["authoris", "authoriz", "eligible", "agree", "consent", "right to work"]):
                            if not el.is_checked():
                                el.check()
                            filled += 1
                        continue

                    # Select dropdown
                    tag = el.evaluate("el => el.tagName").lower()
                    if tag == "select":
                        options = el.query_selector_all("option")
                        option_texts = [o.inner_text().strip() for o in options if o.inner_text().strip()]
                        if option_texts:
                            answer = _ai_answer(
                                f"Select the best option for: {label_text}. Options: {', '.join(option_texts)}",
                                job, profile
                            )
                            # Pick the option whose text most closely matches the AI answer
                            best = option_texts[0]
                            ans_lower = answer.lower()
                            for opt in option_texts:
                                if opt.lower() in ans_lower or ans_lower in opt.lower():
                                    best = opt
                                    break
                            el.select_option(label=best)
                            filled += 1
                        continue

                    # Text / textarea — match standard or ask AI
                    field_key = _match_standard_field(label_text)
                    if field_key == "name":
                        value = profile["name"]
                    elif field_key == "first_name":
                        value = profile["first_name"]
                    elif field_key == "last_name":
                        value = profile["last_name"]
                    elif field_key == "email":
                        value = profile["email"]
                    elif field_key == "phone":
                        value = profile["phone"]
                    elif field_key == "location":
                        value = profile["location"]
                    elif field_key == "linkedin":
                        value = profile["linkedin"]
                    elif field_key == "github":
                        value = profile["github"]
                    elif field_key == "portfolio":
                        value = profile["portfolio"] or profile["linkedin"]
                    elif field_key == "cover_letter":
                        value = cover_letter_text
                    else:
                        # Unknown field — ask AI
                        value = _ai_answer(label_text, job, profile)

                    el.fill(value)
                    filled += 1

                except Exception:
                    continue

            if filled == 0:
                screenshot("no_fields_found")
                browser.close()
                return {
                    "success": False,
                    "status": "needs_review",
                    "reason": "Could not detect any fillable form fields",
                    "screenshots": screenshots,
                }

            screenshot("02_filled")

            # Find and click submit button
            submit_btn = None
            for selector in [
                "button[type='submit']",
                "input[type='submit']",
                "button:has-text('Submit')",
                "button:has-text('Apply')",
                "button:has-text('Send application')",
                "button:has-text('Submit application')",
            ]:
                try:
                    btn = page.query_selector(selector)
                    if btn and btn.is_visible():
                        submit_btn = btn
                        break
                except Exception:
                    continue

            if not submit_btn:
                screenshot("no_submit_button")
                browser.close()
                return {
                    "success": False,
                    "status": "needs_review",
                    "reason": "Could not find submit button",
                    "screenshots": screenshots,
                }

            submit_btn.click()
            page.wait_for_timeout(3000)
            screenshot("03_submitted")

            # Check for confirmation signals
            final_text = page.content().lower()
            confirmed = any(x in final_text for x in [
                "thank you", "thanks for applying", "application received",
                "application submitted", "we'll be in touch", "application complete",
                "successfully submitted", "we have received your application",
            ])

            browser.close()
            return {
                "success": confirmed,
                "status": "applied" if confirmed else "needs_review",
                "reason": "" if confirmed else "No confirmation signal after submit — may need manual check",
                "screenshots": screenshots,
            }

        except PlaywrightTimeout:
            screenshot("timeout")
            browser.close()
            return {
                "success": False,
                "status": "needs_review",
                "reason": "Page timed out loading",
                "screenshots": screenshots,
            }
        except Exception as e:
            try:
                screenshot("error")
                browser.close()
            except Exception:
                pass
            return {
                "success": False,
                "status": "needs_review",
                "reason": f"Unexpected error: {e}",
                "screenshots": screenshots,
            }
