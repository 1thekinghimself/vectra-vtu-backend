"""Re-export `transactions_bp` from `services.routes.transactions` for compatibility."""
from services.routes.transactions import transactions_bp

__all__ = ["transactions_bp"]
