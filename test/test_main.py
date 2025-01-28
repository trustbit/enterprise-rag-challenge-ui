import pytest
from fastapi.testclient import TestClient
from src.main import app  # Adjust if your main file is named differently

client = TestClient(app)


@pytest.fixture
def valid_submission_json():
    """
    Returns a valid JSON submission (as dict) conforming to SubmissionSchema.
    """
    return {
        "team_name": "test-team",
        "contact_mail_address": "test@example.com",
        "submission": [
            {
                "question": "What was the Net Profit Margin of \"Oesterreichische Kontrollbank\" in June 30, 2023?",
                "schema": "number",
                "answer": 0.1243
            },
            {
                "question": "What was the total liabilities of \"CrossFirst Bank\" in the fiscal year 2023?",
                "schema": "number",
                "answer": 5992487000
            }
        ]
    }


def test_serve_index():
    """
    Ensure the GET / endpoint returns 200 and some HTML.
    """
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_check_submission_correct_json(valid_submission_json):
    """
    Test /check-submission with correct submission JSON file.
    """
    # # We can simulate file upload by passing (filename, file-like, content_type)
    # response = client.post(
    #     "/check-submission",
    #     files={"file": ("valid.json",
    #                     pytest.lazy_fixture('valid_submission_json'),
    #                     "application/json")}
    # )
    # # Note: Above, lazy_fixture won't directly serialize dict -> JSON.
    # # For test correctness, do:
    # # files={"file": ("valid.json", json.dumps(valid_submission_json), "application/json")}

    import json
    response = client.post(
        "/check-submission",
        files={"file": ("valid.json",
                        json.dumps(valid_submission_json),
                        "application/json")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "valid submission"


def test_check_submission_incorrect_filetype(valid_submission_json):
    """
    Test /check-submission with a non-.json file extension.
    """
    import json
    response = client.post(
        "/check-submission",
        files={"file": ("invalid.txt",
                        json.dumps(valid_submission_json),
                        "application/json")}
    )
    assert response.status_code == 400
    assert "must be a JSON file" in response.json()["detail"]


def test_check_submission_wrong_answer_type():
    """
    Send a submission where answer type doesn't match schema 'number'.
    Should detect issues about incorrect answer type.
    """
    invalid_submission = {
        "team_name": "test-team",
        "contact_mail_address": "test@example.com",
        "submission": [
            {
                "question": "What was the Net Profit Margin of \"Oesterreichische Kontrollbank\" in June 30, 2023?",
                "schema": "number",
                "answer": "not-a-number"
            }
        ]
    }
    import json
    response = client.post(
        "/check-submission",
        files={"file": ("invalid.json",
                        json.dumps(invalid_submission),
                        "application/json")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "issues found"
    assert any("Expected a number" in issue for issue in data["issues"])


def test_check_submission_wrong_schema_key():
    """
    Modify 'submission' list with a key that doesn't exist in the pydantic model.
    This should raise a ValidationError (extra fields not allowed).
    """
    invalid_submission = {
        "team_name": "test-team",
        "contact_mail_address": "test@example.com",
        "submission": [
            {
                "question": "An existing question?",
                "schem": "number",  # invalid key
                "answer": 123,
            }
        ]
    }
    import json
    response = client.post(
        "/check-submission",
        files={"file": ("invalid.json",
                        json.dumps(invalid_submission),
                        "application/json")}
    )
    assert response.status_code == 400
    # Check that the detail mentions "Invalid JSON or schema"
    # or "extra fields not allowed"
    detail_msg = response.json()["detail"]
    assert "extra fields not allowed" in detail_msg or "Invalid JSON or schema" in detail_msg


def test_check_submission_invalid_email(valid_submission_json):
    """
    Provide an invalid email format. Should detect an email issue.
    """
    invalid_email_submission = valid_submission_json.copy()
    invalid_email_submission["contact_mail_address"] = "invalid-email-format"
    import json
    response = client.post(
        "/check-submission",
        files={"file": ("invalid_email.json",
                        json.dumps(invalid_email_submission),
                        "application/json")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "issues found"
    assert any("INVALID EMAIL ADDRESS" in issue for issue in data["issues"])


def test_submit_valid_submission(valid_submission_json):
    """
    Test /submit with a valid submission. It should return a success or partial success if issues were found.
    """
    import json
    response = client.post(
        "/submit",
        files={"file": ("valid.json",
                        json.dumps(valid_submission_json),
                        "application/json")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["success", "issues found"]
    # Should return a response ID and signature
    assert "response" in data
    assert "signature" in data["response"]
    assert "tsp_verification_data" in data["response"]


def test_submissions_list_after_submit(valid_submission_json):
    """
    Submit once and check if that new submission is in /submissions result.
    """
    import json
    # Clear or not? In-memory DB can't be easily cleared here, so we rely on the global state.
    # We'll at least check that the last submission is appended.

    # Submit
    submit_response = client.post(
        "/submit",
        files={"file": ("valid.json", json.dumps(valid_submission_json), "application/json")}
    )
    submit_data = submit_response.json()
    assert submit_response.status_code == 200
    assert "tsp_verification_data" in submit_data["response"]

    # Now get /submissions
    get_response = client.get("/submissions")
    assert get_response.status_code == 200
    submissions_list = get_response.json()
    last_id = submit_data["response"]["signature"]
    assert any(s["signature"] == last_id for s in submissions_list), \
        "Expected newly submitted id to be in the submissions list."
