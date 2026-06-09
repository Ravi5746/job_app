import os
import sys
import json
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
        runs = list(client.list_runs(project_name=project, limit=100))
        print(f"Total retrieved runs: {len(runs)}")
        
        # Save run list metadata to inspect
        summary = []
        for idx, r in enumerate(runs, 1):
            summary.append({
                "idx": idx,
                "name": r.name,
                "type": r.run_type,
                "status": r.status,
                "id": str(r.id),
                "error": str(r.error) if r.error else None,
                "parent_run_id": str(r.parent_run_id) if r.parent_run_id else None
            })
            
        with open("scratch/run_list_100.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
            
        print("Wrote 100 runs list to scratch/run_list_100.json")
        
        # Let's count success/error per type
        stats = {}
        for s in summary:
            key = (s["type"], s["status"])
            stats[key] = stats.get(key, 0) + 1
            
        print("\nStatistics (Type, Status):")
        for k, v in stats.items():
            print(f"  {k}: {v}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
