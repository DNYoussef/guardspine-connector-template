"""
GuardSpine Connector Framework

Build connectors that emit verifiable evidence bundles.
"""

from .base import BaseConnector
from .events import ChangeEvent, EventType
from .bundle_emitter import BundleEmitter

__version__ = "0.1.0"
__all__ = ["BaseConnector", "ChangeEvent", "EventType", "BundleEmitter"]
