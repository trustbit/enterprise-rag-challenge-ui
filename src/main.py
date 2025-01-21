from fastapi import FastAPI, Form, HTTPException, UploadFile, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ValidationError, Field
from typing import Optional, List, Union
import json
import os
import re
import uuid
import time
import logging
from dotenv import load_dotenv

app = FastAPI()
load_dotenv()

# Logging
if os.getenv("DEVELOPMENT"):
    logger = logging.getLogger(__name__)
    logging.basicConfig(filename='temp/debug.log', encoding='utf-8', level=logging.INFO)

# Mount the static directory for serving CSS
app.mount("/static", StaticFiles(directory="src/static"), name="static")
templates = Jinja2Templates(directory="src/")

# In-memory submission storage
# TODO Just write to folder of json files
submissions_db = []
with open("src/static/questions.json", "r", encoding="utf-8") as file:
    true_questions = json.load(file)


class AnswerItem(BaseModel):
    question: Optional[str]
    schema: Optional[str]
    answer: Union[bool, int, float, str] = Field(..., description="Answer value, type depends on schema")

    class Config:
        extra = "forbid"  # Disallow unexpected fields, to also validate for typos in keys


class SubmissionSchema(BaseModel):
    team_name: str
    contact_mail_address: str  # TODO validate email address
    submission: List[AnswerItem]

    class Config:
        extra = "forbid"


def is_valid_email(email: str) -> bool:
    email_pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return re.match(email_pattern, email) is not None


def validate_answer_item(submission: SubmissionSchema) -> tuple[list, list]:
    issues_questions = []
    issues_schema = []
    for idx, (true_item, submission_item) in enumerate(zip(true_questions, submission.submission)):
        true_question = re.sub(r'[^A-Za-z0-9\s]', '', true_item["question"].lower())
        submitted_question = re.sub(r'[^A-Za-z0-9\s]', '', submission_item.question.lower())
        if true_question != submitted_question:
            issues_questions.append(
                f"\n - Submission item {idx}: Question mismatch: '{submission_item.question}' != '{true_item['question']}'")

        true_schema = true_item["schema"]
        submitted_schema = submission_item.schema
        if true_schema != submitted_schema:
            issues_schema.append(
                f"\n - Submission item {idx}: Schema mismatch: '{submission_item.schema}' != '{true_item['schema']}'")

    return issues_questions, issues_schema


def validate_answer(schema: Optional[str], answer: any) -> tuple[any, Optional[str]]:
    if answer is None:
        return "n/a", None
    if isinstance(answer, str) and answer.lower() in ["n/a", "na", "nan", ""]:
        return "n/a", None
    if schema == "number" and not isinstance(answer, (int, float)):
        try:
            return float(answer), None
        except ValueError:
            return answer, f"Expected a number for schema 'number', got: {type(answer).__name__}"
    if schema == "name" and not isinstance(answer, str):
        return answer, f"Expected text for schema 'name', got: {type(answer).__name__}"
    if schema == "boolean":
        if isinstance(answer, str) and answer.lower() in ["true", "yes"]:
            return True, None
        elif isinstance(answer, str) and answer.lower() in ["false", "no"]:
            return False, None
        elif not isinstance(answer, bool):
            return answer, f"Expected boolean for schema 'boolean', got: {type(answer).__name__}"
    return answer, None


def validate_submission(submission: SubmissionSchema) -> list:
    issues_questions = []
    issues_schema = []
    logger.info(f"CHECK_QUESTIONS: {os.getenv('CHECK_QUESTIONS')}")

    # checking email address
    if is_valid_email(submission.contact_mail_address):
        issue_email = []
    else:
        issue_email = ["\n - INVALID EMAIL ADDRESS! \n"]

    if os.getenv("CHECK_QUESTIONS") == "True":
        issues_questions, issues_schema = validate_answer_item(submission)
        if len(issues_questions) > 5:
            issues_questions = issues_questions[:5] + [
                f"\n - ... and {len(issues_questions) - 5} more question issue(s)"]
        if len(issues_schema) > 5:
            issues_schema = issues_schema[:5] + [
                f"\n - ... and {len(issues_schema) - 5} more schema issue(s)"]

    answer_issues = []
    for idx, item in enumerate(submission.submission):
        answer, issue = validate_answer(item.schema, item.answer)
        submission.submission[idx].answer = answer
        if issue:
            issue = f"\n - Submission item {idx}: {issue}"
            answer_issues.append(issue)

    return issue_email + issues_questions + issues_schema + answer_issues


