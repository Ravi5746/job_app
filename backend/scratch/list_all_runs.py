import os
import sys
from langsmith import Client

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
        print("Error: LANGCHAIN_API_KEY not found.")
        return

    client = Client(api_key=api_key)
    try:
        runs = list(client.list_runs(project_name=project, limit=50))
        print(f"Total retrieved runs from '{project}': {len(runs)}")
        
        statuses = {}
        types = {}
        for r in runs:
            statuses[r.status] = statuses.get(r.status, 0) + 1
            types[r.run_type] = types.get(r.run_type, 0) + 1
            
        print("\nStatus counts:")
        for k, v in statuses.items():
            print(f"  {k}: {v}")
            
        print("\nRun type counts:")
        for k, v in types.items():
            print(f"  {k}: {v}")
            
        print("\nLast 15 runs list:")
        for idx, r in enumerate(runs[:15], 1):
            print(f"  #{idx} | Name: {r.name} | Type: {r.run_type} | Status: {r.status} | ID: {r.id}")
            if r.error:
                print(f"    Error: {str(r.error)[:100]}...")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
