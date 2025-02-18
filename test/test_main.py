import json
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
        "team_email": "test@rag-tat.com",
        "submission_name": "test-team",
        "answers": [
            {
                "question_text": "What was the Net Profit Margin of \"Oesterreichische Kontrollbank\" in June 30, 2023?",
                "kind": "number",
                "value": 0.1243,
                "references": []
            },
            {
                "question_text": "What was the total liabilities of \"CrossFirst Bank\" in the fiscal year 2023?",
                "kind": "number",
                "value": 5992487000,
                "references": []
            },
            {
                "question_text": "How much more did \"Astral Resources NL\" spend on marketing compared to \"TSX_Y\" in June 30, 2021?",
                "kind": "number",
                "value": "N/A",
                "references": []
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
        "team_email": "test@rag-tat.com",
        "submission_name": "test-team",
        "answers": [
            {
                "question_text": "What was the Net Profit Margin of \"Oesterreichische Kontrollbank\" in June 30, 2023?",
                "kind": "number",
                "value": "not-a-number",
                "references": []
            }
        ]
    }

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
        "team_email": "test@rag-tat.com",
        "submission_name": "test-team",
        "answers": [
            {
                "question_text": "What was the Net Profit Margin of \"Oesterreichische Kontrollbank\" in June 30, 2023?",
                "kind": "number",
                "value": "not-a-number",
                "references": []
            }
        ]
    }

    response = client.post(
        "/check-submission",
        files={"file": ("invalid.json",
                        json.dumps(invalid_submission),
                        "application/json")}
    )
    print()
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "issues found"
    assert any("expected a number" in issue.lower() for issue in data["issues"])


def test_check_submission_invalid_email(valid_submission_json):
    """
    Provide an invalid email format. Should detect an email issue.
    """
    invalid_email_submission = valid_submission_json.copy()
    invalid_email_submission["team_email"] = "invalid-email-format"

    response = client.post(
        "/check-submission",
        files={"file": ("invalid_email.json",
                        json.dumps(invalid_email_submission),
                        "application/json")}
    )
    print("######")
    print(response.json())
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "issues found"
    assert any("INVALID EMAIL ADDRESS" in issue for issue in data["issues"])


def test_submit_valid_submission(valid_submission_json):
    """
    Test /submit with a valid submission. It should return a success or partial success if issues were found.
    """
    response = client.post(
        "/submit",
        files={"file": ("valid.json",
                        json.dumps(valid_submission_json),
                        "application/json")}
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] in ["success", "issues found"], data
    # Should return a response ID and signature
    assert "response" in data
    assert "signature" in data["response"]
    assert "tsp_verification_data" in data["response"]


def test_submissions_list_after_submit(valid_submission_json):
    """
    Submit once and check if that new submission is in /submissions result.
    """

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
