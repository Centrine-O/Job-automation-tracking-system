"""Gmail API email sender — sends job applications and detects replies."""
import base64
import json
import os
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
]

CREDENTIALS_PATH = Path("data/gmail_credentials.json")
TOKEN_PATH = Path("data/gmail_token.json")

SENDER_NAME = "Centrine Ong'aria"
SENDER_EMAIL = "centyanita@gmail.com"


def _get_service():
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_PATH.exists():
                raise FileNotFoundError(
                    f"Gmail credentials not found at {CREDENTIALS_PATH}. "
                    "Download from Google Cloud Console → APIs & Services → Credentials."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=8080, open_browser=False)
        TOKEN_PATH.write_text(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def _build_message(to: str, subject: str, body_text: str, attachments: list[str]) -> dict:
    msg = MIMEMultipart("mixed")
    msg["To"] = to
    msg["From"] = f"{SENDER_NAME} <{SENDER_EMAIL}>"
    msg["Subject"] = subject

    msg.attach(MIMEText(body_text, "plain"))

    for path_str in attachments:
        p = Path(path_str)
        if p.exists():
            with open(p, "rb") as f:
                part = MIMEApplication(f.read(), Name=p.name)
            part["Content-Disposition"] = f'attachment; filename="{p.name}"'
            msg.attach(part)

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return {"raw": raw}


def send_application(to: str, subject: str, cv_path: str, cover_letter_path: str) -> str:
    """Send a job application email with CV and cover letter as PDF attachments.
    Returns the sent message ID."""
    body_text = (
        f"Dear Hiring Team,\n\n"
        f"Please find attached my CV and cover letter for your consideration.\n\n"
        f"I look forward to hearing from you.\n\n"
        f"Best regards,\n"
        f"{SENDER_NAME}\n"
        f"{SENDER_EMAIL} | +254 712 382 443"
    )
    service = _get_service()
    message = _build_message(to, subject, body_text, [cv_path, cover_letter_path])
    sent = service.users().messages().send(userId="me", body=message).execute()
    return sent["id"]


def detect_replies(sent_message_ids: list[str]) -> list[dict]:
    """Check if any sent application emails have received replies.

    Returns list of dicts: {message_id, thread_id, snippet}
    """
    if not sent_message_ids:
        return []

    service = _get_service()
    replies = []

    for msg_id in sent_message_ids:
        try:
            msg = service.users().messages().get(
                userId="me", id=msg_id, format="metadata"
            ).execute()
            thread_id = msg.get("threadId")

            thread = service.users().threads().get(
                userId="me", id=thread_id
            ).execute()

            messages_in_thread = thread.get("messages", [])
            if len(messages_in_thread) > 1:
                latest = messages_in_thread[-1]
                if latest["id"] != msg_id:
                    replies.append({
                        "original_message_id": msg_id,
                        "reply_message_id": latest["id"],
                        "thread_id": thread_id,
                        "snippet": latest.get("snippet", ""),
                    })
        except HttpError:
            continue

    return replies
