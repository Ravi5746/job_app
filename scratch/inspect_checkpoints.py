import sqlite3
import json
import pickle

def main():
    conn = sqlite3.connect("d:/automation/Job Applied/backend/checkpoints.db")
    cursor = conn.cursor()
    
    # List tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print("Tables:", tables)
    
    # Check checkpoints table
    for table in tables:
        name = table[0]
        cursor.execute(f"SELECT COUNT(*) FROM {name}")
        count = cursor.fetchone()[0]
        print(f"Table {name}: {count} rows")
        
    # Let's inspect the latest checkpoints
    cursor.execute("SELECT thread_id, checkpoint_id, checkpoint FROM checkpoints ORDER BY checkpoint_id DESC LIMIT 5")
    rows = cursor.fetchall()
    for row in rows:
        thread_id, checkpoint_id, checkpoint_data = row
        print(f"\n--- Thread ID: {thread_id}, Checkpoint ID: {checkpoint_id} ---")
        try:
            # Checkpoints are usually serialized using pickle or JSON
            # In langgraph, they might be pickled or serialized with a specific serializer. Let's try loading.
            checkpoint = pickle.loads(checkpoint_data)
            print("Keys:", checkpoint.keys())
            if "channel_values" in checkpoint:
                cv = checkpoint["channel_values"]
                print("Channel keys:", cv.keys())
                # Print status, step_type, pending_fields, etc.
                for k in ["step_type", "status", "retry_count", "errors"]:
                    if k in cv:
                        print(f"  {k}: {cv[k]}")
                if "accessible_fields" in cv:
                    print(f"  accessible_fields count: {len(cv['accessible_fields'])}")
                    for idx, f in enumerate(cv['accessible_fields']):
                        print(f"    Field {idx}: qa_idx={f.get('qa_idx')}, name={f.get('name')}, type={f.get('type')}, label={f.get('aria-label')}, value={f.get('value')}")
                if "pending_fields" in cv:
                    print(f"  pending_fields count: {len(cv['pending_fields'])}")
                if "html" in cv and cv["html"]:
                    print(f"  HTML length: {len(cv['html'])}")
                    # Save HTML to a file to inspect it
                    with open(f"d:/automation/Job Applied/scratch/checkpoint_{checkpoint_id}.html", "w", encoding="utf-8") as f_html:
                        f_html.write(cv["html"])
                    print(f"  Saved HTML to d:/automation/Job Applied/scratch/checkpoint_{checkpoint_id}.html")
        except Exception as e:
            print("Failed to parse checkpoint:", e)
            
    conn.close()

if __name__ == "__main__":
    main()
