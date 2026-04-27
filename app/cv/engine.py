"""CV tailoring engine — extracts JD keywords, tailors CV, scores ATS."""
import json
import re
from pathlib import Path
from app.ai.client import ask_ai


def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&[a-z]+;", " ", text)
    return re.sub(r"\s+", " ", text).strip()

CV_PATH = Path("data/master_cv.json")

KEYWORD_PROMPT = """Extract the top 30 ATS keywords from this job description.
Focus ONLY on: programming languages, frameworks, tools, platforms, technical skills, methodologies (e.g. Agile, CI/CD), and specific role requirements.
EXCLUDE: company names, VC names, location requirements, salary info, culture words like "remote" or "fast-paced".
Return ONLY a JSON array of strings. No explanation, no markdown.

Job Description:
{jd_text}

Return the JSON array now:"""

TAILOR_PROMPT = """You are an expert ATS-optimised CV writer. Tailor this candidate's CV for a specific job.

Rules:
- Use ONLY skills and experience the candidate actually has
- Naturally incorporate as many of the target keywords as possible (aim for 90%+ coverage)
- Do NOT keyword-stuff — keywords must appear in natural sentences
- Rewrite the profile summary to speak directly to this role
- For experience bullets: rewrite/enhance to highlight relevant work using JD keywords
- For skills: reorganise and highlight skills most relevant to the JD (keep all real skills, just reorder/regroup)

Return ONLY this JSON (no markdown, no explanation):
{{
  "profile_summary": "3-4 sentence summary targeting this role",
  "skills": {{
    "Languages": ["...", "..."],
    "Frameworks & Libraries": ["...", "..."],
    "Databases": ["...", "..."],
    "Data Analysis": ["...", "..."],
    "AI & Machine Learning": ["...", "..."],
    "Automation & Tools": ["...", "..."],
    "DevOps & Cloud": ["...", "..."]
  }},
  "experience_bullets": {{
    "role_key": ["bullet 1", "bullet 2", "bullet 3"]
  }}
}}

The experience_bullets keys must match exactly: "title|company" format.
Only include the top 4 most relevant roles.

--- CANDIDATE PROFILE ---
Name: {name}
{all_skills}

Work Experience:
{experience_text}

--- TARGET JOB ---
Title: {job_title}
Company: {company}
Keywords to hit: {keywords}

Return ONLY the JSON now:"""


def _all_skills_text(cv: dict) -> str:
    skills = cv.get("skills", {})
    lines = []
    label_map = {
        "languages": "Languages", "frameworks": "Frameworks",
        "databases": "Databases", "data": "Data Analysis",
        "ai_ml": "AI & ML", "automation": "Automation",
        "tools": "Tools", "cloud": "Cloud",
    }
    for key, label in label_map.items():
        items = skills.get(key, [])
        if items:
            lines.append(f"{label}: {', '.join(items)}")
    return "\n".join(lines)


def _experience_text(cv: dict) -> str:
    lines = []
    for role in cv.get("work_experience", []):
        key = f"{role['title']}|{role['company']}"
        lines.append(f"\n[{key}] {role['start_date']} – {role['end_date']}, {role.get('location','')}")
        for b in role.get("bullets", []):
            lines.append(f"  • {b}")
    return "\n".join(lines)


def extract_keywords(jd_text: str) -> list[str]:
    prompt = KEYWORD_PROMPT.format(jd_text=jd_text[:3000])
    response = ask_ai(prompt)
    cleaned = re.sub(r"```[a-z]*", "", response).strip().strip("`").strip()
    try:
        kws = json.loads(cleaned)
        return [k.strip() for k in kws if isinstance(k, str)]
    except Exception:
        return re.findall(r'"([^"]+)"', cleaned)


def calculate_ats_score(cv_text: str, keywords: list[str]) -> float:
    if not keywords:
        return 0.0
    cv_lower = cv_text.lower()
    matched = sum(1 for kw in keywords if kw.lower() in cv_lower)
    return round(matched / len(keywords) * 100, 1)


