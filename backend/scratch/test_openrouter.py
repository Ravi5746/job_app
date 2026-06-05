import json
import os
import httpx
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open("d:/automation/Job Applied/backend/.env", "r") as f:
    for line in f:
        if line.strip() and not line.startswith("#"):
            k, v = line.strip().split("=", 1)
            os.environ[k] = v

def test_tokens(max_tokens):
    model_name = "google/gemini-2.5-flash"
    api_key = os.environ.get("OPENAI_API_KEY")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": "Return a JSON object with a key 'name' and value 'Tejaswini'."}],
        "response_format": {"type": "json_object"},
        "max_tokens": max_tokens
    }
    url = "https://openrouter.ai/api/v1/chat/completions"
    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=10.0)
        print(f"Testing max_tokens={max_tokens} -> Status: {response.status_code}")
        if response.status_code != 200:
            print("Response:", response.text)
        else:
            print("Success!")
    except Exception as e:
        print("Exception:", e)

def main():
    for tokens in [1500, 1000, 800, 500, 350]:
        test_tokens(tokens)

if __name__ == "__main__":
    main()
