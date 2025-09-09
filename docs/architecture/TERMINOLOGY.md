# PacketFS Terminology (authoritative)

Date: 2025-09-06

Core concepts
- PacketFS (PFS): The system where files are represented and operated on as packet-native structures. Data motion and compute are expressed via descriptors (offset/length) over a large, kernel-managed, hugepage-backed blob.
- pCPU (packet CPU): Execution model where one state-changing PacketFS packet maps to one pCPU thread. A wave of M packets implies up to M concurrent pCPU threads.

Transport overlays
- PFS-TCP: PacketFS overlay using TCP as the underlying transport. You get PacketFS reduction plus TCP reliability/congestion control. Wire artifacts (retries, ordering) are handled by TCP; PacketFS handles reduction and descriptor semantics.
- PFS-UDP: PacketFS overlay using UDP as the underlying transport. You get PacketFS reduction with batching; PacketFS adds its own consistency plane (ACK/repair windows) as needed.

Transportless (native) modes
- PFS-Native Offset Mode: Pure PacketFS execution with no payload on the wire; reconstruction is via offset/length descriptors into a pre-shared randomized blob.
- PFS-Native Arithmetic Mode: Same as Offset Mode, but subsequent offsets are expressed relative to a base (± deltas, strides). This compacts descriptors and simplifies loops.

Relationship to prior naming
- “PacketFS‑gram” (older docs) maps to the overlay framing used by PFS-TCP and PFS-UDP (grams = batched frames with header + descriptor table [+ optional payload slab]).
- “Native PFS Offset-only/Arithmetic” in older docs aligns directly with PFS-Native Offset Mode and PFS-Native Arithmetic Mode here.

Naming conventions (docs and tooling)
- Prefer: PFS-TCP, PFS-UDP, PFS-Native Offset Mode, PFS-Native Arithmetic Mode.
- When referring to grams in overlays: say “PFS-TCP gram” or “PFS-UDP gram” (descriptor batches carried over TCP/UDP).
- Keep older names in historical sections with a pointer to this document for clarity.

Comparisons policy
- Compute comparisons: pCPU time vs conventional CPU (measured when possible; otherwise clearly labeled estimates).
- Transfer comparisons: PFS-TCP/UDP vs conventional tools (scp/rsync/…); same link, same environment.

Security terminology (summary)
- Confidentiality derives from secrecy of the pre-shared randomized blob and blueprint. To make claims equivalent to standard cryptography, use a well-vetted AEAD (e.g., AES‑GCM or XChaCha20‑Poly1305) keyed via seeds. See ../security/SECURITY_MODEL.md for details and assumptions.

