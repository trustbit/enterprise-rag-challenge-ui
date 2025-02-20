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
from typing import Optional, List, Union, Literal
from tsp_client import TSPSigner, TSPVerifier, SigningSettings
from dotenv import load_dotenv

# TODO set env variables!
# TODO update URL in index.html to actual API domain

app = FastAPI()
load_dotenv()
DEV = os.getenv("DEVELOPMENT")

if DEV:
    logger = logging.getLogger(__name__)
    if not os.path.exists('temp'):
        os.makedirs('temp')
    logging.basicConfig(filename='temp/debug.log', encoding='utf-8', level=logging.INFO)

app.mount("/static", StaticFiles(directory="src/static"), name="static")
templates = Jinja2Templates(directory="src/")

with open(os.getenv("CORRECT_QUESTIONS_PATH"), "r", encoding="utf-8") as f:
    true_questions = json.load(f)


class SourceReference(BaseModel):
    model_config = ConfigDict(extra='ignore')

    pdf_sha1: str = Field(..., description="SHA1 hash of the PDF file")
    page_index: int = Field(..., description="Physical page number in the PDF file")


class Answer(BaseModel):
    model_config = ConfigDict(extra='ignore')

    question_text: Optional[str] = Field(None, description="Text of the question")
    kind: Optional[Literal["number", "name", "boolean", "names"]] = Field(None, description="Kind of the question")
    value: Union[float, str, bool, List[str], Literal["N/A"]] = (
        Field(..., description="Answer to the question, according to the question schema"))
    references: List[SourceReference] = Field([], description="References to the source material in the PDF file")


class AnswerSubmission(BaseModel):
    model_config = ConfigDict(extra='ignore')

    team_email: str = Field(..., description="Email that your team used to register for the challenge")
    submission_name: str = Field(..., description="Unique name of the submission (e.g. experiment name)")
    answers: List[Answer] = Field(...,
                                  description="List of answers to the questions",
                                  max_length=int(os.getenv("MAX_NR_OF_QUESTIONS")))


def is_valid_email(email: str) -> bool:
    email_pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return re.match(email_pattern, email) is not None


def validate_answer_item(submission: AnswerSubmission) -> tuple[list, list]:
    issues_questions = []
    issues_kind = []
    questions_missing, kinds_missing = False, False
    for idx, (true_item, submission_item) in enumerate(zip(true_questions, submission.answers)):
        if submission_item.question_text:
            true_question = re.sub(r'[^A-Za-z0-9\s]', '', true_item["text"].lower())
            submitted_question = re.sub(r'[^A-Za-z0-9\s]', '', submission_item.question_text.lower())
            if true_question != submitted_question:
                issues_questions.append(
                    f"\n - Question mismatch (index {idx}): '{submission_item.question_text}' != '{true_item['text']}'")
        else:
            questions_missing = True

        # if submission_item.kind:
        #     true_kind = true_item["kind"]
        #     submitted_kind = submission_item.kind
        #     if true_kind != submitted_kind:
        #         issues_kind.append(
        #             f"\n - Kind mismatch (index {idx}): '{submission_item.kind}' != '{true_item['kind']}'")
        # else:
        #     kinds_missing = True

    if questions_missing:
        issues_questions.insert(0, "\n - Missing question_text. To validate that answers are in correct order like in "
                                "questions.json and aligned with correct answers, consider also adding 'question_text' "
                                "to the answer items.")
    # if kinds_missing:
    #     issues_kind.append("\n - Missing kind. To validate answers kind corresponding to questions, consider "
    #                        "also adding 'kind' to the answer items.")

    return issues_questions, issues_kind


def validate_answer(kind: Optional[str], answer: any) -> tuple[any, Optional[str]]:
    if answer is None:
        return "N/A", None
    if isinstance(answer, str) and answer.lower() in ["n/a", "na", "nan", ""]:
        return "N/A", None
    if kind == "number" and not isinstance(answer, (int, float)):
        for convert_fn in (int, float):
            try:
                return convert_fn(answer), None
            except ValueError:
                continue
        try:
            return float(answer.replace(",", ".")), None
        except ValueError:
            pass
        return answer, f"Expected a number for kind 'number', got: '{answer}' ({type(answer).__name__})"
    if kind == "name" and not isinstance(answer, str):
        return answer, f"Expected text for kind 'name', got: '{answer}' ({type(answer).__name__})"
    if kind == "boolean":
        if isinstance(answer, str) and answer.lower() in ["true", "yes"]:
            return True, None
        elif isinstance(answer, str) and answer.lower() in ["false", "no"]:
            return False, None
        elif not isinstance(answer, bool):
            return answer, f"Expected boolean for kind 'boolean', got: '{answer}' ({type(answer).__name__})"
    return answer, None


