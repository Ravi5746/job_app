import os
import json
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

def summarize_message(msg):
    if not msg:
        return "None"
    
    if isinstance(msg, list):
        if len(msg) > 0:
            return summarize_message(msg[0])
        return "Empty list"
        
    kwargs = msg.get("kwargs", {})
    content = kwargs.get("content", "")
    
    if isinstance(content, list):
        content = str(content)
        
    tool_calls = kwargs.get("tool_calls", [])
    if not tool_calls and "tool_calls" in msg:
        tool_calls = msg["tool_calls"]
        
    summary = ""
    if content:
        summary += f"Content (truncated): {content[:150]}...\n"
    if tool_calls:
        summary += f"Tool Calls: {json.dumps(tool_calls)}\n"
        
    return summary.strip()

def main():
    json_path = os.path.join(os.path.dirname(__file__), "llm_runs_details.json")
    if not os.path.exists(json_path):
        print(f"Error: {json_path} not found.")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        runs = json.load(f)

    print(f"Analyzing {len(runs)} LLM runs:\n")
    for r in runs:
        print(f"Run #{r['index']} | Name/Model: {r['name']} | ID: {r['id']} | Status: {r['status']}")
        print(f"Start Time: {r['start_time']}")
        
        # Check inputs
        inputs = r.get("inputs", {})
        messages = inputs.get("messages", [])
        if not messages and "input" in inputs:
            messages = inputs["input"]
            
        print(f"Inputs - Message Count: {len(messages)}")
        
        if messages and isinstance(messages[0], list):
            messages = messages[0]
            
        system_prompt = ""
        user_prompt = ""
        last_human_prompt = ""
        
        for msg in messages:
            if isinstance(msg, dict):
                mtype = msg.get("type", "")
                kwargs = msg.get("kwargs", {})
                role = kwargs.get("type") or msg.get("role") or mtype
                content = kwargs.get("content") or msg.get("content") or ""
                
                if role == "system" or "SystemMessage" in str(msg.get("id", "")):
                    system_prompt = content
                elif role == "human" or "HumanMessage" in str(msg.get("id", "")):
                    last_human_prompt = content
                    if not user_prompt:
                        user_prompt = content
            else:
                user_prompt = str(msg)
                
        if system_prompt:
            print(f"  System Prompt Length: {len(system_prompt)} chars")
        if last_human_prompt:
            print(f"  Last Human Prompt Length: {len(last_human_prompt)} chars")
            lines = [l.strip() for l in last_human_prompt.split("\n") if l.strip()]
            print(f"    Snippet: {' / '.join(lines[:3])[:120]}...")
            
        # Check outputs
        outputs = r.get("outputs", {})
        if outputs:
            generations = outputs.get("generations", [])
            if generations and len(generations) > 0:
                gen = generations[0]
                if isinstance(gen, list) and len(gen) > 0:
                    gen = gen[0]
                if isinstance(gen, dict):
                    msg_out = gen.get("message", {})
                    if msg_out:
                        print("  Output Message:")
                        print("    " + summarize_message(msg_out).replace("\n", "\n    "))
            elif "output" in outputs:
                print(f"  Output: {outputs['output']}")
                
        if r.get("error"):
            print(f"  Error: {r['error']}")
            
        print("-" * 60)

if __name__ == "__main__":
    main()
