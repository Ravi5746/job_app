import asyncio
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

async def main():
    async with AsyncSqliteSaver.from_conn_string("backend/checkpoints.db") as checkpointer:
        # List all threads
        print("Retrieving all checkpoints...")
        config_list = []
        async for checkpoint in checkpointer.alist(None):
            config_list.append(checkpoint)
            
        print(f"Total checkpoints found: {len(config_list)}")
        
        # Group by thread_id and print latest
        by_thread = {}
        for config in config_list:
            tid = config.config["configurable"]["thread_id"]
            if tid not in by_thread:
                by_thread[tid] = []
            by_thread[tid].append(config)
            
        print("Threads:")
        for tid, configs in by_thread.items():
            print(f"  Thread {tid}: {len(configs)} checkpoints")
            
        # Get the latest thread checkpoint
        if by_thread:
            latest_tid = "2_771"
            print(f"\nAnalyzing thread: {latest_tid}")
            configs = by_thread[latest_tid]
            # Print the latest checkpoint values
            latest_config = configs[0] # alist returns them sorted newest first
            
            # Print keys
            cv = latest_config.checkpoint.get("channel_values", {})
            print("Channel values keys:", list(cv.keys()))
            for key in ["step_type", "status", "retry_count", "errors", "step_number"]:
                if key in cv:
                    print(f"  {key}: {cv[key]}")
            
            # Print accessible_fields
            if "accessible_fields" in cv:
                print(f"  accessible_fields: {len(cv['accessible_fields'])} fields")
                for idx, f in enumerate(cv["accessible_fields"]):
                    print(f"    {idx}: {f}")
            
            if "pending_fields" in cv:
                print(f"  pending_fields: {len(cv['pending_fields'])} fields")
                for idx, f in enumerate(cv["pending_fields"]):
                    print(f"    {idx}: qa_idx={f.get('qa_idx')}")
            
            # Save HTML
            if "html" in cv and cv["html"]:
                html_path = "scratch/latest_modal.html"
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(cv["html"])
                print(f"  Saved HTML to {html_path}")
                
            # Also let's inspect the questionnaire_answers or questionnaire in state
            if "profile" in cv:
                p = cv["profile"]
                print("Profile keys and values:")
                for k, v in p.items():
                    print(f"  {k}: {v}")
                
if __name__ == "__main__":
    asyncio.run(main())