def validate_submission(submission: AnswerSubmission) -> list:
    issues_questions = []
    issues_kind = []
    if DEV: logger.info(f"CHECK_QUESTIONS: {os.getenv('CHECK_QUESTIONS')}")

    # checking email address
    if is_valid_email(submission.team_email):
        issue_email = []
    else:
        issue_email = ["\n - INVALID EMAIL ADDRESS! \n"]

    if os.getenv("CHECK_QUESTIONS") == "True":
        issues_questions, issues_kind = validate_answer_item(submission)
        if len(issues_questions) > 3:
            issues_questions = issues_questions[:3] + [
                f"\n - ... and {len(issues_questions) - 3} more question issue(s)"]
        if len(issues_kind) > 3:
            issues_kind = issues_kind[:3] + [
                f"\n - ... and {len(issues_kind) - 3} more kind issue(s)"]

    issues_answers = []
    for idx, item in enumerate(submission.answers):
        corrected_value, issue = validate_answer(item.kind, item.value)
        submission.answers[idx].value = corrected_value
        if issue:
            issue = f"\n - Answer index {idx}: {issue}"
            issues_answers.append(issue)

    if len(issues_answers) > 3:
        issues_answers = issues_answers[:3] + [
            f"\n - ... and {len(issues_answers) - 3} more answer issue(s)"]

    return issue_email + issues_questions + issues_kind + issues_answers


def get_submission_schema(content: str | bytes) -> AnswerSubmission:
    try:
        if len(content) > int(os.getenv("MAX_JSON_SIZE")):
            raise HTTPException(status_code=413,
                                detail=f"JSON payload too large. Max size is {os.getenv('MAX_JSON_SIZE')} bytes.")

        data = json.loads(content)
        return AnswerSubmission(**data)
    except (json.JSONDecodeError, ValidationError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON or schema: {str(e)}")


def sign_with_tsp_server(submission: AnswerSubmission) -> [str, str, str]:
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


def store_submission(submission: AnswerSubmission, signature: str, tsp_signature: str, digest: str, timestamp: str):
    """Store a submission record as JSON locally in SUBMISSIONS_PATH."""
    record = {
        "submission_name": submission.submission_name,
        "team_email": submission.team_email,
        "time": timestamp,
        "signature": signature,
        "tsp_signature": tsp_signature,
        "submission_digest": digest,
        "answers": submission.model_dump()["answers"],
    }
    clean_timestamp = timestamp.replace(":", "-").replace(", ", "-")

    with open(os.path.join(os.getenv("SUBMISSIONS_PATH"), f"{clean_timestamp}_{record['signature'][:64]}.json"), "w",
              encoding="utf-8") as f:
        json.dump(record, f, indent=4)


def process_submission(submission: AnswerSubmission) -> dict:
    """Generates a signature and stores the submission in the database."""
    tsp_signature, submission_digest, timestamp = sign_with_tsp_server(submission)
    signature = hashlib.sha256(tsp_signature.encode("utf-8")).hexdigest()[:64]
    store_submission(submission, signature, tsp_signature, submission_digest, timestamp)
    return {
        "submission_name": submission.submission_name,
        "time": timestamp,
        "signature": signature,  # only publish first 64 characters
        "tsp_verification_data": {"timestamp": timestamp, "submission_digest": submission_digest,
                                  "tsp_signature": tsp_signature, "submission": str(submission.model_dump())},
    }


@app.get("/", response_class=HTMLResponse)
async def serve_index(request: Request):
    return templates.TemplateResponse(request, "index.html")


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


@app.post("/check-submission-ui")
async def check_submission(content: str = Form(...)):
    submission = get_submission_schema(content)
    issues = validate_submission(submission)
    if issues:
        return {"status": "issues found", "issues": issues}
    return {"status": "valid submission"}


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
                               "submission_name and team_email to overwrite this submission. Verify submission on "
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
                           "Consider submitting again adhering to the submission guidelines. Use the identical "
                           "submission_name and team_email to overwrite this submission.",
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
            submission = {k: v for k, v in submission.items() if k in ["time", "submission_name", "signature"]}
            submissions_db.append(submission)
    submissions_db = sorted(submissions_db, key=lambda x: x["time"], reverse=True)
    return JSONResponse(submissions_db)
