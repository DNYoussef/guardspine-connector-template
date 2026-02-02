import { createHash, randomUUID } from "node:crypto";
import type {
  ConnectorConfig,
  EvidenceBundle,
  EvidenceItem,
  HashChainLink,
  ImmutabilityProof,
} from "./types";

/**
 * Base connector template for GuardSpine.
 *
 * To build a new connector:
 *   1. Copy this file and rename the class.
 *   2. Implement connect() with your source system's auth/setup.
 *   3. Implement fetchArtifacts() to pull raw data from the source.
 *   4. (Optional) Override transformToEvidenceItems() if you need
 *      custom mapping from raw artifacts to EvidenceItems.
 *   5. Call emitEvidenceBundle() to package items into a v0.2.0 bundle.
 */
export class GuardSpineConnector {
  protected config: ConnectorConfig;
  private connected = false;

  constructor(config: ConnectorConfig) {
    this.config = config;
  }

  // -------------------------------------------------------------------
  // Lifecycle -- customize these for your source system
  // -------------------------------------------------------------------

  /**
   * Establish a connection to the external source system.
   * Replace with real auth logic (API keys, OAuth, etc.).
   */
  async connect(): Promise<void> {
    // TODO: Add your authentication / connection logic here.
    // Example: this.client = new SourceClient(this.config.apiKey);
    this.connected = true;
  }

  /**
   * Gracefully tear down the connection.
   */
  async disconnect(): Promise<void> {
    // TODO: Clean up connections, flush buffers, etc.
    this.connected = false;
  }

  // -------------------------------------------------------------------
  // Data retrieval -- customize for your source
  // -------------------------------------------------------------------

  /**
   * Fetch raw artifacts from the source system.
   * Returns an array of arbitrary objects that will be transformed
   * into EvidenceItems.
   *
   * @param since - Optional ISO-8601 timestamp to fetch only newer artifacts.
   */
  async fetchArtifacts(since?: string): Promise<Record<string, unknown>[]> {
    this.ensureConnected();

    // TODO: Replace with real data fetching.
    // Example:
    //   const response = await this.client.getCommits({ since });
    //   return response.data;

    return [];
  }

  /**
   * Transform raw artifacts into typed EvidenceItems.
   * Override this if your source needs custom mapping.
   */
  protected transformToEvidenceItems(
    artifacts: Record<string, unknown>[],
  ): EvidenceItem[] {
    // TODO: Map each artifact to an EvidenceItem with the correct
    // source, kind, and payload for your connector.
    return artifacts.map((artifact) => ({
      id: randomUUID(),
      source: this.config.connectorId,
      kind: "generic",
      createdAt: new Date().toISOString(),
      payload: artifact,
    }));
  }

  // -------------------------------------------------------------------
  // Bundle emission -- generally no changes needed
  // -------------------------------------------------------------------

  /**
   * Package evidence items into a v0.2.0 EvidenceBundle with an
   * immutability proof (hash chain).
   */
  emitEvidenceBundle(items: EvidenceItem[]): EvidenceBundle {
    const proof = this.buildImmutabilityProof(items);

    return {
      schemaVersion: "0.2.0",
      bundleId: randomUUID(),
      connectorId: this.config.connectorId,
      createdAt: new Date().toISOString(),
      items,
      proof,
    };
  }

  /**
   * Convenience method: fetch, transform, and emit in one call.
   */
  async collectAndEmit(since?: string): Promise<EvidenceBundle> {
    const artifacts = await this.fetchArtifacts(since);
    const items = this.transformToEvidenceItems(artifacts);
    return this.emitEvidenceBundle(items);
  }

  // -------------------------------------------------------------------
  // Internal helpers
  // -------------------------------------------------------------------

  private buildImmutabilityProof(items: EvidenceItem[]): ImmutabilityProof {
    const chain: HashChainLink[] = [];
    let previousHash: string | null = null;

    for (const item of items) {
      const content = JSON.stringify(item);
      const hash = createHash("sha256").update(content).digest("hex");
      const link: HashChainLink = {
        hash,
        previousHash,
        timestamp: new Date().toISOString(),
      };
      chain.push(link);
      previousHash = hash;
    }

    const rootHash = createHash("sha256")
      .update(chain.map((l) => l.hash).join(""))
      .digest("hex");

    return {
      version: "0.2.0",
      algorithm: "sha256",
      chain,
      rootHash,
    };
  }

  private ensureConnected(): void {
    if (!this.connected) {
      throw new Error(
        "Connector is not connected. Call connect() before fetching artifacts.",
      );
    }
  }
}
