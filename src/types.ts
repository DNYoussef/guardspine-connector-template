/**
 * GuardSpine Evidence Bundle Schema v0.2.0
 *
 * These interfaces define the structure of evidence bundles that connectors
 * produce and emit to the GuardSpine kernel. All connectors MUST emit bundles
 * conforming to this schema version.
 */

export interface HashChainLink {
  sequence: number;
  item_id: string;
  content_type: string;
  content_hash: string;
  previous_hash: string;
  chain_hash: string;
}

export interface ImmutabilityProof {
  hash_chain: HashChainLink[];
  root_hash: string;
}

export interface EvidenceItem {
  /** Unique identifier for this evidence item */
  id: string;
  /** Source system that produced this evidence (e.g. "github", "jira") */
  source: string;
  /** Type of evidence (e.g. "commit", "review", "test-result", "deployment") */
  kind: string;
  /** ISO-8601 timestamp of when the evidence was created at source */
  createdAt: string;
  /** Arbitrary payload from the source system */
  payload: Record<string, unknown>;
  /** Optional tags for filtering and categorization */
  tags?: string[];
}

export interface BundleItem {
  item_id: string;
  sequence: number;
  content_type: string;
  content: Record<string, unknown>;
  content_hash: string;
}

export interface EvidenceBundle {
  version: "0.2.0";
  bundle_id: string;
  created_at: string;
  items: BundleItem[];
  immutability_proof: ImmutabilityProof;
  metadata?: Record<string, unknown>;
}

/**
 * Configuration that every connector receives on initialization.
 * Extend this interface with connector-specific options.
 */
export interface ConnectorConfig {
  /** Unique identifier for this connector instance */
  connectorId: string;
  /** Polling interval in milliseconds (0 = manual only) */
  pollIntervalMs?: number;
  /** Additional connector-specific settings */
  [key: string]: unknown;
}
