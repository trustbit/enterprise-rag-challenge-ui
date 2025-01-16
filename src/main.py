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


class SubmissionSchema(BaseModel):
    data: List[AnswerItem]


def validate_questions(submission: SubmissionSchema):
    issues = []
    for idx, (true_item, submission_item) in enumerate(zip(true_questions, submission.data)):
        true = re.sub(r'[^A-Za-z0-9\s]', '', true_item["question"].lower())
        submitted = re.sub(r'[^A-Za-z0-9\s]', '', submission_item.question.lower())
        if true != submitted:
            issues.append(f"\n - List item {idx + 1}: Question mismatch: '{submission_item.question}' != '{true_item['question']}'")
    return issues


def validate_answer(schema: Optional[str], answer: any):
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


def validate_submission(content: str | bytes):
    try:
        data = json.loads(content)
        submission = SubmissionSchema(data=data)
        question_issues = []
        logger.info(f"CHECK_QUESTIONS: {os.getenv('CHECK_QUESTIONS')}")

        if os.getenv("CHECK_QUESTIONS") == "True":
            question_issues = validate_questions(submission)
            if len(question_issues) > 5:
                question_issues = question_issues[:5] + [f"\n - ... and {len(question_issues) - 5} more question issue(s)"]

        answer_issues = []
        for idx, item in enumerate(submission.data):
            answer, issue = validate_answer(item.schema, item.answer)
            submission.data[idx].answer = answer
            if issue:
                issue = f"\n - List item {idx + 1}: {issue}"
                answer_issues.append(issue)

        return question_issues + answer_issues

    except (json.JSONDecodeError, ValidationError) as e:
        return [f"Invalid JSON or schema: {str(e)}"]


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
        "data": submission.model_dump()["data"],
    }
    submissions_db.append(record)

    return {
        "message": "Submission stored successfully",
        "id": submission_id,
        "signature": signature,
        "time": now_str,
        # "data": submission.model_dump()["data"],
    }


@app.get("/", response_class=HTMLResponse)
async def serve_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/check-submission")
async def check_submission(content: str = Form(...)):
    issues = validate_submission(content)
    if issues:
        return {"status": "issues", "issues": issues}
    return {"status": "valid"}


@app.post("/submit")
async def submit(file: UploadFile):
    try:
        # Ensure the file is a JSON file
        if not file.filename.endswith('.json'):
            raise HTTPException(status_code=400, detail="Uploaded file must be a JSON file.")

        # Read the uploaded file
        content = await file.read()

        submission = validate_submission(content)  # Parse and validate form input
        response = process_submission(submission)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")


@app.post("/submit-ui")
async def submit_ui(content: str = Form(...)):
    issues = validate_submission(content)
    if issues:
        return {"status": "issues", "issues": issues}
    submission = SubmissionSchema(data=json.loads(content))
    response = process_submission(submission)
    return {"status": "success", "message": response}


@app.get("/submissions")
def get_submissions():
    """
    Return all submissions as JSON so the frontend can dynamically
    load them and populate the table.
    """
    logger.info(f"SUBMISSIONS_DB: {submissions_db}")
    return JSONResponse(submissions_db)
