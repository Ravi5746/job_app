import logging
import sys
import contextvars

# Context variable to hold the trace/correlation ID
trace_id_ctx = contextvars.ContextVar("trace_id", default="-")

class TraceIdFilter(logging.Filter):
    def filter(self, record):
        record.trace_id = trace_id_ctx.get()
        return True

import os

# Ensure logs directory exists
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "app.log")

# Create stream handler and add the filter
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.addFilter(TraceIdFilter())

# Create file handler and add the filter
file_handler = logging.FileHandler(log_file, encoding="utf-8")
file_handler.addFilter(TraceIdFilter())

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(trace_id)s] %(name)s: %(message)s",
    handlers=[stream_handler, file_handler]
)

logger = logging.getLogger("api")


