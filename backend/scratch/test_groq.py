import os
import json
import httpx

with open("d:/automation/Job Applied/backend/.env", "r") as f:
    for line in f:
        if line.strip() and not line.startswith("#"):
            k, v = line.strip().split("=", 1)
            os.environ[k] = v

def main():
    api_key = os.environ.get("GROQ_API_KEY")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": "Return a JSON object with a key 'name' and value 'Tejaswini'."}],
        "response_format": {"type": "json_object"},
        "max_tokens": 150
    }
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=10.0)
        print("Status code:", response.status_code)
        if response.status_code == 200:
            res_json = response.json()
            if "choices" in res_json and res_json["choices"]:
                print("Content:", res_json["choices"][0]["message"].get("content"))
        else:
            print("Error:", response.text)
    except Exception as e:
        print("Exception:", e)

if __name__ == "__main__":
    main()
