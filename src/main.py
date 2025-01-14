#!/usr/bin/env python3

import json
import uuid
import time

from fastapi import FastAPI, Form, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from typing import Optional, List, Union
from pydantic import BaseModel, ValidationError, Field
import uvicorn

app = FastAPI()

# Mount the static directory for serving CSS
app.mount("/static", StaticFiles(directory="src/static"), name="static")

# In-memory submission storage
# TODO add a database connection here
submissions_db = []


class QuestionAnswer(BaseModel):
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
    data: List[QuestionAnswer]


def validate_submission(content_str: str) -> SubmissionSchema:
    """Validate the string as JSON, check schema constraints, etc."""
    try:
        data = json.loads(content_str)
        submission = SubmissionSchema(data=data)
    except (json.JSONDecodeError, ValidationError) as e:
        raise ValueError(f"Invalid JSON or schema: {e}")
    # TODO Extra custom checks:
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
def submit(content: str = Form(...), body: SubmissionSchema = Body(None)):
    """
    Submits data to the backend via a form or JSON.
    Validates, signs, and stores the submission.
    """
    if content:
        try:
            submission = validate_submission(content)
        except ValueError as e:
            return {"error": str(e)}
    elif body:
        # FIXME still not working via curl
        print(body)
        submission = body
    else:
        return {"error": "No input provided"}

    # Generate a signature
    submission_bytes = content.encode("utf-8")
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


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
