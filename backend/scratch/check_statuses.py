import os
import json

def main():
    json_path = os.path.join(os.path.dirname(__file__), "llm_runs_details.json")
    if not os.path.exists(json_path):
        print(f"Error: {json_path} not found.")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        runs = json.load(f)

    statuses = {}
    names = {}
    for r in runs:
        status = r.get("status", "unknown")
        statuses[status] = statuses.get(status, 0) + 1
        
        name = r.get("name", "unknown")
        names[name] = names.get(name, 0) + 1

    print("Statuses:")
    for k, v in statuses.items():
        print(f"  {k}: {v}")
        
    print("\nNames:")
    for k, v in names.items():
        print(f"  {k}: {v}")

    # Let's print the first run's details to see what is going on
    if runs:
        print("\nFirst Run Info:")
        print(f"  Name: {runs[0]['name']}")
        print(f"  Status: {runs[0]['status']}")
        print(f"  Error: {runs[0].get('error')}")
        if 'outputs' in runs[0]:
            print(f"  Outputs: {list(runs[0]['outputs'].keys()) if runs[0]['outputs'] else 'None'}")

if __name__ == "__main__":
    main()
