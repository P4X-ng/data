# PacketFS P-ASM (Packet Assembly) — Minimal Spec

Goal
- Provide a tiny, safe IR to drive execution via state transitions, not CPU ISA.
- Default to simulation (no privileged changes). Opt-in backends can map to real systems under explicit gating.

Core concepts
- Program = ordered list of steps (ops). Each step is idempotent where possible.
- Ops target abstract substrates (kv, pkt, log, barrier). More can be added later (dns, fw, lb).

Minimal ops (v0)
- state.set(scope, key, value)
  - Semantics: set an entry in a logical KV space. Default backend is an in-memory map; logged.
- pkt.send(target, payload, meta)
  - Semantics: send a packet to target. Default backend supports UDP only and only to 127.0.0.0/8.
  - target example: "udp://127.0.0.1:9999"
  - payload: UTF-8 string; meta: optional {ttl:int}
- log.info(message, fields)
  - Semantics: structured log event.
- barrier.sleep(ms)
  - Semantics: sleep the engine for a bounded duration (ms).

Program format
- JSON file (extension .pasm for readability). Example:
[
  {"op":"state.set","scope":"kv:/demo","key":"hello","value":"world"},
  {"op":"pkt.send","target":"udp://127.0.0.1:9999","payload":"Hello, world!","meta":{"ttl":64}},
  {"op":"log.info","message":"done","fields":{"msg_id":"hello1"}}
]

Planner rules (v0)
- Order is preserved.
- Each op becomes a single execution action.
- Planfile is written as plans/pasm_<timestamp>.json with run metadata and per-step outcomes.

Simulation backends (default)
- KV: in-memory dict; all writes logged to JSONL.
- pkt: UDP only; restrict to 127.0.0.0/8 for safety. Logged including byte counts.
- log: info-level JSONL event.
- barrier: sleep with cap (e.g., max 10s).

Safety gates
- No privileged system changes by default.
- Real backends (dns/fw/lb/af_packet) must be opt-in flags later.

Outputs
- Planfile (JSON) in plans/
- Event log JSONL in logs/ (pasm_run_<timestamp>.jsonl)

Future extensions
- Predicates and guards (barrier.wait on observed state).
- Additional backends (dns, nft, lb) in a test netns.
- Compiler from a tiny subset of assembly to P-ASM state ops.
