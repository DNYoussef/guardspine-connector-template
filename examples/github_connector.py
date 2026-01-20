"""
Example GitHub Connector for GuardSpine.

This connector watches GitHub repositories for changes and emits
evidence bundles for pull requests and commits.

Usage:
    pip install guardspine-connector-template[github]

    # config.yaml
    connector:
      type: github
      name: "My GitHub Connector"

    source:
      token: "${GITHUB_TOKEN}"
      repos:
        - "owner/repo1"
        - "owner/repo2"

    output:
      mode: file
      file_path: ./bundles
"""

import os
from typing import Any, AsyncIterator, Optional

from github import Github, PullRequest, Commit

from connector import BaseConnector, ChangeEvent, EventType, BundleEmitter
from connector.events import DiffResult


class GitHubConnector(BaseConnector):
    """
    Connector for GitHub repositories.

    Watches for:
    - Pull request events (opened, merged, closed)
    - Commit pushes
    - File changes
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        source = config.get("source", {})
        token = source.get("token", os.environ.get("GITHUB_TOKEN"))
        self.github = Github(token)
        self.repos = source.get("repos", [])
        self._last_seen: dict[str, str] = {}

    async def watch_changes(self) -> AsyncIterator[ChangeEvent]:
        """
        Watch GitHub repos for changes.

        Yields ChangeEvent for each detected change.
        """
        for repo_name in self.repos:
            repo = self.github.get_repo(repo_name)

            # Watch pull requests
            for pr in repo.get_pulls(state="all", sort="updated", direction="desc"):
                pr_key = f"{repo_name}/pr/{pr.number}"

                # Skip if we've seen this state
                current_state = f"{pr.state}:{pr.updated_at}"
                if self._last_seen.get(pr_key) == current_state:
                    continue
                self._last_seen[pr_key] = current_state

                event_type = self._pr_to_event_type(pr)
                yield ChangeEvent(
                    artifact_id=f"github:{repo_name}/pr/{pr.number}",
                    event_type=event_type,
                    from_version=pr.base.sha[:7],
                    to_version=pr.head.sha[:7],
                    change_type=f"pull_request_{pr.state}",
                    actor_id=pr.user.login if pr.user else None,
                    actor_name=pr.user.name if pr.user else None,
                    source_url=pr.html_url,
                    metadata={
                        "pr_number": pr.number,
                        "title": pr.title,
                        "body": pr.body,
                        "base_branch": pr.base.ref,
                        "head_branch": pr.head.ref,
                        "state": pr.state,
                        "merged": pr.merged,
                        "additions": pr.additions,
                        "deletions": pr.deletions,
                        "changed_files": pr.changed_files,
                    },
                )

    def _pr_to_event_type(self, pr: PullRequest.PullRequest) -> EventType:
        """Map PR state to event type."""
        if pr.merged:
            return EventType.FILE_MODIFIED
        elif pr.state == "open":
            return EventType.APPROVAL_REQUESTED
        else:
            return EventType.FILE_MODIFIED

    async def get_diff(self, event: ChangeEvent) -> Optional[DiffResult]:
        """
        Get diff for a GitHub change.
        """
        # Parse artifact ID
        parts = event.artifact_id.replace("github:", "").split("/")
        if len(parts) < 4:
            return None

        repo_name = f"{parts[0]}/{parts[1]}"
        pr_number = int(parts[3])

        repo = self.github.get_repo(repo_name)
        pr = repo.get_pull(pr_number)

        # Get files changed
        files = list(pr.get_files())

        hunks = []
        for f in files:
            hunks.append({
                "filename": f.filename,
                "status": f.status,
                "additions": f.additions,
                "deletions": f.deletions,
                "patch": f.patch[:1000] if f.patch else None,  # Truncate large patches
            })

        return DiffResult(
            artifact_id=event.artifact_id,
            from_version=event.from_version or "unknown",
            to_version=event.to_version or "unknown",
            diff_type="text",
            hunks=hunks,
            stats={
                "additions": pr.additions,
                "deletions": pr.deletions,
                "files_changed": pr.changed_files,
            },
        )

    async def get_artifact_metadata(self, artifact_id: str) -> dict[str, Any]:
        """
        Get metadata for a GitHub artifact.
        """
        parts = artifact_id.replace("github:", "").split("/")
        if len(parts) < 4:
            return {"title": artifact_id}

        repo_name = f"{parts[0]}/{parts[1]}"
        pr_number = int(parts[3])

        repo = self.github.get_repo(repo_name)
        pr = repo.get_pull(pr_number)

        return {
            "title": f"PR #{pr.number}: {pr.title}",
            "description": pr.body,
            "owner": pr.user.login if pr.user else "unknown",
            "url": pr.html_url,
            "connector_type": "github",
            "connector_name": self.name,
        }


# Example usage
async def main():
    """Example of running the GitHub connector."""
    import asyncio
    import yaml

    # Load config
    with open("config.yaml") as f:
        config = yaml.safe_load(f)

    # Create connector and emitter
    connector = GitHubConnector(config)
    emitter = BundleEmitter.from_config(config)

    print(f"Starting {connector.name}...")

    # Process changes
    async for event in connector.watch_changes():
        if not connector.should_process(event.artifact_id):
            print(f"Skipping {event.artifact_id} (filtered)")
            continue

        print(f"Processing: {event.artifact_id}")

        # Get diff and metadata
        diff = await connector.get_diff(event)
        metadata = await connector.get_artifact_metadata(event.artifact_id)

        # Determine risk tier
        risk_tier = connector.map_risk_tier(event.artifact_id)

        # Emit bundle
        bundle = await emitter.emit(
            event=event,
            diff=diff,
            metadata=metadata,
            risk_tier=risk_tier,
        )

        print(f"  Emitted bundle: {bundle['bundle_id']}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
