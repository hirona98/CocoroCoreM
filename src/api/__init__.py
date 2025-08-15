"""CocoroCore2 API Endpoints"""

from .health import router as health_router
from .control import router as control_router

__all__ = [
    "health_router",
    "control_router",
]