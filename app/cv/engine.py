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

CRITICAL RULES FOR THE PROFILE SUMMARY:
- 3 sentences MAX. No exceptions.
- Start with the role/title area, NOT the candidate's name
- NEVER use these generic phrases: "proven", "expertise in", "track record", "passionate about", "results-driven", "dedicated", "leverage", "spearhead", "dynamic", "seeking to", "looking to", "strong foundation", "responsible for"
- Write like a confident person talking in an interview — specific, real, direct
- Reference ACTUAL things from the CV: real tools used, real companies, real types of work done
- BAD example: "Proven AI engineer with expertise in automation and a track record of delivering results."
- GOOD example: "Full Stack Developer and AI engineer with hands-on experience building agentic systems, LLM-powered pipelines, and automation tools — across both U.S. and Kenyan tech companies. I work across the full stack, from Python backends and REST APIs to React frontends, and have spent the last year deep in AI data work including model evaluation, prompt engineering, and dataset structuring. Currently building production systems at Copy Cat Group, including a live SAP API integration and an AI-powered tender scraping pipeline."
- Naturally include the target keywords but do NOT keyword-stuff

OTHER RULES:
- Use ONLY skills and experience the candidate actually has
- For experience bullets: use action verbs, keep concise (max 15 words each), include JD keywords naturally
- For the Copy Cat Group role specifically: draw from the live projects listed below to write specific, credible bullets
- Only include the top 4 most relevant roles in experience_bullets

Return ONLY this JSON (no markdown, no explanation):
{{
  "profile_summary": "3-4 sentence summary in professional CV voice",
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
    "Full Stack Developer|Copy Cat Group": ["bullet 1", "bullet 2", "bullet 3"]
  }}
}}

The experience_bullets keys must match exactly: "title|company" format.

--- CANDIDATE PROFILE ---
Name: {name}
{all_skills}

Work Experience:
{experience_text}

Copy Cat Group — Live Projects (use these for specific, credible bullets):
{copycat_projects}

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
    score = 0.0
    for kw in keywords:
        kw_lower = kw.lower()
        if kw_lower in cv_lower:
            score += 1.0
        else:
            # Partial credit: check how many individual words appear
            words = [w for w in kw_lower.split() if len(w) > 2]
            if words:
                hits = sum(1 for w in words if w in cv_lower)
                score += (hits / len(words)) * 0.8
    return round(score / len(keywords) * 100, 1)


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
    copycat_proj_text = "\n".join(
        f"- {p['name']}: {p['description']}"
        for p in cv.get("copycat_projects", [])
    )
    prompt = TAILOR_PROMPT.format(
        name=cv["personal"]["name"],
        all_skills=_all_skills_text(cv),
        experience_text=_experience_text(cv),
        copycat_projects=copycat_proj_text,
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
            # Only add short keywords (tools/tech names) — skip long contextual phrases
            SKIP_PHRASES = {"client operations", "workflow", "intelligent solutions",
                            "measurable results", "streamline", "enhance"}
            injectable = [
                kw for kw in missing
                if len(kw.split()) <= 3
                and kw.lower() not in SKIP_PHRASES
            ]
            if injectable:
                print(f"  Boosting score — adding {len(injectable)} skill keywords...")
                mid = len(injectable) // 2
                group_a = injectable[:mid]
                group_b = injectable[mid:]
                a = tailored["skills"].setdefault("AI & Specialist Tools", [])
                a.extend(kw for kw in group_a if kw not in a)
                if group_b:
                    b = tailored["skills"].setdefault("Platforms & Methods", [])
                    b.extend(kw for kw in group_b if kw not in b)
            ats_score = calculate_ats_score(_cv_to_text(tailored), keywords)
            tailored["ats_score"] = ats_score
            print(f"  ATS Score after boost: {ats_score}%")

    return tailored
