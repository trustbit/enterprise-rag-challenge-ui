#!/usr/bin/env python3

import os
import json
import uuid
import time
import logging
from dotenv import load_dotenv

from fastapi import FastAPI, Form, Body, Request, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from typing import Optional, List, Union
from pydantic import BaseModel, ValidationError, Field
import uvicorn

app = FastAPI()
load_dotenv()

# Logging
if os.getenv("DEVELOPMENT"):
    logger = logging.getLogger(__name__)
    logging.basicConfig(filename='temp/debug.log', encoding='utf-8', level=logging.INFO)


# Mount the static directory for serving CSS
app.mount("/static", StaticFiles(directory="src/static"), name="static")

# In-memory submission storage
# TODO add a database connection here
submissions_db = []


class AnswerItem(BaseModel):
    question: Optional[str]
    schema: Optional[str]
    answer: Union[bool, int, float, str] = Field(..., description="Answer value, type depends on schema")

    @staticmethod
    def validate_answer(schema: Optional[str], answer: any):
        # TODO think about how to handle schema deviations (reject submission, try to fix it first)
        if answer is None:
            return 1
        if isinstance(answer, str):
            if answer.lower() == "n/a" or answer == "" or answer.lower == "na":
                return 1
        else:
            if schema == "number" and not isinstance(answer, (int, float)):
                raise ValueError(f"Expected a number for schema 'number', got: {type(answer).__name__}")
            if schema == "name" and not isinstance(answer, str):
                raise ValueError(f"Expected text for schema 'text', got: {type(answer).__name__}")
            if schema == "boolean" and not isinstance(answer, bool):
                # TODO handle boolean case (True vs. true, yes/no case)
                raise ValueError(f"Expected text for schema 'text', got: {type(answer).__name__}")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.validate_answer(self.schema, self.answer)


class SubmissionSchema(BaseModel):
    data: List[AnswerItem]


def validate_submission(content_str: str | bytes) -> SubmissionSchema:
    """Validate the string as JSON, check schema constraints, etc."""
    try:
        data = json.loads(content_str)
        submission = SubmissionSchema(data=data)
    except (json.JSONDecodeError, ValidationError) as e:
        raise ValueError(f"Invalid JSON or schema: {e}")
    return submission


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
        "message": "Submission stored",
        "id": submission_id,
        "signature": signature,
        "time": now_str,
        "data": submission.model_dump()["data"],
    }


@app.get("/")
def serve_index():
    """Return the main HTML page."""
    return FileResponse("src/index.html")


@app.get("/submissions")
def get_submissions():
    """
    Return all submissions as JSON so the frontend can dynamically
    load them and populate the table.
    """
    return JSONResponse(submissions_db)


# TODO instead of json return, show fail/success in UI
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
def submit_ui(content: str = Form(...)):
    """
    Endpoint for submitting data via an HTML form.
    """
    try:
        submission = validate_submission(content)  # Parse and validate form input
        response = process_submission(submission)
        return response
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid form data: {str(e)}")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