def _cv_to_text(tailored: dict) -> str:
    parts = [tailored.get("profile_summary", "")]
    for items in tailored.get("skills", {}).values():
        parts.extend(items)
    for role in tailored.get("experience", []):
        parts.append(role.get("title", ""))
        parts.append(role.get("company", ""))
        parts.extend(role.get("bullets", []))
    return " ".join(parts)


def tailor(job_id: int, title: str, company: str, jd_text: str) -> dict:
    """Tailor master CV for a specific job. Returns tailored CV dict."""
    cv = json.loads(CV_PATH.read_text())

    jd_text = _strip_html(jd_text)

    print(f"  Extracting keywords from JD...")
    keywords = extract_keywords(jd_text)
    print(f"  Found {len(keywords)} keywords")

    print(f"  Tailoring CV with AI...")
    prompt = TAILOR_PROMPT.format(
        name=cv["personal"]["name"],
        all_skills=_all_skills_text(cv),
        experience_text=_experience_text(cv),
        job_title=title,
        company=company,
        keywords=", ".join(keywords),
    )

    response = ask_ai(prompt)
    cleaned = re.sub(r"```[a-z]*", "", response).strip().strip("`").strip()

    try:
        ai_output = json.loads(cleaned)
    except Exception as e:
        raise ValueError(f"AI returned invalid JSON: {e}\nResponse: {cleaned[:300]}")

    # Merge AI output with master CV structure
    exp_bullets = ai_output.get("experience_bullets", {})
    experience = []
    for role in cv.get("work_experience", []):
        key = f"{role['title']}|{role['company']}"
        role_out = {
            "title": role["title"],
            "company": role["company"],
            "location": role.get("location", ""),
            "start_date": role["start_date"],
            "end_date": role["end_date"],
            "bullets": exp_bullets.get(key, role.get("bullets", [])),
        }
        experience.append(role_out)

    tailored = {
        "job_id": job_id,
        "job_title": title,
        "company": company,
        "name": cv["personal"]["name"],
        "location": cv["personal"]["location"],
        "email": cv["personal"]["email"],
        "phone": cv["personal"]["phone"],
        "linkedin": cv["personal"].get("linkedin", ""),
        "github": cv["personal"].get("github", ""),
        "profile_summary": ai_output.get("profile_summary", ""),
        "skills": ai_output.get("skills", {}),
        "experience": experience,
        "certifications": cv.get("certifications", []),
        "education": cv.get("education", []),
        "keywords": keywords,
    }

    ats_score = calculate_ats_score(_cv_to_text(tailored), keywords)
    tailored["ats_score"] = ats_score
    print(f"  ATS Score: {ats_score}%")

    # Second pass if below 90% — explicitly inject missing keywords
    if ats_score < 80:
        cv_lower = _cv_to_text(tailored).lower()
        missing = [kw for kw in keywords if kw.lower() not in cv_lower]
        if missing:
            print(f"  Boosting score — {len(missing)} missing keywords, running second pass...")
            boost_prompt = (
                "You are an ATS CV optimiser. Rewrite ONLY the profile_summary and add to skills "
                "to naturally include these missing keywords. Do not fabricate experience. "
                "Return ONLY JSON: {{\"profile_summary\": \"...\", \"extra_skills\": [\"...\"]}}\\n\\n"
                f"Current profile summary:\\n{tailored['profile_summary']}\\n\\n"
                f"Missing keywords to include: {', '.join(missing)}\\n\\n"
                f"Candidate's actual skills for reference:\\n{_all_skills_text(cv)}"
            )
            try:
                boost_response = ask_ai(boost_prompt)
                boost_cleaned = re.sub(r"```[a-z]*", "", boost_response).strip().strip("`").strip()
                boost_data = json.loads(boost_cleaned)
                tailored["profile_summary"] = boost_data.get("profile_summary", tailored["profile_summary"])
                extra = boost_data.get("extra_skills", [])
                if extra:
                    existing = tailored["skills"].setdefault("Additional Skills", [])
                    existing.extend(e for e in extra if e not in existing)
                ats_score = calculate_ats_score(_cv_to_text(tailored), keywords)
                tailored["ats_score"] = ats_score
                print(f"  ATS Score after boost: {ats_score}%")
            except Exception as e:
                print(f"  [boost error] {e}")

    return tailored
