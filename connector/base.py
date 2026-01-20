"""
Base connector class for GuardSpine integrations.
"""

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Optional

from .events import ChangeEvent, DiffResult


class BaseConnector(ABC):
    """
    Base class for GuardSpine connectors.

    Implement this class to create a connector for your source system.

    Example:
        class GitHubConnector(BaseConnector):
            async def watch_changes(self) -> AsyncIterator[ChangeEvent]:
                async for event in self.github.watch_events():
                    yield ChangeEvent(...)

            async def get_diff(self, event: ChangeEvent) -> DiffResult:
                return await self.github.get_diff(...)
    """

    def __init__(self, config: dict[str, Any]):
        """
        Initialize the connector.

        Args:
            config: Configuration dictionary from YAML file
        """
        self.config = config
        self.name = config.get("connector", {}).get("name", "unknown")
        self.connector_type = config.get("connector", {}).get("type", "unknown")

    @abstractmethod
    async def watch_changes(self) -> AsyncIterator[ChangeEvent]:
        """
        Watch for changes and yield events.

        This is the main entry point for the connector. Implement this
        to connect to your source system and yield ChangeEvent objects
        when changes are detected.

        Yields:
            ChangeEvent objects for each detected change
        """
        pass

    @abstractmethod
    async def get_diff(self, event: ChangeEvent) -> Optional[DiffResult]:
        """
        Get the diff for a change event.

        Implement this to retrieve the actual diff content from your
        source system.

        Args:
            event: The change event to get diff for

        Returns:
            DiffResult with diff content, or None if diff not available
        """
        pass

    @abstractmethod
    async def get_artifact_metadata(self, artifact_id: str) -> dict[str, Any]:
        """
        Get metadata for an artifact.

        Implement this to retrieve artifact metadata like title, owner,
        permissions, etc.

        Args:
            artifact_id: The artifact identifier

        Returns:
            Dictionary with artifact metadata
        """
        pass

    async def healthcheck(self) -> dict[str, Any]:
        """
        Check connector health.

        Override this to implement custom health checks.

        Returns:
            Dictionary with health status
        """
        return {
            "healthy": True,
            "connector": self.name,
            "type": self.connector_type,
        }

    async def start(self) -> None:
        """
        Called when the connector starts.

        Override to perform initialization like establishing connections.
        """
        pass

    async def stop(self) -> None:
        """
        Called when the connector stops.

        Override to perform cleanup like closing connections.
        """
        pass

    def map_risk_tier(self, artifact_path: str) -> str:
        """
        Map an artifact path to a risk tier.

        Uses the risk_mapping configuration to determine risk tier.

        Args:
            artifact_path: Path or identifier of the artifact

        Returns:
            Risk tier (L0, L1, L2, L3, L4)
        """
        import fnmatch

        risk_mapping = self.config.get("risk_mapping", {})
        default_tier = risk_mapping.get("default", "L0")

        for pattern, tier in risk_mapping.items():
            if pattern == "default":
                continue
            if fnmatch.fnmatch(artifact_path, pattern):
                return tier

        return default_tier

    def should_process(self, artifact_path: str) -> bool:
        """
        Check if an artifact should be processed.

        Uses include_paths and exclude_paths filters.

        Args:
            artifact_path: Path or identifier of the artifact

        Returns:
            True if artifact should be processed
        """
        import fnmatch

        filters = self.config.get("filters", {})
        include_paths = filters.get("include_paths", ["**"])
        exclude_paths = filters.get("exclude_paths", [])

        # Check exclude first
        for pattern in exclude_paths:
            if fnmatch.fnmatch(artifact_path, pattern):
                return False

        # Check include
        for pattern in include_paths:
            if fnmatch.fnmatch(artifact_path, pattern):
                return True

        return False
