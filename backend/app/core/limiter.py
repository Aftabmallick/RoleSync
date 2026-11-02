import os
import sys
from slowapi import Limiter
from slowapi.util import get_remote_address

is_testing = os.environ.get("TESTING", "").lower() in ("true", "1") or "pytest" in sys.modules

# Enterprise in-memory / redis-backed rate limiter
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["120/minute"],
    enabled=not is_testing,
)

