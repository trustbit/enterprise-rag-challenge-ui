# Enterprise RAG Challenge UI & Submission Handling
Codebase for the Enterprise RAG Challenge UI and submission handling

## Getting Started
Install dependencies
```bash
conda env create -f environment.yml
```

Activate the environment
```bash
conda activate rag-challenge-ui
``` 

Run the app
```bash
python -m uvicorn src.main:app --reload
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

### Test file submission (json)
```bash
curl -X 'POST' \
  'http://127.0.0.1:8000/submit'
  -H 'accept: application/json' \
  -H 'Content-Type: multipart/form-data' \
  -F 'file=@test/samples/sample_answer.json;type=application/json'
```