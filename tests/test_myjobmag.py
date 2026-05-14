from unittest.mock import patch, MagicMock
import pytest


SAMPLE_HTML = """
<html><body>
<div class="job-list-item">
  <h2 class="title"><a href="/job/123">Senior Python Developer</a></h2>
  <span class="company">Safaricom</span>
  <span class="location">Nairobi</span>
  <a class="apply-btn" href="https://myjobmag.co.ke/apply/123">Apply</a>
</div>
<div class="job-list-item">
  <h2 class="title"><a href="/job/456">Marketing Executive</a></h2>
  <span class="company">ACME</span>
  <span class="location">Mombasa</span>
  <a class="apply-btn" href="https://myjobmag.co.ke/apply/456">Apply</a>
</div>
</body></html>
"""


def test_run_returns_count():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = SAMPLE_HTML
    mock_resp.raise_for_status = MagicMock()

    with patch("app.scrapers.myjobmag.requests.get", return_value=mock_resp), \
         patch("app.scrapers.myjobmag.insert_job", return_value=1) as mock_insert:
        from app.scrapers import myjobmag
        count = myjobmag.run()
        assert count == 3
        assert mock_insert.called


def test_irrelevant_jobs_skipped():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = SAMPLE_HTML
    mock_resp.raise_for_status = MagicMock()

    with patch("app.scrapers.myjobmag.requests.get", return_value=mock_resp), \
         patch("app.scrapers.myjobmag.insert_job", return_value=1) as mock_insert:
        from app.scrapers import myjobmag
        myjobmag.run()
        calls = [str(c) for c in mock_insert.call_args_list]
        assert not any("Marketing" in c for c in calls)
