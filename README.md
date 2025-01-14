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
```bash
curl -X POST -H "Content-Type: application/json" -d '[{ "question": "Q1", "schema": "name", "answer": "A1" }, { "question": "Q2", "schema": "number", "answer": 2.5 }, { "question": "Q2", "schema": "boolean", "answer": true }]' http://localhost:8000/submit
```

curl -X POST -H "Content-Type: application/json" -d '{"question": "What was the Quick Ratio of IMUNON, INC. in June 30, 2021?", "answer": 1.5}' http://localhost:8000/submit