import argparse
import json
import os
import sys
from typing import Any

from langsmith import Client

# Reconfigure stdout to use UTF-8 to handle unicode/emojis in Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


def load_env(env_path: str) -> None:
    if not os.path.exists(env_path):
        return

    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.strip().split("=", 1)
                os.environ[k] = v


def safe_string(value: Any, max_length: int = 500) -> str:
    try:
        text = json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        text = str(value)
    if len(text) > max_length:
        return text[:max_length] + "... [TRUNCATED]"
    return text


def print_run_summary(run: Any, index: int, show_details: bool = False) -> None:
    print(f"Run #{index} | Name: {getattr(run, 'name', None)} | Status: {getattr(run, 'status', None)} | ID: {getattr(run, 'id', None)}")
    print(f"   Start Time: {getattr(run, 'start_time', None)}")
    if show_details:
        if getattr(run, 'inputs', None):
            inputs = run.inputs
            print(f"   Input Keys: {list(inputs.keys())}")
            for key, val in inputs.items():
                print(f"      - {key}: {safe_string(val)}")

        if getattr(run, 'outputs', None):
            outputs = run.outputs
            print(f"   Output Keys: {list(outputs.keys())}")
            for key, val in outputs.items():
                print(f"      - {key}: {safe_string(val)}")

        if getattr(run, 'error', None):
            error_text = str(run.error).strip()
            print(f"   Error: {safe_string(error_text, max_length=800)}")
    print("=" * 80)


def serialize_run(run: Any) -> dict[str, Any]:
    return {
        "name": getattr(run, "name", None),
        "id": str(getattr(run, "id", None)),
        "status": getattr(run, "status", None),
        "start_time": str(getattr(run, "start_time", None)),
        "end_time": str(getattr(run, "end_time", None)) if getattr(run, "end_time", None) else None,
        "inputs": getattr(run, "inputs", None),
        "outputs": getattr(run, "outputs", None),
        "error": getattr(run, "error", None),
        "extra": getattr(run, "extra", None),
    }


def write_json_file(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch current LangSmith run details from the configured project.")
    parser.add_argument("--project", default=os.getenv("LANGCHAIN_PROJECT", "job-applied-automation"), help="LangSmith project name")
    parser.add_argument("--run-type", default="llm", help="Run type filter for LangSmith list_runs")
    parser.add_argument("--limit", type=int, default=20, help="Maximum number of runs to fetch")
    parser.add_argument("--latest", action="store_true", help="Show only the latest run")
    parser.add_argument("--run-id", help="Fetch a specific run by ID")
    parser.add_argument("--output-json", help="Write fetched run details to JSON file")
    parser.add_argument("--details", action="store_true", help="Print full inputs and outputs for each fetched run")
    args = parser.parse_args()

    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    load_env(env_path)

    api_key = os.getenv("LANGCHAIN_API_KEY")
    if not api_key:
        print("Error: LANGCHAIN_API_KEY not found in backend/.env or environment.")
        sys.exit(1)

    client = Client(api_key=api_key)
    print(f"Connecting to LangSmith project: {args.project}")

    try:
        runs = []
        if args.run_id:
            run = client.get_run(args.run_id)
            runs = [run]
        else:
            runs = list(client.list_runs(project_name=args.project, run_type=args.run_type, limit=args.limit))

        if not runs:
            print("No runs found.")
            return

        if args.latest:
            runs = runs[:1]

        print(f"Loaded {len(runs)} run(s) from LangSmith project '{args.project}'.\n")
        for idx, run in enumerate(runs, 1):
            print_run_summary(run, idx, show_details=args.details)

        if args.output_json:
            output_data = [serialize_run(run) for run in runs]
            write_json_file(args.output_json, output_data)
            print(f"Wrote run details to: {args.output_json}")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
