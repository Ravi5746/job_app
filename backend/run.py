import asyncio
import sys
import uvicorn

if __name__ == "__main__":
    # Fix for NotImplementedError on Windows
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    # Run the server
    # Note: reload=False is REQUIRED on Windows to prevent loop policy loss in subprocesses
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
