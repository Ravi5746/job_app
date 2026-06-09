import os
import json

def main():
    json_path = os.path.join(os.path.dirname(__file__), "llm_runs_details.json")
    if not os.path.exists(json_path):
        print("Error: JSON not found.")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        runs = json.load(f)

    print(f"Loaded {len(runs)} runs.")
    
    # We will print the error message of each run
    for r in runs[:27]:
        error_msg = r.get("error")
        clean_error = "None"
        if error_msg:
            # Clean up the trace/exception to show the core error message
            if "RateLimitError" in error_msg:
                idx = error_msg.find("RateLimitError")
                clean_error = error_msg[idx:idx+200]
            elif "APIStatusError" in error_msg:
                idx = error_msg.find("APIStatusError")
                clean_error = error_msg[idx:idx+200]
            elif "APIConnectionError" in error_msg:
                idx = error_msg.find("APIConnectionError")
                clean_error = error_msg[idx:idx+200]
            else:
                clean_error = error_msg[:150]
        
        # Check inputs / messages to see if there's any HTML size issue
        inputs = r.get("inputs", {})
        messages = inputs.get("messages", []) or inputs.get("input", [])
        if messages and isinstance(messages[0], list):
            messages = messages[0]
        
        html_len = 0
        for msg in messages:
            if isinstance(msg, dict):
                content = msg.get("kwargs", {}).get("content", "") or msg.get("content", "")
                if "FORM HTML" in content or "Updated HTML" in content:
                    html_len = len(content)
                    
        print(f"Run #{r['index']} | Name: {r['name']} | Status: {r['status']} | Model/LLM: {r.get('extra', {}).get('invocation_params', {}).get('model_name', 'unknown')}")
        print(f"  Error Snippet: {clean_error}")
        print(f"  Approx Input HTML/User Prompt Char Count: {html_len}")
        print("-" * 60)

if __name__ == "__main__":
    main()
