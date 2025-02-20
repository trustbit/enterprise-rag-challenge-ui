import requests

SUBMISSION_JSON_PATH = r"test\samples\sample_answer.json"


def main():
    # LOCAL
    # url = "http://127.0.0.1:8000/check-submission"
    # url = "http://127.0.0.1:8000/submit"

    # PROD
    # url = "https://rag.timetoact.at/check-submission"
    url = "https://rag.timetoact.at/submit"

    headers = {"accept": "application/json"}
    files = {
        "file": ("sample_answer.json", open(SUBMISSION_JSON_PATH, "rb"), "application/json")
    }
    response = requests.post(url, headers=headers, files=files)
    print(response.json())


if __name__ == "__main__":
    main()
