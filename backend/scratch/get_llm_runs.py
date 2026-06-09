import os
import sys
import json
from langsmith import Client

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

def main():
    # Load env vars
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.strip().split("=", 1)
                    os.environ[k] = v

    api_key = os.getenv("LANGCHAIN_API_KEY")
    project = os.getenv("LANGCHAIN_PROJECT", "job-applied-automation")
    
    if not api_key:
        print("Error: LANGCHAIN_API_KEY not found.")
        return

    client = Client(api_key=api_key)
    print(f"Connecting to LangSmith project: {project}")
    
    try:
        # List LLM runs
        runs = list(client.list_runs(
            project_name=project,
            run_type="llm",
            limit=40
        ))
        
        print(f"Retrieved {len(runs)} LLM runs.")
        output_file = os.path.join(os.path.dirname(__file__), "llm_runs_details.json")
        
        runs_data = []
        for idx, r in enumerate(runs, 1):
            run_info = {
                "index": idx,
                "name": r.name,
                "id": str(r.id),
                "status": r.status,
                "start_time": str(r.start_time),
                "end_time": str(r.end_time) if r.end_time else None,
                "extra": r.extra,
                "error": r.error,
                "inputs": r.inputs,
                "outputs": r.outputs
            }
            runs_data.append(run_info)
            
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(runs_data, f, indent=2, ensure_ascii=False)
            
        print(f"Successfully wrote LLM runs details to: {output_file}")
            
    except Exception as e:
        print(f"Error fetching runs: {e}")

if __name__ == "__main__":
    main()
