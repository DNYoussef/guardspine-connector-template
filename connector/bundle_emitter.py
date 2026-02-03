"""
Bundle emitter for creating evidence bundles from connector events.

UPDATED: Now uses guardspine-kernel-py for canonical hash operations.
This ensures cross-language parity with @guardspine/kernel (TypeScript).
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional

import httpx

from .events import ChangeEvent, DiffResult

# Import from canonical kernel package
try:
    from guardspine_kernel import (
        canonical_json,
        compute_content_hash,
        build_hash_chain,
        compute_root_hash,
        GENESIS_HASH,
    )
    _HAS_KERNEL = True
except ImportError:
    _HAS_KERNEL = False
    # Fallback will raise error at runtime if kernel is needed


KERNEL_VERSION = "0.2.0"


@dataclass
class BundleEmitter:
    """
    Creates and emits evidence bundles from connector events.

    Supports multiple output modes:
    - api: Send to GuardSpine API
    - file: Write to local filesystem
    - webhook: POST to webhook URL

    SECURITY: This emitter requires guardspine-kernel-py to be installed.
    Without the kernel, bundle creation will fail hard to prevent
    producing bundles with incorrect hash values.
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

        # SECURITY: Require kernel for hash operations
        if not _HAS_KERNEL:
            raise ImportError(
                "guardspine-kernel-py is required for bundle creation. "
                "Install with: pip install guardspine-kernel"
            )

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
        """Create bundle structure from event and diff using kernel functions."""
        bundle_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        # Build evidence items with kernel hash computation
        items = []
        sequence = 0

        # Add diff as evidence item
        if diff:
            diff_content = diff.to_dict()
            items.append({
                "item_id": str(uuid.uuid4()),
                "sequence": sequence,
                "content_type": "diff",
                "content_hash": compute_content_hash(diff_content),
                "content": diff_content,
                "created_at": now,
            })
            sequence += 1

        # Add event as audit evidence
        event_content = event.to_dict()
        items.append({
            "item_id": str(uuid.uuid4()),
            "sequence": sequence,
            "content_type": "audit_event",
            "content_hash": compute_content_hash(event_content),
            "content": event_content,
            "created_at": now,
        })

        # Build hash chain using kernel
        from guardspine_kernel.seal import ChainInput
        chain_inputs = [
            ChainInput(
                content=item["content"],
                content_type=item["content_type"],
                content_id=item["item_id"],
            )
            for item in items
        ]
        chain = build_hash_chain(chain_inputs)
        root_hash = compute_root_hash(chain)

        # Convert chain to dict format
        hash_chain = [link.to_dict() for link in chain]

        bundle = {
            "bundle_id": bundle_id,
            "version": KERNEL_VERSION,
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
                "hash_chain": hash_chain,
                "root_hash": root_hash,
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
