import os
import sys
import json
from langsmith import Client

# Reconfigure stdout to use UTF-8 to handle unicode/emojis in Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

def main():
    # Read backend/.env to load credentials
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
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
    
    try:
        runs = list(client.list_runs(project_name=project, limit=20))
        if not runs:
            print("No runs found.")
            return
            
        print(f"Loaded {len(runs)} runs from LangSmith project '{project}':\n")
        
        for idx, r in enumerate(runs, 1):
            print(f"Run #{idx} | Name: {r.name} | Status: {r.status} | ID: {r.id}")
            print(f"   Start Time: {r.start_time}")
            
            # Print input summary/details
            if r.inputs:
                inputs_keys = list(r.inputs.keys())
                print(f"   Input Keys: {inputs_keys}")
                # Print a snippet of inputs
                for key in inputs_keys:
                    val = r.inputs[key]
                    val_str = str(val)
                    if len(val_str) > 300:
                        val_str = val_str[:300].encode('utf-8', errors='replace').decode('utf-8') + "... [TRUNCATED]"
                    print(f"   - Input '{key}': {val_str}")
            
            # Print output summary/details
            if r.outputs:
                outputs_keys = list(r.outputs.keys())
                print(f"   Output Keys: {outputs_keys}")
                for key in outputs_keys:
                    val = r.outputs[key]
                    val_str = str(val)
                    if len(val_str) > 300:
                        val_str = val_str[:300].encode('utf-8', errors='replace').decode('utf-8') + "... [TRUNCATED]"
                    print(f"   - Output '{key}': {val_str}")
            
            if r.error:
                error_str = r.error.strip()
                if len(error_str) > 400:
                    error_str = error_str[:400].encode('utf-8', errors='replace').decode('utf-8') + "... [TRUNCATED]"
                print(f"   Error: {error_str}")
                
            print("=" * 80)
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
