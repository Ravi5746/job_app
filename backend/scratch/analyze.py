import os
import sys
import json
from langsmith import Client

# Reconfigure stdout to use UTF-8 to handle unicode/emojis in Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

def main():
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
        print("Error: LANGCHAIN_API_KEY not found in backend/.env")
        return

    client = Client(api_key=api_key)
    output_file = os.path.join(os.path.dirname(__file__), "langsmith_20_details.txt")
    
    try:
        runs = list(client.list_runs(project_name=project, limit=20))
        if not runs:
            print("No runs found.")
            return
            
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(f"Loaded {len(runs)} runs from LangSmith project '{project}':\n\n")
            
            for idx, r in enumerate(runs, 1):
                f.write(f"Run #{idx} | Name: {r.name} | Status: {r.status} | ID: {r.id}\n")
                f.write(f"Start Time: {r.start_time}\n")
                
                if r.inputs:
                    f.write("Inputs:\n")
                    f.write(json.dumps(r.inputs, indent=2, ensure_ascii=False))
                    f.write("\n")
                
                if r.outputs:
                    f.write("Outputs:\n")
                    f.write(json.dumps(r.outputs, indent=2, ensure_ascii=False))
                    f.write("\n")
                
                if r.error:
                    f.write(f"Error: {r.error}\n")
                    
                f.write("=" * 80 + "\n\n")
                
        print(f"Details written to {output_file}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
