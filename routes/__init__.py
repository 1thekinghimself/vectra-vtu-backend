"""
Compatibility shim package so existing imports like
`from routes.airtime import airtime_bp` continue to work.
This module intentionally left minimal; see submodules.
"""

__all__ = ["airtime", "data", "webhooks"]
