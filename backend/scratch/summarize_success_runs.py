import os
import json
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

def get_message_content(msg):
    if not msg:
        return ""
    if isinstance(msg, list):
        if len(msg) > 0:
            return get_message_content(msg[0])
        return ""
    kwargs = msg.get("kwargs", {})
    return kwargs.get("content") or msg.get("content") or ""

def get_tool_calls(msg):
    if not msg:
        return []
    if isinstance(msg, list):
        if len(msg) > 0:
            return get_tool_calls(msg[0])
        return []
    kwargs = msg.get("kwargs", {})
    return kwargs.get("tool_calls") or msg.get("tool_calls") or []

def main():
    json_path = os.path.join(os.path.dirname(__file__), "llm_runs_details.json")
    if not os.path.exists(json_path):
        print(f"Error: {json_path} not found.")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        runs = json.load(f)

    success_runs = [r for r in runs if r.get("status") == "success"]
    print(f"Total Runs: {len(runs)}")
    print(f"Success Runs: {len(success_runs)}")

    output_path = os.path.join(os.path.dirname(__file__), "success_runs_details.txt")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"Successful LLM Runs ({len(success_runs)}):\n\n")
        
        for idx, r in enumerate(success_runs, 1):
            f.write(f"SUCCESS RUN #{idx} | Name: {r['name']} | ID: {r['id']} | Start Time: {r['start_time']}\n")
            
            # Extract inputs
            inputs = r.get("inputs", {})
            messages = inputs.get("messages", []) or inputs.get("input", [])
            if messages and isinstance(messages[0], list):
                messages = messages[0]
                
            system_prompt = ""
            human_messages = []
            
            for msg in messages:
                if isinstance(msg, dict):
                    mtype = msg.get("type", "")
                    kwargs = msg.get("kwargs", {})
                    role = kwargs.get("type") or msg.get("role") or mtype
                    content = kwargs.get("content") or msg.get("content") or ""
                    
                    if role == "system" or "SystemMessage" in str(msg.get("id", "")):
                        system_prompt = content
                    elif role == "human" or "HumanMessage" in str(msg.get("id", "")):
                        human_messages.append(content)
                else:
                    human_messages.append(str(msg))
                    
            f.write(f"SYSTEM PROMPT (length: {len(system_prompt)}):\n{system_prompt}\n\n")
            for h_idx, h_msg in enumerate(human_messages, 1):
                f.write(f"HUMAN MESSAGE #{h_idx} (length: {len(h_msg)}):\n{h_msg}\n\n")
                
            # Extract outputs
            outputs = r.get("outputs", {})
            generations = outputs.get("generations", [])
            if generations and len(generations) > 0:
                gen = generations[0]
                if isinstance(gen, list) and len(gen) > 0:
                    gen = gen[0]
                if isinstance(gen, dict):
                    msg_out = gen.get("message", {})
                    if msg_out:
                        content_out = get_message_content(msg_out)
                        tool_calls = get_tool_calls(msg_out)
                        f.write(f"MODEL RESPONSE CONTENT:\n{content_out}\n\n")
                        f.write(f"MODEL TOOL CALLS:\n{json.dumps(tool_calls, indent=2)}\n\n")
            elif "output" in outputs:
                f.write(f"MODEL OUTPUT: {outputs['output']}\n\n")
                
            f.write("=" * 100 + "\n\n")

    print(f"Details of successful runs written to {output_path}")

if __name__ == "__main__":
    main()
