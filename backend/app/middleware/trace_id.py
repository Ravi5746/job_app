from fastapi import Request
import uuid
from app.core.logger import trace_id_ctx

async def trace_id_middleware(request: Request, call_next):
    # Retrieve X-Trace-ID from headers or generate a new UUID
    trace_id = request.headers.get("X-Trace-ID") or str(uuid.uuid4())
    
    # Set the ContextVar trace ID
    token = trace_id_ctx.set(trace_id)
    
    try:
        response = await call_next(request)
        response.headers["X-Trace-ID"] = trace_id
        return response
    finally:
        # Reset ContextVar to restore previous value
        trace_id_ctx.reset(token)
