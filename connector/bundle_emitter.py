"""
Bundle emitter for creating evidence bundles from connector events.
"""

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional

import httpx

from .events import ChangeEvent, DiffResult


@dataclass
class BundleEmitter:
    """
    Creates and emits evidence bundles from connector events.

    Supports multiple output modes:
    - api: Send to GuardSpine API
    - file: Write to local filesystem
    - webhook: POST to webhook URL
    """

    mode: Literal["api", "file", "webhook"]
    api_url: Optional[str] = None
    api_key: Optional[str] = None
    file_path: Optional[str] = None
    webhook_url: Optional[str] = None
    webhook_headers: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.mode == "api" and not self.api_url:
            raise ValueError("api_url required for API mode")
        if self.mode == "file" and not self.file_path:
            raise ValueError("file_path required for file mode")
        if self.mode == "webhook" and not self.webhook_url:
            raise ValueError("webhook_url required for webhook mode")

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "BundleEmitter":
        """Create emitter from configuration."""
        output = config.get("output", {})
        mode = output.get("mode", "file")

        return cls(
            mode=mode,
            api_url=output.get("api_url"),
            api_key=output.get("api_key"),
            file_path=output.get("file_path"),
            webhook_url=output.get("webhook_url"),
            webhook_headers=output.get("headers", {}),
        )

    async def emit(
        self,
        event: ChangeEvent,
        diff: Optional[DiffResult],
        metadata: dict[str, Any],
        risk_tier: str = "L0",
        bead_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Create and emit an evidence bundle.

        Args:
            event: The change event
            diff: Diff result (if available)
            metadata: Artifact metadata
            risk_tier: Risk classification
            bead_id: Associated work item ID

        Returns:
            Created bundle data
        """
        bundle = self._create_bundle(event, diff, metadata, risk_tier, bead_id)

        if self.mode == "api":
            return await self._emit_to_api(bundle)
        elif self.mode == "file":
            return await self._emit_to_file(bundle)
        elif self.mode == "webhook":
            return await self._emit_to_webhook(bundle)

        return bundle

    def _create_bundle(
        self,
        event: ChangeEvent,
        diff: Optional[DiffResult],
        metadata: dict[str, Any],
        risk_tier: str,
        bead_id: Optional[str],
    ) -> dict[str, Any]:
        """Create bundle structure from event and diff."""
        bundle_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        # Build evidence items
        items = []

        # Add diff as evidence item
        if diff:
            diff_content = diff.to_dict()
            items.append({
                "item_id": str(uuid.uuid4()),
                "evidence_type": "diff",
                "content_hash": self._compute_hash(diff_content),
                "content": diff_content,
                "created_at": now,
            })

        # Add event as audit evidence
        event_content = event.to_dict()
        items.append({
            "item_id": str(uuid.uuid4()),
            "evidence_type": "audit_event",
            "content_hash": self._compute_hash(event_content),
            "content": event_content,
            "created_at": now,
        })

        # Build hash chain
        hash_chain = self._build_hash_chain(items, bundle_id)

        # Compute root hash
        root_hash = self._compute_root_hash(hash_chain["entries"])

        bundle = {
            "bundle_id": bundle_id,
            "bead_id": bead_id or f"connector-{event.artifact_id}",
            "artifact_id": event.artifact_id,
            "from_version_id": event.from_version or "initial",
            "to_version_id": event.to_version or "current",
            "risk_tier": risk_tier,
            "scope": {
                "assertion_type": "change_evidence",
                "assertion_text": f"Evidence of change to {metadata.get('title', event.artifact_id)}",
                "artifact_id": event.artifact_id,
                "version_from": event.from_version or "initial",
                "version_to": event.to_version or "current",
                "policy_ids": [],
                "risk_tier_assessed": risk_tier,
                "assessment_date": now,
            },
            "items": items,
            "signatures": [],  # Unsigned by default
            "immutability_proof": {
                "proof_id": str(uuid.uuid4()),
                "bundle_id": bundle_id,
                "root_hash": root_hash,
                "hash_algorithm": "sha256",
                "hash_chain": hash_chain,
                "verified_at": None,
                "verification_status": "unverified",
            },
            "retention": {
                "policy": "standard",
                "retention_days": 365,
                "created_at": now,
                "expires_at": datetime.now(timezone.utc).replace(
                    year=datetime.now().year + 1
                ).isoformat(),
                "legal_hold": False,
                "compliance_frameworks": [],
            },
            "export_status": "pending",
            "integrity_status": "unverified",
            "created_at": now,
            "updated_at": now,
            "verified_at": None,
            "exported_at": None,
            "audit_trail": {
                "bundle_id": bundle_id,
                "entries": [{
                    "entry_id": str(uuid.uuid4()),
                    "bundle_id": bundle_id,
                    "action": "created",
                    "actor": {
                        "signer_id": f"connector:{metadata.get('connector_type', 'unknown')}",
                        "signer_type": "system",
                        "display_name": metadata.get("connector_name", "Connector"),
                    },
                    "timestamp": now,
                    "details": {"source": "connector", "event_type": event.event_type.value},
                }],
                "last_modified": now,
            },
        }

        return bundle

    def _compute_hash(self, content: Any) -> str:
        """Compute SHA-256 hash of content."""
        data = json.dumps(content, sort_keys=True, separators=(",", ":")).encode()
        h = hashlib.sha256(data).hexdigest()
        return f"sha256:{h}"

    def _build_hash_chain(
        self, items: list[dict[str, Any]], bundle_id: str
    ) -> dict[str, Any]:
        """Build hash chain from items."""
        entries = []
        prev_hash = None

        for i, item in enumerate(items):
            entry = {
                "sequence_number": i,
                "content_hash": item["content_hash"],
                "previous_hash": prev_hash,
                "timestamp": item["created_at"],
                "content_type": item["evidence_type"],
                "content_id": item["item_id"],
            }
            entries.append(entry)
            prev_hash = item["content_hash"]

        return {
            "chain_id": str(uuid.uuid4()),
            "entries": entries,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def _compute_root_hash(self, entries: list[dict[str, Any]]) -> str:
        """Compute Merkle root hash from chain entries."""
        hash_values = [e["content_hash"].replace("sha256:", "") for e in entries]
        concatenated = "".join(hash_values).encode()
        h = hashlib.sha256(concatenated).hexdigest()
        return f"sha256:{h}"

    async def _emit_to_api(self, bundle: dict[str, Any]) -> dict[str, Any]:
        """Send bundle to GuardSpine API."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/bundles",
                json=bundle,
                headers=headers,
            )
            response.raise_for_status()
            return response.json()

    async def _emit_to_file(self, bundle: dict[str, Any]) -> dict[str, Any]:
        """Write bundle to filesystem."""
        path = Path(self.file_path)  # type: ignore
        path.mkdir(parents=True, exist_ok=True)

        filename = f"bundle-{bundle['bundle_id']}.json"
        filepath = path / filename

        with open(filepath, "w") as f:
            json.dump(bundle, f, indent=2)

        bundle["_file_path"] = str(filepath)
        return bundle

    async def _emit_to_webhook(self, bundle: dict[str, Any]) -> dict[str, Any]:
        """POST bundle to webhook."""
        headers = {"Content-Type": "application/json", **self.webhook_headers}

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.webhook_url,  # type: ignore
                json=bundle,
                headers=headers,
            )
            response.raise_for_status()
            return bundle
