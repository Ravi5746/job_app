import re

path = 'd:/automation/Job Applied/backend/app/services/automation/agent/langgraph_helpers.py'
with open(path, 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Remove active_targets and get_target_context
code = re.sub(r'# Registry for active live targets.*?\nactive_targets: Dict\[str, Dict\[str, Any\]\] = \{\}\n\ndef get_target_context\(config: RunnableConfig\) -> Dict\[str, Any\]:\n.*?return active_targets\[thread_id\]\n', '', code, flags=re.DOTALL)

# 2. Update run_* signatures
code = re.sub(r'(async def run_[a-zA-Z0-9_]+\(state: Dict\[str, Any\], config: RunnableConfig\)) -> Dict\[str, Any\]:', r'\1, ctx: Dict[str, Any] = None) -> Dict[str, Any]:', code)

# 3. Remove ctx = get_target_context(config) inside nodes
code = re.sub(r'\s+ctx = get_target_context\(config\)\n', '\n', code)

# 4. Update record_step_metrics definition
code = re.sub(r'def record_step_metrics\(\n    config: RunnableConfig,\n', r'def record_step_metrics(\n    config: RunnableConfig,\n    ctx: Dict[str, Any],\n', code)

# 5. Remove ctx = get_target_context(config) inside record_step_metrics
code = re.sub(r'        ctx = get_target_context\(config\)\n', '', code)

# 6. Update record_step_metrics calls
code = re.sub(r'record_step_metrics\(config,', r'record_step_metrics(config, ctx,', code)
code = re.sub(r'record_step_metrics\(\n\s+config,', r'record_step_metrics(\n        config,\n        ctx,', code)

with open(path, 'w', encoding='utf-8') as f:
    f.write(code)
print('Refactored langgraph_helpers.py')
