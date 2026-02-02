# @guardspine/connector-template

Starter template for building GuardSpine connectors. A connector pulls evidence artifacts from an external system (GitHub, Jira, CI pipelines, etc.) and emits them as v0.2.0 Evidence Bundles to the GuardSpine kernel.

## Quick Start

1. Clone or copy this template.
2. `npm install`
3. Edit `src/connector.ts`:
   - Implement `connect()` with your source system's auth.
   - Implement `fetchArtifacts()` to retrieve raw data.
   - Optionally override `transformToEvidenceItems()` for custom mapping.
4. `npm run build`

## Schema Compatibility

This template targets **Evidence Bundle schema v0.2.0**. The interfaces in `src/types.ts` match the v0.2.0 specification:

- `EvidenceBundle` -- top-level container with `schemaVersion: "0.2.0"`
- `EvidenceItem` -- individual evidence records with source, kind, and payload
- `ImmutabilityProof` -- SHA-256 hash chain proving bundle integrity
- `HashChainLink` -- single link in the hash chain

Bundles produced by `emitEvidenceBundle()` include a cryptographic hash chain so the kernel can verify that no items were added, removed, or modified after emission.

## Project Structure

```
src/
  types.ts       -- v0.2.0 schema interfaces
  connector.ts   -- Base connector class (customize this)
package.json
tsconfig.json
```

## Peer Dependency

Requires `@guardspine/kernel >= 0.2.0` as a peer dependency. The kernel provides the runtime that receives emitted bundles.
