import os

print("Searching environment variables:")
for k, v in os.environ.items():
    if any(x in k.upper() for x in ["API", "KEY", "GEMINI", "GOOGLE"]):
        # redact value for safety
        redacted = v[:8] + "..." if len(v) > 8 else v
        print(f"{k} = {redacted}")
