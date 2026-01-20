"""
Event types for connector change detection.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class EventType(str, Enum):
    """Types of change events."""

    FILE_CREATED = "file_created"
    FILE_MODIFIED = "file_modified"
    FILE_DELETED = "file_deleted"
    FILE_MOVED = "file_moved"
    PERMISSION_CHANGED = "permission_changed"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_DECIDED = "approval_decided"


@dataclass
class ChangeEvent:
    """
    A change event from the source system.

    Connectors yield these events, which are then processed
    into evidence bundles.
    """

    artifact_id: str
    """Unique identifier for the artifact in the source system."""

    event_type: EventType
    """Type of change that occurred."""

    from_version: Optional[str] = None
    """Version before the change (for modifications)."""

    to_version: Optional[str] = None
    """Version after the change."""

    change_type: str = "unknown"
    """Human-readable change type."""

    actor_id: Optional[str] = None
    """User or system that made the change."""

    actor_name: Optional[str] = None
    """Display name of the actor."""

    actor_email: Optional[str] = None
    """Email of the actor."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    """When the change occurred."""

    source_url: Optional[str] = None
    """URL to the artifact in the source system."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Additional metadata from the source system."""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "artifact_id": self.artifact_id,
            "event_type": self.event_type.value,
            "from_version": self.from_version,
            "to_version": self.to_version,
            "change_type": self.change_type,
            "actor_id": self.actor_id,
            "actor_name": self.actor_name,
            "actor_email": self.actor_email,
            "timestamp": self.timestamp.isoformat(),
            "source_url": self.source_url,
            "metadata": self.metadata,
        }


@dataclass
class DiffResult:
    """
    Result of computing a diff between versions.
    """

    artifact_id: str
    from_version: str
    to_version: str
    diff_type: str  # "text", "binary", "structured"
    hunks: list[dict[str, Any]] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)
    from_hash: Optional[str] = None
    to_hash: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for bundle embedding."""
        return {
            "diff_id": f"{self.artifact_id}:{self.from_version}:{self.to_version}",
            "algorithm": "unified",
            "from_hash": self.from_hash,
            "to_hash": self.to_hash,
            "hunks": self.hunks,
            "stats": self.stats,
        }
