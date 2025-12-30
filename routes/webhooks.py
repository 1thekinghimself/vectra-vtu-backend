"""Re-export `webhooks_bp` from `services.routes.webhooks` for backwards compatibility."""
from services.routes.webhooks import webhooks_bp

__all__ = ["webhooks_bp"]
