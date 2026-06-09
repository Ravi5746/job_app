with open("d:/automation/Job Applied/backend/scratch/langsmith_20_details.txt", "r", encoding="utf-8") as f:
    current_run = None
    for line in f:
        if line.startswith("Run #"):
            current_run = line.strip()
        elif "Error:" in line:
            print(f"{current_run} => {line.strip()}")
