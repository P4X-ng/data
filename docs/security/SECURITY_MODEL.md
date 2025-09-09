# PacketFS Security Model and Cryptography Choices

Date: 2025-09-06

Threat model (summary)
- Adversary can observe, capture, and replay network traffic; cannot compromise endpoints.
- Confidentiality requires secrecy of: (a) the pre-shared randomized blob (or its cryptographic keystream), and (b) the blueprint/descriptor stream. Integrity requires detecting/handling tampering.

Two practical confidentiality constructions
1) Standard AEAD overlay (recommended)
   - Use an AEAD such as AES-256-GCM or XChaCha20-Poly1305. Derive per-session keys from seeds (KDF with salt and context). Encrypt any on-wire payloads and sensitive control channels (blueprints, descriptors if sent over untrusted links).
   - Pros: Strong, well-analyzed security; built-in integrity; hardware acceleration common; straightforward key rotation.
   - Notes: Even with offset-only flows (no payload bytes), protect descriptor/blueprint channels as they can leak structure.

2) Pre-shared blob as keystream (careful)
   - Treat the pre-shared randomized blob as a secret keystream source, and send only offsets/arithmetic over that private preimage. Without the blob and blueprint, wire observers see no plaintext.
   - Caveats: Security reduces to secrecy and unpredictability of the blob and strict avoidance of reuse/correlation that could leak structure. Lacking formal proofs, this should be documented as a design choice with bounded claims, or augmented by AEAD on control channels.

About one-time pads (OTP)
- A true OTP requires a truly random key of message length, used once and never reused. This is rarely operationally practical at scale. If pursued, document:
  - Key length = message length, one-time use, secure distribution, immediate destruction, and no segment reuse. Any deviation voids OTP guarantees.
  - In most deployments, a modern stream cipher (e.g., XChaCha20) offers strong security with sane operational properties and minimal CPU overhead (essentially XOR plus keystream generation).

Integrity and authenticity
- Use AEAD tags (GCM/Poly1305) for wire-level integrity. For offset-only primary streams, run a light integrity plane (checksum or MAC) and a corrections/repair plane to request missing bytes if verification fails.
- Replay protection: include nonces/sequence numbers in AEAD context; reject stale or duplicate frames.

Key management
- Derive keys via HKDF with strong salts and context (e.g., session IDs, role labels). Support rotation and rekeying per session/flow. Store long-term seeds securely (HSM or OS-managed keyrings); never embed secrets in code or logs.

Claims language (docs)
- Preferred phrasing: “Confidentiality derives from the secrecy of the pre-shared blob and blueprint; with standard AEAD (AES-GCM or XChaCha20-Poly1305) and sound key management, on-wire data are confidential and integrity-protected under conventional cryptographic assumptions.”
- Avoid: “stronger than any crypto,” “quantum encryption,” or similar. Use precise, testable statements.

Operational guidance
- Protect descriptor/blueprint channels, even in offset-only mode.
- Prefer boot-time hugepages and NUMA pinning to keep the blob resident and avoid page-fault or swap-based leakage.
- Log sizes and timings, not raw descriptors or keys. Scrub secrets in crash logs and core dumps.

