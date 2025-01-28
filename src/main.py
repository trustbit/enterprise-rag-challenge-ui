import json
import os
import re
import logging
import hashlib
from fastapi import FastAPI, Form, HTTPException, UploadFile, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ValidationError, Field, ConfigDict
from typing import Optional, List, Union
from tsp_client import TSPSigner, TSPVerifier, SigningSettings
from dotenv import load_dotenv

# TODO set env variables!

app = FastAPI()
load_dotenv()
DEV = os.getenv("DEVELOPMENT")

if DEV:
    logger = logging.getLogger(__name__)
    logging.basicConfig(filename='temp/debug.log', encoding='utf-8', level=logging.INFO)

app.mount("/static", StaticFiles(directory="src/static"), name="static")
templates = Jinja2Templates(directory="src/")

if DEV:
    pass
    # delete current json files
    # for file in os.listdir("submissions"):
    #     os.remove(f"submissions/{file}")

with open(os.getenv("CORRECT_QUESTIONS_PATH"), "r", encoding="utf-8") as f:
    true_questions = json.load(f)


class AnswerItem(BaseModel):
    model_config = ConfigDict(extra='forbid')  # Disallow unexpected fields, to also validate for typos in keys
    question: Optional[str]
    schema: Optional[str]
    answer: Union[bool, int, float, str] = Field(..., description="Answer value, type depends on schema")


class SubmissionSchema(BaseModel):
    model_config = ConfigDict(extra='forbid')
    team_name: str
    contact_mail_address: str
    submission: List[AnswerItem]


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
            return answer, f"Expected a number for schema 'number', got: '{answer}' ({type(answer).__name__})"
    if schema == "name" and not isinstance(answer, str):
        return answer, f"Expected text for schema 'name', got: '{answer}' ({type(answer).__name__})"
    if schema == "boolean":
        if isinstance(answer, str) and answer.lower() in ["true", "yes"]:
            return True, None
        elif isinstance(answer, str) and answer.lower() in ["false", "no"]:
            return False, None
        elif not isinstance(answer, bool):
            return answer, f"Expected boolean for schema 'boolean', got: '{answer}' ({type(answer).__name__})"
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
        if len(issues_questions) > 3:
            issues_questions = issues_questions[:3] + [
                f"\n - ... and {len(issues_questions) - 3} more question issue(s)"]
        if len(issues_schema) > 3:
            issues_schema = issues_schema[:3] + [
                f"\n - ... and {len(issues_schema) - 3} more schema issue(s)"]

    issues_answers = []
    for idx, item in enumerate(submission.submission):
        answer, issue = validate_answer(item.schema, item.answer)
        submission.submission[idx].answer = answer
        if issue:
            issue = f"\n - Submission item {idx}: {issue}"
            issues_answers.append(issue)

    if len(issues_answers) > 3:
        issues_answers = issues_answers[:3] + [
            f"\n - ... and {len(issues_answers) - 3} more answer issue(s)"]

    return issue_email + issues_questions + issues_schema + issues_answers


