import requests

SUBMISSION_JSON_PATH = r"test\samples\sample_answer.json"


def main():
    url = "http://127.0.0.1:8000/submit"
    # url = "http://127.0.0.1:8000/check-submission"
    headers = {"accept": "application/json"}
    files = {
        "file": ("sample_answer.json", open(SUBMISSION_JSON_PATH, "rb"), "application/json")
    }
    response = requests.post(url, headers=headers, files=files)
    assert response.status_code == 200
    print(response.json())


if __name__ == "__main__":
    main()
