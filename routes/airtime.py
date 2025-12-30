"""Re-export `airtime_bp` from `services.routes.airtime` for backwards compatibility."""
from services.routes.airtime import airtime_bp

__all__ = ["airtime_bp"]
