/**
 * GuardSpine Evidence Bundle Schema v0.2.0
 *
 * These interfaces define the structure of evidence bundles that connectors
 * produce and emit to the GuardSpine kernel. All connectors MUST emit bundles
 * conforming to this schema version.
 */

export interface HashChainLink {
  /** SHA-256 hash of this link's content */
  hash: string;
  /** Hash of the previous link in the chain (null for genesis) */
  previousHash: string | null;
  /** ISO-8601 timestamp when this link was created */
  timestamp: string;
}

export interface ImmutabilityProof {
  /** Schema version for the proof format */
  version: "0.2.0";
  /** Algorithm used for hashing (e.g. "sha256") */
  algorithm: string;
  /** Ordered chain of hashes proving integrity */
  chain: HashChainLink[];
  /** Root hash summarizing the entire bundle */
  rootHash: string;
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

export interface EvidenceBundle {
  /** Schema version -- MUST be "0.2.0" */
  schemaVersion: "0.2.0";
  /** Unique bundle identifier */
  bundleId: string;
  /** Connector that produced this bundle */
  connectorId: string;
  /** ISO-8601 timestamp of bundle creation */
  createdAt: string;
  /** Evidence items included in this bundle */
  items: EvidenceItem[];
  /** Cryptographic proof of bundle integrity */
  proof: ImmutabilityProof;
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
