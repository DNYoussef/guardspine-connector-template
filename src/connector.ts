import { randomUUID } from "node:crypto";
import type {
  BundleItem,
  ConnectorConfig,
  EvidenceBundle,
  EvidenceItem,
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
   * Override for source-specific auth/setup.
   */
  async connect(): Promise<void> {
    this.connected = true;
  }

  /**
   * Gracefully tear down the connection.
   */
  async disconnect(): Promise<void> {
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
    void since;
    throw new Error(
      "fetchArtifacts() must be implemented by your connector subclass.",
    );
  }

  /**
   * Transform raw artifacts into typed EvidenceItems.
   * Override this if your source needs custom mapping.
   */
  protected transformToEvidenceItems(
    artifacts: Record<string, unknown>[],
  ): EvidenceItem[] {
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
   * kernel-generated immutability proof.
   */
  async emitEvidenceBundle(items: EvidenceItem[]): Promise<EvidenceBundle> {
    const kernel = await this.loadKernel();
    const createdAt = new Date().toISOString();
    const bundleId = randomUUID();
    const draft = {
      bundle_id: bundleId,
      version: "0.2.0" as const,
      created_at: createdAt,
      items: items.map((item, index) => this.toKernelItem(item, index)),
      metadata: {
        connector_id: this.config.connectorId,
      },
    };
    const sealed = kernel.sealBundle(draft) as {
      items?: BundleItem[];
      immutabilityProof?: { hashChain?: unknown[]; rootHash?: string };
    };

    if (!sealed?.items || !sealed?.immutabilityProof?.hashChain || !sealed?.immutabilityProof?.rootHash) {
      throw new Error("Kernel sealing failed to return v0.2.0 proof data.");
    }

    const proof = this.toProof(sealed.immutabilityProof.hashChain, sealed.immutabilityProof.rootHash);
    return {
      version: "0.2.0",
      bundle_id: bundleId,
      created_at: createdAt,
      items: sealed.items,
      immutability_proof: proof,
      metadata: draft.metadata,
    };
  }

  /**
   * Convenience method: fetch, transform, and emit in one call.
   */
  async collectAndEmit(since?: string): Promise<EvidenceBundle> {
    const artifacts = await this.fetchArtifacts(since);
    const items = this.transformToEvidenceItems(artifacts);
    return await this.emitEvidenceBundle(items);
  }

  // -------------------------------------------------------------------
  // Internal helpers
  // -------------------------------------------------------------------

  private async loadKernel(): Promise<{ sealBundle: (bundle: unknown) => unknown }> {
    let kernel: unknown;
    try {
      kernel = await import("@guardspine/kernel");
    } catch (err) {
      throw new Error(
        "@guardspine/kernel is required for sealing. Install with: npm install @guardspine/kernel",
      );
    }
    if (
      typeof kernel !== "object"
      || kernel === null
      || !("sealBundle" in kernel)
      || typeof (kernel as { sealBundle?: unknown }).sealBundle !== "function"
    ) {
      throw new Error("@guardspine/kernel does not expose sealBundle()");
    }
    return kernel as { sealBundle: (bundle: unknown) => unknown };
  }

  private toKernelItem(item: EvidenceItem, index: number): Record<string, unknown> {
    return {
      item_id: item.id || `item-${index}`,
      content_type: `guardspine/connector/${item.kind}`,
      content: {
        source: item.source,
        kind: item.kind,
        created_at: item.createdAt,
        payload: item.payload,
        tags: item.tags ?? [],
      },
    };
  }

  private toProof(chain: unknown[], rootHash: string): ImmutabilityProof {
    return {
      hash_chain: chain as ImmutabilityProof["hash_chain"],
      root_hash: rootHash,
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