def get_submission_schema(content: str | bytes) -> SubmissionSchema:
    try:
        data = json.loads(content)
        return SubmissionSchema(**data)
    except (json.JSONDecodeError, ValidationError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON or schema: {str(e)}")


def sign_with_timestamp_server(payload_bytes: bytes) -> str:
    """
    Mock signature. Replace this with a real TSP call if needed.
    e.g. using 'tsp-client' library:

        from tsp import TimeStampClient
        tsp_client = TimeStampClient("https://tsa.example.com")
        tsp_response = tsp_client.request_tsa(payload_bytes)
        return tsp_response.time_stamp_token.hex()  # or something similar
    """
    mock_hash = str(abs(hash(payload_bytes)))
    return mock_hash


def process_submission(submission: SubmissionSchema) -> dict:
    # TODO split into process and store submission functions
    """
    Processes a validated submission, generates a signature,
    and stores the submission in the database.
    """

    if os.getenv("DEVELOPMENT"): logging.info(f"Processing submission: {submission}")

    # Generate a signature
    submission_bytes = str(submission.model_dump()).encode("utf-8")
    signature = sign_with_timestamp_server(submission_bytes)

    # Build a record
    submission_id = str(uuid.uuid4())
    now_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    record = {
        "id": submission_id,
        "time": now_str,
        "signature": signature,
        "submission": submission.model_dump()["submission"],
    }
    submissions_db.append(record)

    return {
        "id": submission_id,
        "time": now_str,
        "signature": signature,
        # "submission": submission.model_dump()["submission"],
    }


@app.get("/", response_class=HTMLResponse)
async def serve_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/check-submission-ui")
async def check_submission(content: str = Form(...)):
    submission = get_submission_schema(content)
    issues = validate_submission(submission)
    if issues:
        return {"status": "issues found", "issues": issues}
    return {"status": "valid submission"}


@app.post("/check-submission")
async def check_submission(file: UploadFile):
    try:
        # Ensure the file is a JSON file
        if not file.filename.endswith('.json'):
            raise HTTPException(status_code=400, detail="Uploaded file must be a JSON file.")

        content = await file.read()
        submission = get_submission_schema(content)
        issues = validate_submission(submission)

        if issues:
            return {"status": "issues found", "issues": issues}
        else:
            return {"status": "valid submission",
                    "message": "No issues with submission file found. Ready to submit via /submit endpoint"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")


@app.post("/submit")
async def submit(file: UploadFile):
    try:
        # Ensure the file is a JSON file
        if not file.filename.endswith('.json'):
            raise HTTPException(status_code=400, detail="Uploaded file must be a JSON file.")

        content = await file.read()
        submission = get_submission_schema(content)
        issues = validate_submission(submission)  # Parse and validate form input
        response = process_submission(submission)

        if issues:
            return {"status": "issues found",
                    "message": "Successfully submitted! However, issues with submission file were detected. "
                               "Submit again with identical team name and contact mail address to overwrite this "
                               "submission.",
                    "issues": issues,
                    "response": response}
        else:
            return {"status": "success",
                    "message": "Successfully submitted! Verify on submissions table",
                    "response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")


@app.post("/submit-ui")
async def submit_ui(content: str = Form(...)):
    submission = get_submission_schema(content)
    issues = validate_submission(submission)
    response = process_submission(submission)
    if issues:
        return {"status": "issues found",
                "message": "Successfully submitted! However, issues with submission file were detected. "
                           "Submit again with identical team details to overwrite this submission.",
                "issues": issues,
                "response": response}
    else:
        return {"status": "success",
                "message": "Successfully submitted! Verify on submissions table",
                "response": response}


@app.get("/submissions")
def get_submissions():
    """
    Return all submissions as JSON so the frontend can dynamically
    load them and populate the table.
    """
    logger.info(f"SUBMISSIONS_DB: {submissions_db}")
    return JSONResponse(submissions_db)
