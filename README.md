# Enterprise RAG Challenge UI & Submission Handling

Codebase for the Submission API and UI for the TIMETOACT 
[Enterprise RAG Challenge](https://www.timetoact-group.at/details/enterprise-rag-challenge) 
taking place on 27th of February 2025.

![UI_sample_image.png](UI_sample_image.png)

## Before you start
Specify necessary variables in the [`.env`](.env) file and adapt to needs.

Adapt URL in [index.html](src/index.html) to actual API domain.



## Getting Started
### Locally
Install dependencies (preferably in a virtual environment)
```bash
pip install -r requirements.txt
```

Run the app
```bash
python -m uvicorn src.main:app --reload
```

### With Docker
Build docker image
```bash
docker build -t rag_challenge .
```

Run docker container
```bash
docker run -d -p 8000:8000 rag_challenge
```


## Test submission with curl

### Test UI submission (string)

```bash
curl -X 'POST' \
  'http://127.0.0.1:8000/submit-ui' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'content=%5B%7B%22question%22%3A%22Q1%22%2C%22schema%22%3A%22name%22%2C%22answer%22%3A%22A1%22%7D%2C%7B%22question%22%3A%22Q2%22%2C%22schema%22%3A%22number%22%2C%22answer%22%3A2.5%7D%2C%7B%22question%22%3A%22Q2%22%2C%22schema%22%3A%22boolean%22%2C%22answer%22%3Atrue%7D%5D'
```

### Test json file submission

```bash
curl -X 'POST' \
  'http://127.0.0.1:8000/submit' \
  -H 'accept: application/json' \
  -H 'Content-Type: multipart/form-data' \
  -F 'file=@test/samples/sample_answer.json;type=application/json'
```

### Test submission data check and submission with python

Run the file [`submit_via_API.py`](submit_via_API.py).

### Run unittests
Note, that running the tests will generate two submissions, which will 
be stored in the specified path 

```bash
pytest
```


## Schema

```json
{
  "team_email": "test@rag-tat.com",
  "submission_name": "test-team",
  "answers": [
    {
      "question_text": "What was the Net Profit Margin of \"Oesterreichische Kontrollbank\" in June 30, 2023?",
      "kind": "number",
      "value": 0.1243,
      "references": [
        {
            "pdf_sha1": "053b7cb83115789346e2a9efc7e2e640851653ff",
            "page_index": 3
        }
      ]
    },
    {
      "question_text": "What was the total liabilities of \"CrossFirst Bank\" in the fiscal year 2023?",
      "kind": "number",
      "value": 5992487000,
      "references": []
    },
    
  ]
}
```

Also see the sample answer in the file [`sample_answer.json`](test/samples/sample_answer.json).
