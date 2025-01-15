import json
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_get_index():
    """
    Ensure the index page returns status 200 and contains some expected text.
    """
    response = client.get("/")
    assert response.status_code == 200
    # Since we're serving a static HTML file, we can check if a known substring is present
    assert "Submission API Usage" in response.text


def test_get_submissions_empty():
    """
    Initially, the submissions list should be empty.
    """
    response = client.get("/submissions")
    assert response.status_code == 200
    assert response.json() == []


def test_submit_valid():
    """
    Test a valid submission, check the response data,
    then ensure the new submission appears in /submissions.
    """
    payload = [
        {"question": "Q1", "schema": "name", "answer": "A1"},
        {"question": "Q2", "schema": "number", "answer": 2.5},
        {"question": "Q2", "schema": "boolean", "answer": True}
    ]

    response = client.post(
        "/submit-ui",
        data={"content": json.dumps(payload)}  # mimics form data with JSON
    )
    assert response.status_code == 200
    result = response.json()
    assert "id" in result
    assert "signature" in result
    assert "time" in result
    assert "data" in result
    assert result["data"] == payload

    # Now check /submissions to see if it's stored
    submissions_resp = client.get("/submissions")
    subs = submissions_resp.json()
    assert len(subs) == 1
    assert subs[0]["data"] == payload


def test_submit_invalid():
    """
    Test submission with invalid data (e.g. negative age).
    The API should return an error.
    """
    invalid_payload = {"name": "InvalidUser", "age": -1}
    response = client.post(
        "/submit-ui",
        data={"content": json.dumps(invalid_payload)}
    )
    assert response.status_code == 400
    result = response.json()
    assert "Invalid form data" in str(result)
    # TODO check for specific use cases
    # assert "Age must be a positive integer" in result["error"]
