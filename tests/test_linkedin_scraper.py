from unittest.mock import patch, MagicMock
import pytest


SAMPLE_RESPONSE = {
    "jobs_results": [
        {
            "title": "Senior Data Engineer",
            "company_name": "Safaricom",
            "location": "Nairobi, Kenya",
            "description": "We need a Python data engineer with 5+ years experience...",
            "apply_options": [{"link": "https://linkedin.com/jobs/view/123"}],
            "job_id": "linkedin_123",
        },
        {
            "title": "Sales Manager",
            "company_name": "ACME",
            "location": "Nairobi",
            "description": "Looking for a sales manager...",
            "apply_options": [{"link": "https://linkedin.com/jobs/view/456"}],
            "job_id": "linkedin_456",
        },
    ]
}


def test_run_returns_count():
    mock_resp = MagicMock()
    mock_resp.json.return_value = SAMPLE_RESPONSE
    mock_resp.raise_for_status = MagicMock()

    with patch("app.scrapers.linkedin.requests.get", return_value=mock_resp), \
         patch("app.scrapers.linkedin.settings.serpapi_key", "TESTKEY"), \
         patch("app.scrapers.linkedin.insert_job", side_effect=[1, 0, 0, 0, 0, 0]) as mock_insert:
        from app.scrapers import linkedin
        count = linkedin.run()
        assert count == 1  # only "Senior Data Engineer" is relevant, detected as duplicate on retries
        assert mock_insert.called


def test_irrelevant_jobs_skipped():
    mock_resp = MagicMock()
    mock_resp.json.return_value = SAMPLE_RESPONSE
    mock_resp.raise_for_status = MagicMock()

    with patch("app.scrapers.linkedin.requests.get", return_value=mock_resp), \
         patch("app.scrapers.linkedin.settings.serpapi_key", "TESTKEY"), \
         patch("app.scrapers.linkedin.insert_job", return_value=1) as mock_insert:
        from app.scrapers import linkedin
        linkedin.run()
        calls = [str(c) for c in mock_insert.call_args_list]
        assert not any("Sales Manager" in c for c in calls)


def test_skips_when_no_key():
    with patch("app.scrapers.linkedin.settings.serpapi_key", ""), \
         patch("app.scrapers.linkedin.requests.get") as mock_get:
        from app.scrapers import linkedin
        count = linkedin.run()
        assert count == 0
        assert not mock_get.called
