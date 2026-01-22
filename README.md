# GuardSpine Connector Template

> **Build connectors that emit verifiable evidence bundles.**

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

This template provides the structure for building GuardSpine connectors - sidecars that integrate with document stores, code repositories, and workflow systems to emit evidence bundles.

## Architecture

```
+----------------+     +-------------------+     +------------------+
|  Source System |---->| GuardSpine        |---->| Evidence Bundle  |
|  (SharePoint,  |     | Connector         |     | (JSON/ZIP)       |
|   Drive, etc.) |     | (this template)   |     |                  |
+----------------+     +-------------------+     +------------------+
                              |
                              v
                       +------------------+
                       | GuardSpine API   |
                       | (webhooks)       |
                       +------------------+
```

## Quick Start

1. Copy this template
2. Implement the `Connector` interface
3. Configure credentials
4. Run as a sidecar

```bash
# Clone template
cp -r guardspine-connector-template my-sharepoint-connector

# Install dependencies
cd my-sharepoint-connector
pip install -e .

# Configure
cp config.example.yaml config.yaml
# Edit config.yaml with your credentials

# Run
guardspine-connector run --config config.yaml
```

## Project Structure

```
guardspine-connector-template/
+-- connector/
|   +-- __init__.py
|   +-- base.py          # Base connector class
|   +-- events.py        # Event types
|   +-- bundle_emitter.py # Bundle creation
+-- examples/
|   +-- github_connector.py
|   +-- sharepoint_connector.py
|   +-- jira_connector.py
|   +-- slack_connector.py
+-- config.example.yaml
+-- pyproject.toml
+-- README.md
```

## Implementing a Connector

```python
from connector import BaseConnector, ChangeEvent, BundleEmitter

class MyConnector(BaseConnector):
    """Connect to MySystem and emit evidence bundles."""

    def __init__(self, config: dict):
        super().__init__(config)
        self.client = MySystemClient(config["api_key"])

    async def watch_changes(self) -> AsyncIterator[ChangeEvent]:
        """Watch for changes and yield events."""
        async for event in self.client.watch():
            yield ChangeEvent(
                artifact_id=event.file_id,
                from_version=event.old_version,
                to_version=event.new_version,
                change_type=event.type,
                metadata=event.metadata,
            )

    async def get_diff(self, event: ChangeEvent) -> dict:
        """Get the diff for a change event."""
        return await self.client.get_diff(
            event.artifact_id,
            event.from_version,
            event.to_version,
        )

    async def get_artifact_metadata(self, artifact_id: str) -> dict:
        """Get artifact metadata."""
        return await self.client.get_file(artifact_id)
```

## Configuration

```yaml
# config.yaml
connector:
  type: "my-connector"
  name: "My SharePoint Connector"

source:
  api_url: "https://api.myservice.com"
  api_key: "${MY_API_KEY}"  # Environment variable

output:
  mode: "webhook"  # api | file | webhook
  webhook_url: "http://guardspine:8000/api/v1/webhooks/my-connector"
  api_key: "${GUARDSPINE_API_KEY}"

filters:
  include_paths:
    - "/documents/**"
    - "/policies/**"
  exclude_paths:
    - "/**/drafts/**"

risk_mapping:
  "/policies/**": "L3"
  "/documents/**": "L1"
  default: "L0"
```

## Event Types

| Event | Description |
|-------|-------------|
| `file_created` | New file added |
| `file_modified` | File content changed |
| `file_deleted` | File removed |
| `file_moved` | File location changed |
| `permission_changed` | Access permissions modified |
| `approval_requested` | Approval workflow started |
| `approval_granted` | Approval given |
| `approval_rejected` | Approval denied |

## Output Modes

### Webhook Mode (Recommended)
Posts events directly to GuardSpine webhook endpoint:
```yaml
output:
  mode: "webhook"
  webhook_url: "http://guardspine:8000/api/v1/webhooks/my-connector"
  headers:
    Authorization: "Bearer ${GUARDSPINE_API_KEY}"
```

### API Mode
Sends bundles directly to GuardSpine API:
```yaml
output:
  mode: "api"
  api_url: "http://guardspine:8000/api/v1"
  api_key: "${GUARDSPINE_API_KEY}"
```

### File Mode
Writes bundles to disk (for air-gapped environments):
```yaml
output:
  mode: "file"
  file_path: "./bundles"
  format: "json"  # or "zip"
```

## Integration with GuardSpine Phase 5

Connectors integrate with GuardSpine's Phase 5 webhook system:

```python
# Your connector sends events to GuardSpine
POST /api/v1/webhooks/{connector_id}
Content-Type: application/json
X-Connector-Signature: sha256=...

{
  "event_type": "file_modified",
  "artifact_id": "doc-123",
  "from_version": "v1",
  "to_version": "v2",
  "metadata": {...}
}
```

GuardSpine processes these events and:
- Creates/updates artifacts
- Links to Beads (work units)
- Triggers approval workflows
- Creates evidence bundles

## Testing

```bash
# Run tests
pytest

# Test with mock events
guardspine-connector test --mock-events 10

# Dry run (don't emit bundles)
guardspine-connector run --dry-run

# Validate config
guardspine-connector validate --config config.yaml
```

## Pre-built Connectors

| Connector | Status | Source |
|-----------|--------|--------|
| GitHub | Production | `examples/github_connector.py` |
| Jira | Production | `examples/jira_connector.py` |
| Slack | Production | `examples/slack_connector.py` |
| SharePoint | Template | Requires Microsoft Graph API |
| Google Drive | Template | Requires Google API |
| ServiceNow | Template | Requires ServiceNow API |
| Confluence | Template | Requires Atlassian API |

## Signature Verification

Connectors should sign webhook payloads:

```python
import hmac
import hashlib

def sign_payload(payload: bytes, secret: str) -> str:
    signature = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return f"sha256={signature}"
```

GuardSpine verifies signatures before processing events.

## Related Projects

| Project | Description |
|---------|-------------|
| [GuardSpine](https://github.com/DNYoussef/GuardSpine) | Full governance platform |
| [guardspine-spec](https://github.com/DNYoussef/guardspine-spec) | Bundle specification |
| [guardspine-verify](https://github.com/DNYoussef/guardspine-verify) | Offline verifier |

## License

Apache 2.0 - See [LICENSE](LICENSE).

---

**GuardSpine**: Verifiable governance evidence you don't have to trust.