def get_submission_schema(content: str | bytes) -> SubmissionSchema:
    try:
        data = json.loads(content)
        return SubmissionSchema(**data)
    except (json.JSONDecodeError, ValidationError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON or schema: {str(e)}")


def sign_with_tsp_server(submission: SubmissionSchema) -> [str, str, str]:
    """
    Mock signature. Replace this with a real TSP call if needed.
    e.g. using 'tsp-client' library:

        from tsp import TimeStampClient
        tsp_client = TimeStampClient("https://tsp.example.com")
        tsp_response = tsp_client.request_tsp(payload_bytes)
        return tsp_response.time_stamp_token.hex()  # or something similar
    """
    submission_bytes = str(submission.model_dump()).encode("utf-8")
    digest = hashlib.sha512(submission_bytes).digest()

    signer = TSPSigner()
    if os.getenv("TSP_URL"):
        if DEV: logger.info("Signing with specified TSP server...")
        signing_settings = SigningSettings(tsp_server=os.getenv("TSP_URL"))
        signature = signer.sign(message_digest=digest, signing_settings=signing_settings)
    else:
        if DEV: logger.info("Signing with default TSP server...")
        signature = signer.sign(message_digest=digest)

    verified = TSPVerifier().verify(signature, message_digest=digest)
    if DEV:
        logger.info("Signature verification:")
        logger.info(verified.tst_info)  # Parsed TSTInfo (CMS SignedData) structure
        logger.info("")
        logger.info(verified.signed_attrs)  # Parsed CMS SignedAttributes structure

    return signature.hex(), digest.hex(), verified.tst_info["gen_time"].strftime("%Y-%m-%d, %H:%M:%S")


def store_submission(submission: SubmissionSchema, signature: str, tsp_signature: str, digest: str, timestamp: str):
    """
    Store a submission record as JSON locally in SUBMISSIONS_PATH.
    """
    record = {
        "team_name": submission.team_name,
        "contact_mail_address": submission.contact_mail_address,
        "time": timestamp,
        "signature": signature,  # sha256 of tsp signature
        "tsp_signature": tsp_signature,
        "submission_digest": digest,
        "submission": submission.model_dump()["submission"],
    }

    with open(os.path.join(os.getenv("SUBMISSIONS_PATH"), f"{record['signature'][:64]}.json"), "w", encoding="utf-8") as f:
        json.dump(record, f, indent=4)


def process_submission(submission: SubmissionSchema) -> dict:
    # TODO split into process and store submission functions
    """
    Processes a validated submission, generates a signature,
    and stores the submission in the database.
    """

    # Generate a signature
    tsp_signature, digest, timestamp = sign_with_tsp_server(submission)
    signature = hashlib.sha256(tsp_signature.encode("utf-8")).hexdigest()

    # metadata = {"tsp_server": os.getenv("TSP_URL"), "hash_algorithm": "SHA-512", "string_encoding": "hexadecimal",
    # UTC time}

    store_submission(submission, signature, tsp_signature, digest, timestamp)

    return {
        "team_name": submission.team_name,
        "time": timestamp,
        "signature": signature[:64],  # only publish first 64 characters
        "tsp_signature": tsp_signature,
        "tsp_verification_data": {"timestamp": timestamp, "digest": digest, "tsp_signature": tsp_signature,
                                  "submission": str(submission.model_dump())},
        # "submission": submission.model_dump()["submission"],
    }


@app.get("/", response_class=HTMLResponse)
async def serve_index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.post("/check-submission-ui")
async def check_submission(content: str = Form(...)):
    submission = get_submission_schema(content)
    issues = validate_submission(submission)
    if issues:
        return {"status": "issues found", "issues": issues}
    return {"status": "valid submission"}


@app.post("/check-submission")
async def check_submission(file: UploadFile):
    if not file.filename.endswith('.json'):
        raise HTTPException(status_code=400, detail="Uploaded file must be a JSON file.")
    try:
        content = await file.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

    submission = get_submission_schema(content)
    issues = validate_submission(submission)

    if issues:
        return {"status": "issues found", "issues": issues}
    else:
        return {"status": "valid submission",
                "message": "No issues with submission file found. Ready to submit via /submit endpoint"}


@app.post("/submit")
async def submit(file: UploadFile):
    if not file.filename.endswith('.json'):
        raise HTTPException(status_code=400, detail="Uploaded file must be a JSON file.")
    try:
        content = await file.read()
        submission = get_submission_schema(content)
        issues = validate_submission(submission)  # Parse and validate form input
        response = process_submission(submission)

        if issues:
            return {"status": "issues found",
                    "message": "Successfully submitted! However, issues with submission file were detected. "
                               "Consider submitting again adhering to the submission guidelines. Use the identical "
                               "team name and mail address to overwrite this submission. Verify submission on "
                               "submissions table and/or with TSP!",
                    "issues": issues,
                    "response": response}
        else:
            return {"status": "success",
                    "message": "Successfully submitted! Verify on submissions table and/or with TSP!",
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
                           "Consider submitting again adhering to the submission guidelines. Use the identical team "
                           "name and mail address to overwrite this submission.",
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
    submissions_db = []
    files = os.listdir(os.getenv("SUBMISSIONS_PATH"))

    for file in files:
        with open(os.path.join(os.getenv("SUBMISSIONS_PATH"), file), "r", encoding="utf-8") as f:
            submission = json.load(f)
            # TODO update which variables should be sent to frontend for data security and efficiency
            submission = {k: v for k, v in submission.items() if k in ["time", "team_name", "signature"]}
            submissions_db.append(submission)
    submissions_db = sorted(submissions_db, key=lambda x: x["time"], reverse=True)
    return JSONResponse(submissions_db)
