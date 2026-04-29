"""AI cover letter generator — short, personal, tailored to the specific JD."""
import json
import re
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

from app.ai.client import ask_ai

CV_PATH = Path("data/master_cv.json")

COVER_LETTER_PROMPT = """Write a short cover letter for a job application. 3 paragraphs maximum.

RULES:
- Sound like a real person writing directly, not a corporate template
- Paragraph 1: Why this specific role at this specific company interests you (reference something real about the company or role)
- Paragraph 2: 2-3 specific things from your background that directly match what they need — use real tools, real projects, real companies
- Paragraph 3: One sentence closing — confident, not desperate
- NEVER use: "I am writing to express", "proven track record", "passionate about", "leverage", "synergy", "dynamic", "seeking to", "looking to", "I believe I would be a great fit"
- No sign-off line (e.g. no "Sincerely," or "Best regards,") — just end after the closing sentence
- Plain text only, no markdown

--- CANDIDATE ---
Name: {name}
Location: {location}
Email: {email}
Background: {summary}
Key skills: {skills}
Recent roles: {recent_roles}
Notable projects: {projects}

--- JOB ---
Title: {title}
Company: {company}
Key requirements: {keywords}

Write the cover letter now (plain text, 3 paragraphs, no sign-off):"""


OUTPUT_DIR = Path("data/cvs")


def generate(job_id: int, title: str, company: str, keywords: list[str]) -> str:
    """Generate a short cover letter. Returns plain text string."""
    cv = json.loads(CV_PATH.read_text())

    personal = cv["personal"]
    skills_flat = []
    for items in cv["skills"].values():
        skills_flat.extend(items[:3])

    recent_roles = []
    for role in cv["work_experience"][:3]:
        recent_roles.append(f"{role['title']} at {role['company']}")

    projects = [p["name"] for p in cv.get("copycat_projects", [])[:3]]
    summary = cv.get("summary_variants", {}).get("ai_automation", "")

    prompt = COVER_LETTER_PROMPT.format(
        name=personal["name"],
        location=personal["location"],
        email=personal["email"],
        summary=summary,
        skills=", ".join(skills_flat[:15]),
        recent_roles=", ".join(recent_roles),
        projects=", ".join(projects),
        title=title,
        company=company,
        keywords=", ".join(keywords[:15]),
    )

    text = ask_ai(prompt).strip()
    text = re.sub(r"```[a-z]*", "", text).strip("`").strip()
    return text


def render_pdf(job_id: int, title: str, company: str, text: str) -> str:
    """Render cover letter text to a PDF. Returns the file path."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    slug = "".join(c if c.isalnum() or c in "-_" else "_" for c in company)[:30]
    path = str(OUTPUT_DIR / f"cl_{job_id}_{slug}.pdf")

    cv = json.loads(CV_PATH.read_text())
    personal = cv["personal"]

    doc = SimpleDocTemplate(
        path, pagesize=A4,
        topMargin=0.9 * inch, bottomMargin=0.9 * inch,
        leftMargin=0.9 * inch, rightMargin=0.9 * inch,
    )

    S = {
        "name": ParagraphStyle("name", fontSize=13, fontName="Helvetica-Bold", spaceAfter=2),
        "contact": ParagraphStyle("contact", fontSize=9, fontName="Helvetica", spaceAfter=16,
                                  textColor=(0.4, 0.4, 0.4)),
        "meta": ParagraphStyle("meta", fontSize=10, fontName="Helvetica", spaceAfter=20,
                               textColor=(0.3, 0.3, 0.3)),
        "body": ParagraphStyle("body", fontSize=10, fontName="Helvetica",
                               spaceAfter=12, leading=16),
    }

    story = []
    story.append(Paragraph(personal["name"], S["name"]))
    contact_line = f"{personal['email']}  |  {personal['phone']}  |  {personal['location']}"
    story.append(Paragraph(contact_line, S["contact"]))

    from datetime import date
    story.append(Paragraph(date.today().strftime("%B %d, %Y"), S["meta"]))
    story.append(Paragraph(f"Re: {title} — {company}", S["meta"]))

    for paragraph in text.split("\n\n"):
        para = paragraph.strip()
        if para:
            story.append(Paragraph(para, S["body"]))

    story.append(Spacer(1, 20))
    story.append(Paragraph("Sincerely,", S["body"]))
    story.append(Paragraph(personal["name"], S["body"]))

    doc.build(story)
    return path
