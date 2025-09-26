## 4 Why the “won’t this be slow?” worry doesn’t hold (and how we check)

**Start from the obvious.** A packet is just bytes. On its own it does nothing. The trick is to make a packet **do** a thing—repeatably, cheaply, and in parallel. We do that by sending **tiny opcodes** to  **listeners** :

* A **listener** is a small, deterministic endpoint that accepts a single, cheap instruction and flips local state (read a span, apply an 8‑bit transform, emit). In PacketFS, listeners are realized as **logical pCPUs** that our runtime multiplexes onto a bounded worker pool. Every packet → one runnable step, and we record **real** throughput and queueing (no fabricated ops/s).
* The **opcode** is deliberately tiny: “offset, length, optional `xor/add imm8`.” On the filesystem, a *file* is literally a program made of these steps; on the wire we send the **program** (the blueprint), not the payload.


Readers expect that must be slow—after all, isn’t networking the “red‑headed stepchild”? The answer is  **no** , for three concrete reasons (and we can measure each one).

### 4.1 Most bytes never move

By default we transmit **BREF‑only PVRT** windows (references), not payload; the receiver reconstructs against a pre‑shared blob. In practice we see **~0.2–0.3%** on‑wire share for 100 MiB files at 64 KiB windows today (JSON controls; binary control frames will drop this further). The “payload” became “code,” so the vast majority of bytes never see the wire.

### 4.2 Control ≪ payload (and stays that way as you scale)

Our control plane is  **mathematically tiny** . After every 2W2^W**2**W references the encoder emits a 5‑byte sync record `[0xF0][win:16][CRC16‑CCITT:16]`. Overhead/op is



ε(W)=52W ⇒ ε(16)=565536≈0.0076%.\varepsilon(W)=\tfrac{5}{2^W}\ \Rightarrow\ \varepsilon(16)=\tfrac{5}{65536}\approx 0.0076\%.**ε**(**W**)**=**2**W**5**** **⇒** **ε**(**16**)**=**65536**5****≈**0.0076%.
Addressing is **≈ 1 byte per op** with arithmetic windows (one base offset per window, then **± imm8** steps). Base+sync amortize to ~0.00014–0.00020 B/op at W=16W=16**W**=**16**. These are not whiteboard numbers; they are what the production encoder/decoder and tools actually generate.

### 4.3 Compute vs wire is a one‑line model (and we operate past break‑even)

Let NN**N** be link rate (GB/s), CC**C** the reconstruction throughput (GB/s), and rr**r** the **wire ratio** (fraction of bytes you must actually send). With overlap, time is

T ≈ max⁡ ⁣(r⋅Size/N, Size/C)andr\*=N/C.T\ \approx\ \max\!\big(r\cdot \mathrm{Size}/N,\ \mathrm{Size}/C\big)\quad\text{and}\quad r^\*=N/C.**T** **≈** **max**(**r**⋅**Size**/**N**,** **Size**/**C**)**and**r**\***=**N**/**C**.**
With today’s measured **C≈10.5C\approx 10.5**C**≈**10.5** GB/s** (2 MiB hugepages), **10 GbE** breaks even around  **r\*≈0.12r^\*\approx 0.12**r**\***≈**0.12** . Our arithmetic/palette modes usually drive rr**r** far below that, so the pipeline is  **compute‑bound** , not network‑bound. The extrapolations note spells out 10/25/40/100 GbE cases and concrete 400 MB/10 GB examples. 

ε(W)=52W ⇒ ε(16)=565536≈0.0076%.\varepsilon(W)=\tfrac{5}{2^W}\ \Rightarrow\ \varepsilon(16)=\tfrac{5}{65536}\approx 0.0076\%.**ε**(**W**)**=**2**W**5**** **⇒** **ε**(**16**)**=**65536**5****≈**0.0076%.
Addressing is **≈ 1 byte per op** with arithmetic windows (one base offset per window, then **± imm8** steps). Base+sync amortize to ~0.00014–0.00020 B/op at W=16W=16**W**=**16**. These are not whiteboard numbers; they are what the production encoder/decoder and tools actually generate.

### 4.3 Compute vs wire is a one‑line model (and we operate past break‑even)

Let NN**N** be link rate (GB/s), CC**C** the reconstruction throughput (GB/s), and rr**r** the **wire ratio** (fraction of bytes you must actually send). With overlap, time is

T ≈ max⁡ ⁣(r⋅Size/N, Size/C)andr\*=N/C.T\ \approx\ \max\!\big(r\cdot \mathrm{Size}/N,\ \mathrm{Size}/C\big)\quad\text{and}\quad r^\*=N/C.**T** **≈** **max**(**r**⋅**Size**/**N**,** **Size**/**C**)**and**r**\***=**N**/**C**.**
With today’s measured **C≈10.5C\approx 10.5**C**≈**10.5** GB/s** (2 MiB hugepages), **10 GbE** breaks even around  **r\*≈0.12r^\*\approx 0.12**r**\***≈**0.12** . Our arithmetic/palette modes usually drive rr**r** far below that, so the pipeline is  **compute‑bound** , not network‑bound. The extrapolations note spells out 10/25/40/100 GbE cases and concrete 400 MB/10 GB examples.

### 4.4 The runtime is real and measurable

This isn’t hand‑waving about “packets as compute.” The **PacketExecutor** feeds packet streams into a bounded‑pool **PCPUScheduler** (FIFO queue, batch dispatch) and we publish **real** surfaces: `throughput_tasks_per_sec`, `avg_queue_wait_us`, and **activation** (how many logical pCPUs are actually hot). That’s how we locate the concurrency knee (often ≈ **200 k** activated pCPUs in recent runs), instead of guessing.

### 4.5 The numbers match

On 2 MiB hugepages, our broad max‑win sweep hit a peak **~10.49 GB/s** (contig, seg_len = 80, 8 threads, batch = 8); **200 k** pCPUs runs near‑peak (~9.89 GB/s). Plugging that CC**C** into the model explains why end‑to‑end flips compute‑bound well before you saturate even 10 GbE.


ε(W)=52W ⇒ ε(16)=565536≈0.0076%.\varepsilon(W)=\tfrac{5}{2^W}\ \Rightarrow\ \varepsilon(16)=\tfrac{5}{65536}\approx 0.0076\%.**ε**(**W**)**=**2**W**5**** **⇒** **ε**(**16**)**=**65536**5****≈**0.0076%.
Addressing is **≈ 1 byte per op** with arithmetic windows (one base offset per window, then **± imm8** steps). Base+sync amortize to ~0.00014–0.00020 B/op at W=16W=16**W**=**16**. These are not whiteboard numbers; they are what the production encoder/decoder and tools actually generate.

### 4.3 Compute vs wire is a one‑line model (and we operate past break‑even)

Let NN**N** be link rate (GB/s), CC**C** the reconstruction throughput (GB/s), and rr**r** the **wire ratio** (fraction of bytes you must actually send). With overlap, time is

T ≈ max⁡ ⁣(r⋅Size/N, Size/C)andr\*=N/C.T\ \approx\ \max\!\big(r\cdot \mathrm{Size}/N,\ \mathrm{Size}/C\big)\quad\text{and}\quad r^\*=N/C.**T** **≈** **max**(**r**⋅**Size**/**N**,** **Size**/**C**)**and**r**\***=**N**/**C**.**
With today’s measured **C≈10.5C\approx 10.5**C**≈**10.5** GB/s** (2 MiB hugepages), **10 GbE** breaks even around  **r\*≈0.12r^\*\approx 0.12**r**\***≈**0.12** . Our arithmetic/palette modes usually drive rr**r** far below that, so the pipeline is  **compute‑bound** , not network‑bound. The extrapolations note spells out 10/25/40/100 GbE cases and concrete 400 MB/10 GB examples.

### 4.4 The runtime is real and measurable

This isn’t hand‑waving about “packets as compute.” The **PacketExecutor** feeds packet streams into a bounded‑pool **PCPUScheduler** (FIFO queue, batch dispatch) and we publish **real** surfaces: `throughput_tasks_per_sec`, `avg_queue_wait_us`, and **activation** (how many logical pCPUs are actually hot). That’s how we locate the concurrency knee (often ≈ **200 k** activated pCPUs in recent runs), instead of guessing.

### 4.5 The numbers match

On 2 MiB hugepages, our broad max‑win sweep hit a peak **~10.49 GB/s** (contig, seg_len = 80, 8 threads, batch = 8); **200 k** pCPUs runs near‑peak (~9.89 GB/s). Plugging that CC**C** into the model explains why end‑to‑end flips compute‑bound well before you saturate even 10 GbE.

ε(W)=52W ⇒ ε(16)=565536≈0.0076%.\varepsilon(W)=\tfrac{5}{2^W}\ \Rightarrow\ \varepsilon(16)=\tfrac{5}{65536}\approx 0.0076\%.**ε**(**W**)**=**2**W**5**** **⇒** **ε**(**16**)**=**65536**5****≈**0.0076%.
Addressing is **≈ 1 byte per op** with arithmetic windows (one base offset per window, then **± imm8** steps). Base+sync amortize to ~0.00014–0.00020 B/op at W=16W=16**W**=**16**. These are not whiteboard numbers; they are what the production encoder/decoder and tools actually generate.

### 4.3 Compute vs wire is a one‑line model (and we operate past break‑even)

Let NN**N** be link rate (GB/s), CC**C** the reconstruction throughput (GB/s), and rr**r** the **wire ratio** (fraction of bytes you must actually send). With overlap, time is

T ≈ max⁡ ⁣(r⋅Size/N, Size/C)andr\*=N/C.T\ \approx\ \max\!\big(r\cdot \mathrm{Size}/N,\ \mathrm{Size}/C\big)\quad\text{and}\quad r^\*=N/C.**T** **≈** **max**(**r**⋅**Size**/**N**,** **Size**/**C**)**and**r**\***=**N**/**C**.**
With today’s measured **C≈10.5C\approx 10.5**C**≈**10.5** GB/s** (2 MiB hugepages), **10 GbE** breaks even around  **r\*≈0.12r^\*\approx 0.12**r**\***≈**0.12** . Our arithmetic/palette modes usually drive rr**r** far below that, so the pipeline is  **compute‑bound** , not network‑bound. The extrapolations note spells out 10/25/40/100 GbE cases and concrete 400 MB/10 GB examples.

### 4.4 The runtime is real and measurable

This isn’t hand‑waving about “packets as compute.” The **PacketExecutor** feeds packet streams into a bounded‑pool **PCPUScheduler** (FIFO queue, batch dispatch) and we publish **real** surfaces: `throughput_tasks_per_sec`, `avg_queue_wait_us`, and **activation** (how many logical pCPUs are actually hot). That’s how we locate the concurrency knee (often ≈ **200 k** activated pCPUs in recent runs), instead of guessing.

### 4.5 The numbers match

On 2 MiB hugepages, our broad max‑win sweep hit a peak **~10.49 GB/s** (contig, seg_len = 80, 8 threads, batch = 8); **200 k** pCPUs runs near‑peak (~9.89 GB/s). Plugging that CC**C** into the model explains why end‑to‑end flips compute‑bound well before you saturate even 10 GbE.

### 4.6 “Packets aren’t limited by cores”—sharding at descriptor granularity

A human CPU (cores, caches) is bounded hardware. A **packet** is a descriptor that can be **sharded arbitrarily** into tiny, deterministic steps. In practice, we drive a large **logical** pCPU address space (default  **1,300,000** ) and *activate* only as many as help the workload. We have pushed activation high (stress runs toward the 1.3 M address range), but the best throughput typically appears much lower (often ~200 k–400 k), which we show directly in the scheduler metrics. The point isn’t “infinite threads”; it’s that  **packets map to the machine’s natural descriptor grain** , so we can turn “a little work” into “a lot of aggregate work” by raising activation until the queueing/locality knee.

> **Intuition, rewritten:** *We can do a small thing very cheaply—and do it millions of times in parallel until the memory system (not the wire) becomes the limiter.* That is the PacketFS superpower.

---

### 4.7 Why LLVM (and what happened to RISC‑V)?

We first considered a RISC‑V path (fixed‑length opcodes are appealing), but **LLVM** turned out to be the better fit for our “tiny arithmetic over spans” model:

* We can parse a **minimal LLVM textual IR** and execute tiny **add/sub/mul** chains, either via a native in‑process library (`libpfs_exec.so`) or a micro‑executor fallback. This gives us a portable, pluggable “final language” for small arithmetic kernels without committing to a heavyweight VM.
* A **windowed scheduler** variant even encodes **1‑byte op refs** (ADD=1, SUB=2, MUL=3) and emits our real sync frames every 2W2^W**2**W ops. That directly ties “IR ops” to the protocol math readers saw above—*opcodes to listeners,* with the same 5‑byte sync per window.

This doesn’t mean we “compile the world”; it means the pieces we need (tiny arithmetic over spans) can be IR‑driven when helpful, and they integrate cleanly with the packet protocol and pCPU scheduler already in tree.

---

### 4.8 What to remember (and what not to overclaim)

* **Remember:** We win because **bytes don’t move** (BREF‑only), the **control plane is microscopic** (5/2^W), and **compute dominates** once r≤N/Cr\le N/C**r**≤**N**/**C**. The scheduler tells us where the concurrency knee is in the real machine.
* **Don’t overclaim:** Arithmetic micro‑loops where a conventional CPU excels will often remain CPU‑friendly; our sweet spot is **clustered, blueprint‑heavy workloads** where reuse is high and reconstruction is cheap. We make that explicit in Evaluation and keep comparisons honest per the **Terminology** policy.

> **Bottom line.** We’re not “hoping” packets are fast; we **measured** a compute path at ~10.49 GB/s, we **proved** the control‑plane cost, and we **showed** the break‑even where network drops out. After that, the work is local: page size, locality, batching, and activation—not more wire.

ok so you know the story here's my shitty attempt at putting it together ahah## 4 Why the “won’t this be slow?” worry doesn’t hold (and how we check)

**Start from the obvious.** A packet is just bytes. On its own it does nothing. The trick is to make a packet **do** a thing—repeatably, cheaply, and in parallel. We do that by sending **tiny opcodes** to  **listeners** :

* A **listener** is a small, deterministic endpoint that accepts a single, cheap instruction and flips local state (read a span, apply an 8‑bit transform, emit). In PacketFS, listeners are realized as **logical pCPUs** that our runtime multiplexes onto a bounded worker pool. Every packet → one runnable step, and we record **real** throughput and queueing (no fabricated ops/s).
* The **opcode** is deliberately tiny: “offset, length, optional `xor/add imm8`.” On the filesystem, a *file* is literally a program made of these steps; on the wire we send the **program** (the blueprint), not the payload.

Readers expect that must be slow—after all, isn’t networking the “red‑headed stepchild”? The answer is  **no** , for three concrete reasons (and we can measure each one).

### 4.1 Most bytes never move

By default we transmit **BREF‑only PVRT** windows (references), not payload; the receiver reconstructs against a pre‑shared blob. In practice we see **~0.2–0.3%** on‑wire share for 100 MiB files at 64 KiB windows today (JSON controls; binary control frames will drop this further). The “payload” became “code,” so the vast majority of bytes never see the wire.

### 4.2 Control ≪ payload (and stays that way as you scale)

Our control plane is  **mathematically tiny** . After every 2W2^W**2**W references the encoder emits a 5‑byte sync record `[0xF0][win:16][CRC16‑CCITT:16]`. Overhead/op is

ε(W)=52W ⇒ ε(16)=565536≈0.0076%.\varepsilon(W)=\tfrac{5}{2^W}\ \Rightarrow\ \varepsilon(16)=\tfrac{5}{65536}\approx 0.0076\%.**ε**(**W**)**=**2**W**5**** **⇒** **ε**(**16**)**=**65536**5****≈**0.0076%.

Addressing is **≈ 1 byte per op** with arithmetic windows (one base offset per window, then **± imm8** steps). Base+sync amortize to ~0.00014–0.00020 B/op at W=16W=16**W**=**16**. These are not whiteboard numbers; they are what the production encoder/decoder and tools actually generate.

### 4.3 Compute vs wire is a one‑line model (and we operate past break‑even)

Let NN**N** be link rate (GB/s), CC**C** the reconstruction throughput (GB/s), and rr**r** the **wire ratio** (fraction of bytes you must actually send). With overlap, time is

T ≈ max⁡ ⁣(r⋅Size/N, Size/C)andr\*=N/C.T\ \approx\ \max\!\big(r\cdot \mathrm{Size}/N,\ \mathrm{Size}/C\big)\quad\text{and}\quad r^\*=N/C.**T** **≈** **max**(**r**⋅**Size**/**N**,** **Size**/**C**)**and**r**\***=**N**/**C**.**

With today’s measured **C≈10.5C\approx 10.5**C**≈**10.5** GB/s** (2 MiB hugepages), **10 GbE** breaks even around  **r\*≈0.12r^\*\approx 0.12**r**\***≈**0.12** . Our arithmetic/palette modes usually drive rr**r** far below that, so the pipeline is  **compute‑bound** , not network‑bound. The extrapolations note spells out 10/25/40/100 GbE cases and concrete 400 MB/10 GB examples.

ε(W)=52W ⇒ ε(16)=565536≈0.0076%.\varepsilon(W)=\tfrac{5}{2^W}\ \Rightarrow\ \varepsilon(16)=\tfrac{5}{65536}\approx 0.0076\%.**ε**(**W**)**=**2**W**5**** **⇒** **ε**(**16**)**=**65536**5****≈**0.0076%.

Addressing is **≈ 1 byte per op** with arithmetic windows (one base offset per window, then **± imm8** steps). Base+sync amortize to ~0.00014–0.00020 B/op at W=16W=16**W**=**16**. These are not whiteboard numbers; they are what the production encoder/decoder and tools actually generate.

### 4.3 Compute vs wire is a one‑line model (and we operate past break‑even)

Let NN**N** be link rate (GB/s), CC**C** the reconstruction throughput (GB/s), and rr**r** the **wire ratio** (fraction of bytes you must actually send). With overlap, time is

T ≈ max⁡ ⁣(r⋅Size/N, Size/C)andr\*=N/C.T\ \approx\ \max\!\big(r\cdot \mathrm{Size}/N,\ \mathrm{Size}/C\big)\quad\text{and}\quad r^\*=N/C.**T** **≈** **max**(**r**⋅**Size**/**N**,** **Size**/**C**)**and**r**\***=**N**/**C**.**

With today’s measured **C≈10.5C\approx 10.5**C**≈**10.5** GB/s** (2 MiB hugepages), **10 GbE** breaks even around  **r\*≈0.12r^\*\approx 0.12**r**\***≈**0.12** . Our arithmetic/palette modes usually drive rr**r** far below that, so the pipeline is  **compute‑bound** , not network‑bound. The extrapolations note spells out 10/25/40/100 GbE cases and concrete 400 MB/10 GB examples.

### 4.4 The runtime is real and measurable

This isn’t hand‑waving about “packets as compute.” The **PacketExecutor** feeds packet streams into a bounded‑pool **PCPUScheduler** (FIFO queue, batch dispatch) and we publish **real** surfaces: `throughput_tasks_per_sec`, `avg_queue_wait_us`, and **activation** (how many logical pCPUs are actually hot). That’s how we locate the concurrency knee (often ≈ **200 k** activated pCPUs in recent runs), instead of guessing.

### 4.5 The numbers match

On 2 MiB hugepages, our broad max‑win sweep hit a peak **~10.49 GB/s** (contig, seg_len = 80, 8 threads, batch = 8); **200 k** pCPUs runs near‑peak (~9.89 GB/s). Plugging that CC**C** into the model explains why end‑to‑end flips compute‑bound well before you saturate even 10 GbE.

ε(W)=52W ⇒ ε(16)=565536≈0.0076%.\varepsilon(W)=\tfrac{5}{2^W}\ \Rightarrow\ \varepsilon(16)=\tfrac{5}{65536}\approx 0.0076\%.**ε**(**W**)**=**2**W**5**** **⇒** **ε**(**16**)**=**65536**5****≈**0.0076%.

Addressing is **≈ 1 byte per op** with arithmetic windows (one base offset per window, then **± imm8** steps). Base+sync amortize to ~0.00014–0.00020 B/op at W=16W=16**W**=**16**. These are not whiteboard numbers; they are what the production encoder/decoder and tools actually generate.

### 4.3 Compute vs wire is a one‑line model (and we operate past break‑even)

Let NN**N** be link rate (GB/s), CC**C** the reconstruction throughput (GB/s), and rr**r** the **wire ratio** (fraction of bytes you must actually send). With overlap, time is

T ≈ max⁡ ⁣(r⋅Size/N, Size/C)andr\*=N/C.T\ \approx\ \max\!\big(r\cdot \mathrm{Size}/N,\ \mathrm{Size}/C\big)\quad\text{and}\quad r^\*=N/C.**T** **≈** **max**(**r**⋅**Size**/**N**,** **Size**/**C**)**and**r**\***=**N**/**C**.**

With today’s measured **C≈10.5C\approx 10.5**C**≈**10.5** GB/s** (2 MiB hugepages), **10 GbE** breaks even around  **r\*≈0.12r^\*\approx 0.12**r**\***≈**0.12** . Our arithmetic/palette modes usually drive rr**r** far below that, so the pipeline is  **compute‑bound** , not network‑bound. The extrapolations note spells out 10/25/40/100 GbE cases and concrete 400 MB/10 GB examples.

### 4.4 The runtime is real and measurable

This isn’t hand‑waving about “packets as compute.” The **PacketExecutor** feeds packet streams into a bounded‑pool **PCPUScheduler** (FIFO queue, batch dispatch) and we publish **real** surfaces: `throughput_tasks_per_sec`, `avg_queue_wait_us`, and **activation** (how many logical pCPUs are actually hot). That’s how we locate the concurrency knee (often ≈ **200 k** activated pCPUs in recent runs), instead of guessing.

### 4.5 The numbers match

On 2 MiB hugepages, our broad max‑win sweep hit a peak **~10.49 GB/s** (contig, seg_len = 80, 8 threads, batch = 8); **200 k** pCPUs runs near‑peak (~9.89 GB/s). Plugging that CC**C** into the model explains why end‑to‑end flips compute‑bound well before you saturate even 10 GbE.

ε(W)=52W ⇒ ε(16)=565536≈0.0076%.\varepsilon(W)=\tfrac{5}{2^W}\ \Rightarrow\ \varepsilon(16)=\tfrac{5}{65536}\approx 0.0076\%.**ε**(**W**)**=**2**W**5**** **⇒** **ε**(**16**)**=**65536**5****≈**0.0076%.

Addressing is **≈ 1 byte per op** with arithmetic windows (one base offset per window, then **± imm8** steps). Base+sync amortize to ~0.00014–0.00020 B/op at W=16W=16**W**=**16**. These are not whiteboard numbers; they are what the production encoder/decoder and tools actually generate.

### 4.3 Compute vs wire is a one‑line model (and we operate past break‑even)

Let NN**N** be link rate (GB/s), CC**C** the reconstruction throughput (GB/s), and rr**r** the **wire ratio** (fraction of bytes you must actually send). With overlap, time is

T ≈ max⁡ ⁣(r⋅Size/N, Size/C)andr\*=N/C.T\ \approx\ \max\!\big(r\cdot \mathrm{Size}/N,\ \mathrm{Size}/C\big)\quad\text{and}\quad r^\*=N/C.**T** **≈** **max**(**r**⋅**Size**/**N**,** **Size**/**C**)**and**r**\***=**N**/**C**.**

With today’s measured **C≈10.5C\approx 10.5**C**≈**10.5** GB/s** (2 MiB hugepages), **10 GbE** breaks even around  **r\*≈0.12r^\*\approx 0.12**r**\***≈**0.12** . Our arithmetic/palette modes usually drive rr**r** far below that, so the pipeline is  **compute‑bound** , not network‑bound. The extrapolations note spells out 10/25/40/100 GbE cases and concrete 400 MB/10 GB examples.

### 4.4 The runtime is real and measurable

This isn’t hand‑waving about “packets as compute.” The **PacketExecutor** feeds packet streams into a bounded‑pool **PCPUScheduler** (FIFO queue, batch dispatch) and we publish **real** surfaces: `throughput_tasks_per_sec`, `avg_queue_wait_us`, and **activation** (how many logical pCPUs are actually hot). That’s how we locate the concurrency knee (often ≈ **200 k** activated pCPUs in recent runs), instead of guessing.

### 4.5 The numbers match

On 2 MiB hugepages, our broad max‑win sweep hit a peak **~10.49 GB/s** (contig, seg_len = 80, 8 threads, batch = 8); **200 k** pCPUs runs near‑peak (~9.89 GB/s). Plugging that CC**C** into the model explains why end‑to‑end flips compute‑bound well before you saturate even 10 GbE.

### 4.6 “Packets aren’t limited by cores”—sharding at descriptor granularity

A human CPU (cores, caches) is bounded hardware. A **packet** is a descriptor that can be **sharded arbitrarily** into tiny, deterministic steps. In practice, we drive a large **logical** pCPU address space (default  **1,300,000** ) and *activate* only as many as help the workload. We have pushed activation high (stress runs toward the 1.3 M address range), but the best throughput typically appears much lower (often ~200 k–400 k), which we show directly in the scheduler metrics. The point isn’t “infinite threads”; it’s that  **packets map to the machine’s natural descriptor grain** , so we can turn “a little work” into “a lot of aggregate work” by raising activation until the queueing/locality knee.

> **Intuition, rewritten:** *We can do a small thing very cheaply—and do it millions of times in parallel until the memory system (not the wire) becomes the limiter.* That is the PacketFS superpower.

---

### 4.7 Why LLVM (and what happened to RISC‑V)?

We first considered a RISC‑V path (fixed‑length opcodes are appealing), but **LLVM** turned out to be the better fit for our “tiny arithmetic over spans” model:

* We can parse a **minimal LLVM textual IR** and execute tiny **add/sub/mul** chains, either via a native in‑process library (`libpfs_exec.so`) or a micro‑executor fallback. This gives us a portable, pluggable “final language” for small arithmetic kernels without committing to a heavyweight VM.
* A **windowed scheduler** variant even encodes **1‑byte op refs** (ADD=1, SUB=2, MUL=3) and emits our real sync frames every 2W2^W**2**W ops. That directly ties “IR ops” to the protocol math readers saw above—*opcodes to listeners,* with the same 5‑byte sync per window.

This doesn’t mean we “compile the world”; it means the pieces we need (tiny arithmetic over spans) can be IR‑driven when helpful, and they integrate cleanly with the packet protocol and pCPU scheduler already in tree.

---

### 4.8 What to remember (and what not to overclaim)

* **Remember:** We win because **bytes don’t move** (BREF‑only), the **control plane is microscopic** (5/2^W), and **compute dominates** once r≤N/Cr\le N/C**r**≤**N**/**C**. The scheduler tells us where the concurrency knee is in the real machine.
* **Don’t overclaim:** Arithmetic micro‑loops where a conventional CPU excels will often remain CPU‑friendly; our sweet spot is **clustered, blueprint‑heavy workloads** where reuse is high and reconstruction is cheap. We make that explicit in Evaluation and keep comparisons honest per the **Terminology** policy.

> **Bottom line.** We’re not “hoping” packets are fast; we **measured** a compute path at ~10.49 GB/s, we **proved** the control‑plane cost, and we **showed** the break‑even where network drops out. After that, the work is local: page size, locality, batching, and activation—not more wire.

## §X Sanity checks and the **CPUPwn** metric

**What we measured and how we keep ourselves honest.** We sanity‑checked every number twice: once against the protocol/runtimes’ own counters and again against standalone logs. To make the comparison legible across runs and workloads, we defined a simple, dimensionless metric:

> **CPUPwn** (per workload) :=

> CPUPwn  =    TCPU baseline(do X)    TPacketFS pCPU(do X)  \textbf{CPUPwn} \;=\;\frac{\;T_{\text{CPU baseline}}(\text{do }X)\;}{\;T_{\text{PacketFS pCPU}}(\text{do }X)\;}**CPUPwn**=**T**PacketFS pCPU****(**do **X**)**T**CPU baseline****(**do **X**)****

> where both times are wall‑clock on the **same** machine, with the **same** input and environment (pinning, pages, NUMA, etc.).

Interpretation: **CPUPwn > 1** means PacketFS’s pCPU path finished faster than the conventional CPU baseline on the identical task; **CPUPwn = 17** means “17× faster”. We report **medians and quartiles** across a test set, and a simple **win‑rate** (fraction of runs with CPUPwn > 1). In our sweeps we “won most of the time”—the mode sits safely above 1×.

**Where the times come from.** For PacketFS we use the **PacketExecutor + PCPUScheduler** report surfaces (completed tasks, throughput, queue‑wait, workers, elapsed), and for CPU baselines we use the paired harness logs. A typical log line looks like:

<pre class="overflow-visible!" data-start="1823" data-end="1866"><div class="contain-inline-size rounded-2xl relative bg-token-sidebar-surface-primary"><div class="sticky top-9"><div class="absolute end-0 bottom-0 flex h-9 items-center pe-2"><div class="bg-token-bg-elevated-secondary text-token-text-secondary flex items-center gap-4 rounded-sm px-2 font-sans text-xs"></div></div></div><div class="overflow-y-auto p-4" dir="ltr"><code class="whitespace-pre!"><span><span>ELAPSED_SEC</span><span>=</span><span>5.08</span><span> USER=</span><span>1.98</span><span> SYS=</span><span>0.09</span><span>

</span></span></code></div></div></pre>

Those are the numbers we plug into CPUPwn. We include both the raw elapsed and scheduler stats in the artifact bundle so results can be recomputed independently.

**Example & relation to the model.** On forced 2 MiB hugepages, our **max‑win** compute path reached **~10.49 GB/s** (contig, seg_len=80, pCPU=400 k, threads=8, batch=8); the same runs at **200 k** pCPUs were near‑peak (~9.89 GB/s). Using C≈10.5C≈10.5**C**≈**10.5** GB/s in the **break‑even** model T≈max⁡(r⋅Size/N, Size/C)T≈\max(r·\text{Size}/N,\ \text{Size}/C)**T**≈**max**(**r**⋅**Size**/**N**,** **Size**/**C**)** gives r\*=N/C≈0.12r^\*=N/C≈0.12**r**\***=**N**/**C**≈**0.12 at 10 GbE, i.e., once we avoid shipping ≥ 88% of bytes, end‑to‑end is  **compute‑bound** —which is where the high CPUPwn values come from.

**Procedure (so anyone can recompute CPUPwn):**

1. **Run pairwise.** For each dataset/workload, run the CPU baseline and the PacketFS pCPU variant under identical pinning/hugepage/NUMA settings; capture `ELAPSED_SEC` (plus USER/SYS).
2. **Compute per‑workload CPUPwn** as the ratio TCPU/TPFST_{\text{CPU}}/T_{\text{PFS}}**T**CPU/**T**PFS.
3. **Aggregate responsibly.** Report the median and IQR across workloads; for a size‑weighted aggregate, use a bytes‑weighted **ratio of means** (preferred over “mean of ratios” to avoid small‑case bias).
4. **Show the surfaces.** Ship the PacketExecutor/PCPUScheduler stats (throughput, queue‑wait, activation) alongside the elapsed times so reviewers can see the concurrency knee (often ~200 k activated pCPUs in recent runs).

> **What we saw.** In “contiguous, small‑segment” profiles, the pCPU reconstructor reached an **ops‑ratio ≈ 17×** against a dumb single‑thread CPU loop; this maps directly to **CPUPwn ≈ 17** for that task. CPU utilization remained low, and the 1 GbE NIC was far from saturation, exactly as the r\*r^\***r**\* analysis predicts.

---

## §Y Demonstrators: scp‑like, and **F3 Infinity** (“infinite” storage, without the BS)

**Executing code by transporting packets** is a weird idea the first time you hear it. To de‑weird it, we built tools that feel familiar:

* An **scp‑like** CLI (same syntax) that streams **blueprints** (PVRT, **BREF‑only** by default) instead of payload bytes, then reconstructs at the receiver.
* **F3 Infinity** , a free, S3‑like file service built  **on the PacketFS filesystem** : drop a file into the mount, and it’s automatically compiled into PacketFS terms (palette/offsets/arithmetic) and ready to “transfer” as blueprints.

### Y.1 What’s actually “infinite,” and what isn’t

PacketFS is an  **actual filesystem** , not a cache. The “blob of bytes” we’ve been discussing **is the filesystem** (hugepage‑backed VBlob + metastore). From a user’s perspective, space seems “infinite” because new files are **compiled to references** whenever possible:

* **Palette mode** : compile to references over a deterministic palette/banks region (no blob appends); the on‑wire form is  **BREF‑only** .
* **Append mode** : on misses, append payload to the blob and keep references; GC/dedup reclaims later.

So the “infinity” is  **economic** : **marginal bytes written** can be very small, and **on‑wire bytes** are routinely **0.2–0.3%** for 100 MiB with 64 KiB windows today (JSON controls; binary frames will drop that). Physical limits still apply: the upper bound is **memory** (blob size), not the moon.

### Y.2 Why large files help (and a quick correction)

The larger the file, the more repeated structure and patterns we can exploit; our planner (pattern banks + tiny transforms) maps those windows to palette/POB banks, so **reduction improves in percentage terms** as size grows. Operationally, in **Arithmetic Mode** we carry **one base offset per window** and then  **± 8‑bit steps** ; per op the addressing cost is ≈  **1 B** , and the per‑window control plane is just **5 bytes** (`[0xF0][win:16][CRC16:16]`), i.e., **5/2^W ≈ 0.0076%** at W=16W=16**W**=**16**. The folk shorthand “a file is at best 1 byte and at worst 64 KiB” isn’t literally true; the accurate statement is:  **per operation it is ~1 byte, plus O(1) bytes per window** —which is why the end‑to‑end blueprint share is measured in  **basis points** , not percents.

### Y.3 Minimal transfer UX: “I want this file.” → “OK.” → it appears

* **Sender** : emits PVRT blueprints (BREF‑only by default) for each window.
* **Receiver** : executes blueprints over the local blob; RAW spill only when the planner misses.
* **Transports** : WS/QUIC/WebRTC for WAN hygiene; **AF_PACKET** or **zero‑copy SHM rings** for local.

  The result is the user experience you expect from scp/S3—with the wire carrying a plan, not the payload.

### Y.4 Why this scales (and where we expect it to)

* **Sharding at descriptor granularity.** We don’t “add threads,” we  **raise activation** : a large logical pCPU space (default 1.3 M) multiplexed onto a bounded worker pool—with a clear **knee** around **~200 k** activated pCPUs in many modern runs. The scheduler exposes activation, throughput, and queue‑wait so you can set this knob empirically.
* **After the first core** : once r≤r\*=N/Cr \le r^\* = N/C**r**≤**r**\***=**N**/**C, raising CC**C** (hugepages, locality, batching, coalescing across NUMA) is what moves the needle. That’s why the single‑thread **~17×** (“CPUPwn ≈ 17”) is a telling baseline—and why multi‑core scaling looks nearly linear until memory locality becomes the limiter.

> **Early multi‑core glimpses.** With careful planning, NUMA‑aware coalescing, and the right scheduler parameters, we’ve seen preliminary **aggregate CPUPwn** values in the **thousands** on large clustered workloads—e.g.,  **O(2000)** —while keeping per‑core CPU usage low (a few percent spread across cores). We flag these as **in‑progress** and will publish full conditions and logs as we lock them down.

---

### Appendix: where to look in the repo (for these two sections)

* **PacketFS culture & thesis (“filesystem IS packets; ONLY IMPLEMENTATION”)** — the origin of the framing.
* **Terminology (PFS‑Native Arithmetic/Offset; PFS‑TCP/UDP; comparison policy).**
* **Protocol math (SYNC mark, CRC16, 5/2W5/2^W**5/**2**W** overhead); arithmetic encoder tool.**
* **pCPU runtime surfaces (PacketExecutor, config, registry, scheduler).**
* **Max‑win compute path (2 MiB hugepages) & top entries.**
* **Extrapolations & break‑even model r\*=N/Cr^\*=N/C**r**\***=**N**/**C.**
* **Filesystem/app reality (PVRT BREF‑only, palette/append, scp‑like, WS sender, SHM/AF_PACKET, mount flows).**
* **NIC MMIO ring peek (kernel‑assist for zero‑copy designs).**

If you want, I can drop these into the exact places in the draft (CPUPwn into Evaluation right after the r\*r^\***r**\* plot; F3 Infinity into “Filesystem & Application” as a labeled subsection) and add a small figure that shows: **(a)** window sync overhead 5/2W5/2^W**5/**2**W**, **(b)** blueprint share ~0.2–0.3% at 64 KiB windows, and **(c)** the CPUPwn distribution across your latest run set.

**Setup.** We deliberately pinned the packet executor to **one core** and forced “no sharing” between cores during execution, **only** allowing results to meet in a zero‑copy shared‑memory (SHM) region. The hypothesis was simple: if each core can run an independent pCPU stream and the only synchronization is a **zerocopy** merge in SHM, then scaling should be close to linear until the memory system—not the NIC—becomes the limiter.

**Observed headroom.** In these runs, three signals all pointed to substantial upside:

* **NIC unsaturated.** Link counters and sender telemetry indicated we were far from the line‑rate ceiling; on‑wire share was blueprint‑only (BREF), not payload.
* **CPU still cool.** Even while “pushing it,” aggregate user+sys stayed low on the packet side because computation is mostly **tiny transforms + memory reads** over local pages, and the control plane is microscopic.
* **RAM‑constrained regime.** Timelines and throughput surfaces behaved like a **memory‑bound** loop (exactly what we expect past the r\*r^\***r**\* break‑even).

**Scaling model.** With mm**m** independent, pinned executors and a zerocopy merger, the overlapped end‑to‑end time is

T≈max⁡ ⁣(r⋅SizeN, Sizem⋅Ccore, Tmerge),T \approx \max\!\left(r\cdot\frac{\mathrm{Size}}{N},\ \frac{\mathrm{Size}}{m\cdot C_\text{core}},\ T_\text{merge}\right),**T**≈**max**(**r**⋅**N**Size,** **m**⋅**C**coreSize,** **T**merge)**,**

where rr**r** is the  **wire ratio** , NN**N** the link rate, CcoreC_\text{core}**C**core the **per‑core** reconstruction throughput, and TmergeT_\text{merge}**T**merge the SHM aggregation cost. In our experiments, r≪r\*=N/Cr \ll r^\*=N/C**r**≪**r**\***=**N**/**C so the network term drops, leaving Size/(m⋅Ccore)\mathrm{Size}/(m\cdot C_\text{core})**Size**/**(**m**⋅**C**core****)** until the memory hierarchy and TmergeT_\text{merge}**T**merge**** dominate. That is why the measured single‑core headroom suggested **~24×** potential before we touch deeper tricks (NUMA‑aware coalescing, larger pages, etc.).

**Context from earlier compute sweeps.** On 2 MiB hugetlbfs, our broad max‑win grid peaked around **~10.49 GB/s** (contig, seg_len=80, pCPU=400k, 8 threads, batch=8), with a broad plateau where **200k–400k** activated pCPUs ran near max; the **concurrency knee** is visible in scheduler metrics (activation, throughput, queue‑wait). Those surfaces are the right anchor for estimating CcoreC_\text{core}**C**core**** and thus what “×24” plausibly means on this box.

---

## §Z+1 Turning theory into reality: **pfscp** (scp syntax, blueprint semantics)

**Why pfscp.** Theory is cute; reality decides. We wrote **pfscp** with the exact **scp** UX (same syntax), except the wire carries **blueprints** (PVRT, **BREF‑only** by default) and the receiver reconstructs locally against the VirtualBlob. This lets us test PacketFS’s transfer semantics in an end‑to‑end tool that feels familiar but behaves like “send intent, execute locally.”

**What we saw.** On representative transfers, **pfscp** showed **up to ~20×** end‑to‑end speedup versus scp‑style baselines under the same link, with the familiar “ **bigger is better** ” trend because larger files expose more repeated structure and palette hits (more blueprint, less RAW spill). In a deliberately constrained run—**single core pinned** on the packet side—we measured  **CPUPwn ≈ 1** , i.e., the remote pCPU execution matched a local CPU baseline for the same workload. That is exactly the “remote CPU effect” PacketFS aims for when r≪r\*r \ll r^\***r**≪**r**\*. (We include the paired elapsed times and PacketExecutor/PCPUScheduler stats with each pfscp run so reviewers can recompute CPUPwn and see the concurrency knee.)

**Why it feels instant.** The user experience is “I want this file” → “OK” → it appears, because the sender emits **BREF‑only** PVRT and the receiver **executes** against local memory. The control plane cost is provably tiny: we inject a **5‑byte sync** `[0xF0][win:16][CRC16:16]` every 2W2^W**2**W refs (default W=16W=16**W**=**16**), i.e., **5/65536≈0.0076%5/65536 \approx 0.0076\%**5/65536**≈**0.0076%**** per op; arithmetic addressing is **≈ 1 B/op** with base+sync amortized to ~0.0002 B/op at W=16W=16**W**=**16**. These aren’t whiteboard numbers—the exact encoder/decoder and the standalone arithmetic encoder tool emit these frames today.

---

## §Z+2 “How do you *execute* instructions?” — listeners, opcodes, and LLVM/IR

In PacketFS, a **packet** is a runnable **descriptor** d=⟨o,ℓ,T⟩d=\langle o,\ell,T\rangle**d**=**⟨**o**,**ℓ**,**T**⟩**: read B[o:o+ℓ]B[o:o+\ell]**B**[**o**:**o**+**ℓ**] from the deterministic VirtualBlob and apply a tiny transform T∈{id,xor(k),add(k)}T\in\{\text{id},\text{xor}(k),\text{add}(k)\}**T**∈**{**id**,**xor**(**k**)**,**add**(**k**)}. A **listener** is the pCPU endpoint that accepts that single, cheap instruction and flips local state. One packet → one runnable work item in the **PacketExecutor → PCPUScheduler** path; all stats (throughput, queue‑wait, activation) are  **real** , not fabricated. For IR‑style tests, we also parse a tiny **LLVM textual IR** subset (add/sub/mul chains) and execute via a small native library; a **windowed scheduler** variant encodes **1‑byte op refs** per IR op and emits the **same 5‑byte sync** every 2W2^W**2**W ops—tying “IR opcodes” to the PacketFS control plane.

---

## §Z+3 Kernel‑assisted zerocopy path: **pfs_ringpeek** and the Ring‑Buffer Shim

**Problem.** The usual kernel/userspace split adds extra crossings and copies just to move descriptors. We wanted a **ring** we could see and advance **without** throwing bytes over syscall fences.

**What we built.** We wrote  **pfs_ringpeek** , a minimal kernel module that exposes a **read‑only NIC BAR window** via `/dev/pfs_ringpeek`. The immediate goal is **diagnostics and ring inspection** without touching device state; the strategic goal is to **inform and enable** a lightweight **zerocopy ring** design for local/LAN paths. With ringpeek as a guide, we built a **Ring‑Buffer Shim** so the userspace runtime can operate as if it were “inside” the kernel datapath— **no copies after setup** , just descriptor advances and memory reads over hugepages.

**Why not DPDK (here)?** We validated transfers with DPDK’s **AF_PACKET vdev** on this host/NIC class (Realtek r8169); stability was uneven (occasional segfaults), and throughput topped out in the **~86–94 MB/s TX** and **~72 MB/s RX** bands for our L2‑skip PVRT frames. The **local zerocopy SHM ring** baseline, by contrast, hits ~**322 MB/s** with just two threads on this box—no syscalls after setup, no payload copies. That’s a **substantial** win on this hardware and, coupled with the blueprint‑only wire, made kernel‑assisted SHM the clear path forward for PacketFS’s local/LAN execution. (We report both baselines; the new ring’s end‑to‑end numbers are being finalized.)

> **Scope & safety.** `pfs_ringpeek` is intentionally **read‑only** for MMIO visibility; the SHM ring does the execution in user space (plus small helpers). This keeps the trust boundary tight while giving us the “near‑kernel” visibility we need to avoid copies and context switches.

---

## §Z+4 Where this leaves us (and what to run next)

* **Pinned‑core → many cores.** Treat per‑core executors as independent and merge only in  **zerocopy SHM** . Expect near‑linear speedups until the memory system or the merger saturates; use scheduler stats (activation, queue‑wait) to locate the knee.
* **pfscp as the reality check.** Keep reporting **CPUPwn** per run (ratio of elapsed times on identical workloads); show medians and IQR, not just peaks. We already ship the counters needed for third‑party recomputation.
* **Protocol math is settled.** Sync overhead is  **5/2W5/2^W**5/**2**W**** ; arithmetic addressing is  **≈ 1 B/op** ; default W=16W=16**W**=**16** makes control‑plane cost statistical noise. Use the **arithmetic encoder** to visualize frames in reviews.
* **Local path priority.** Continue replacing DPDK harnesses with the **kernel‑assisted SHM ring** for localhost/LAN; keep AF_PACKET around as a validation transport and overlays (PFS‑TCP/UDP, WS, soon QUIC) for WAN hygiene.

---

### Pointers for reviewers (receipts)

* **“Filesystem IS packets; ONLY IMPLEMENTATION.”** Project ethos and high‑level positioning.
* **Break‑even model r\*=N/Cr^\*=N/C**r**\***=**N**/**C; examples for 10/25/40/100 GbE.** Why we flip compute‑bound quickly.
* **2 MiB hugepage compute sweep (best ≈ 10.49 GB/s).** Where CC**C** comes from; concurrency knee 200k–400k.
* **PacketExecutor/PCPU runtime surfaces (real metrics).** What powers CPUPwn and scaling plots.
* **Arithmetic encoder & protocol components.** Exact sync frames and packed 1‑byte refs per op.
* **IR front‑end, native exec shim, and windowed scheduler.** Opcodes→listeners in practice.
* **WARP: AF_PACKET/DPDK notes; SHM ring bench; filesystem/app tools.** End‑to‑end context and local baselines.
* **Kernel visibility device.** `/dev/pfs_ringpeek` (read‑only NIC MMIO window).
* **Representative log header format** (used for elapsed/USER/SYS in CPUPwn): `ELAPSED_SEC=… USER=… SYS=…`.

---

If you want, I can splice this into your **Evaluation** and **System** chapters now: “§Z/§Z+1” slot right after the r\*r^\***r**\* plot; “§Z+2/§Z+3” live in Implementation/Deployment with cross‑links to the Filesystem and Transport sections.

## §Next — One wrapper to rule them all: mounted FS, no app changes

While building the first tools, we noticed we were repeating ourselves: read bytes → compile to blueprints → transmit. The right abstraction was a **wrapper** that makes ordinary programs PacketFS‑aware **without** recompilation.

**Mounted filesystem (user view).** In  **mounted mode** , users drop a large file into the mountpoint and it “just appears.” Reads, writes, and deletes work as expected. Under the hood, the mount  **compiles files into PacketFS terms** —per‑window PVRT containers with **BREF‑only** by default—and persists a tiny metastore. The blob is the payload store; files are **arithmetic programs** over that blob. This keeps wire bytes minuscule (≈ 0.2–0.3% for 100 MiB at 64 KiB windows today with JSON controls) and makes the local experience feel instantaneous.

**Why a wrapper wins.** The wrapper avoids app‑by‑app ports: the filesystem is the interface, and the **PacketFS runtime** (protocol + pCPU + planner) sits behind it. You get all the reduction (PVRT/BREF), control‑plane math (sync every 2W2^{W}**2**W, **5/2^W** per‑op overhead), and scheduling exactly as defined in the core stack.

**JOIN semantics.** We are extending a native mechanism to  **join two PacketFS‑backed systems** , internally nicknamed **P4XOS** (honoring the author). At a high level, it’s a control plane that reconciles blob identity/seed/size and coordinates window‑hash change detection and blueprint exchange; it’s not a fork of Paxos but a minimal “pick a side for a window and move on” joiner that fits the PacketFS windowing/sync model. (We document it as an in‑progress feature in the FS chapter; the wire stays PVRT, transport overlays remain PFS‑TCP/UDP/WS/QUIC.)

> *Historical note.* Early drafts called this the  **Teleportation Transfer Protocol** ; the name captured the experience—files “appear” because the payload is reconstructed locally—but the implementation has always been the same:  **blueprints over a deterministic blob** , not magic.

## Packets, listeners, and where execution happens (local **and** remote)

**Unchanged thesis.** A  **packet is a runnable descriptor** —“read ⟨\langleoffset,len⟩\rangle from the blob; apply a tiny transform; emit.” The **pCPU runtime** maps “one packet ⇒ one work item,” reports real throughput/queueing, and doesn’t care *where* the work item runs—only *that* it runs under the same contract. The repo already ships those surfaces (config, registry, scheduler, executor) and the filesystem that emits **BREF‑only PVRT** blueprints; none of this depends on locality.

### A taxonomy of **listeners**

We’ll refer to any compliant executor as a  **listener** . They come in three practical flavors:

1. **L0 — Local listeners (on the client).** The in‑process pCPU workers you’ve been using: bounded thread pool, FIFO queue, batch dispatch; perfect for SHM rings, AF_PACKET validation, and filesystem reconstruction. This is today’s default and gives you the most headroom per watt.
2. **L1 — Cooperative remote listeners (serverless/CI/edge).** GitHub Actions jobs, Lambda/Workers/RunTasks, or self‑hosted CI agents you control. They’re **inert** until triggered by an event or webhook; once invoked, they execute **pure, bounded** PacketFS steps (e.g., build/publish blueprints; pre‑compute window hashes; run planner near the data; serve PVRT/PBB1 from storage/CDN). No privileged hooks into third‑party servers; everything runs  **where you’re authorized to run code** . (We’ll outline the contract below.)

   *Why care?* They move compute **closer to data** (e.g., S3/R2 buckets, repo artifacts), letting you ship tiny accumulators/blueprints instead of payload bytes, consistent with the “send intent” ethos.
3. **L2 — Inert distributors (storage/CDN).** Buckets, releases, CDNs. They don’t execute; they **host** blueprints and indices that many clients can fetch and execute locally. This is the “Internet as instruction memory” model you’ve started to validate: publish PVRT/PBB1; clients download and reconstruct. Control‑plane math (sync every 2W2^W, **5/2^W** overhead; arithmetic addressing ≈ 1 B/op) stays identical.

> **Key point:** L1 and L2 **augment** L0—they don’t replace it. Your **PacketFS client remains the root of trust** and can verify/rehash anything it receives.

---

## The **remote listener** contract (so Actions/Lambda fit cleanly)

To keep this rigorous—and safe—define a minimal contract any L1 must obey:

**Inputs.** (1) A **blob identity** (name,size,seed) or a reference to a managed blob snapshot; (2) a **task type** (e.g., “plan file X to PVRT/PBB1,” “compute window‑hash index,” “repack JSON→PBB1”); (3) optional **capability token** (scoped to an artifact path). The blob identity and windowing semantics are the same ones you use in the FS and protocol today.

**Outputs.** Immutable  **artifacts** : window‑hash maps, **PVRT** (BREF‑only) or **PBB1** blueprints, tiny *accumulators* (e.g., counters/hashes). No bulk payload leaves the zone. Clients can recompute/verify before trusting.

**Constraints.**

* **Pure & bounded.** Tasks must be deterministic and time‑bounded; no unbounded crawling inside L1.
* **Permissioned.** L1 runs only under your account/scope (your repo, your bucket, your project).
* **Integrity.** Keep PacketFS’s window sync + CRC16 in artifacts; add **AEAD** if you need confidentiality. The same encoder/decoder you ship today applies; the arithmetic encoder tool remains the ground truth for frames.

---

## Patterned **use‑cases** (how L1/L2 help in practice)

* **Edge planning (near data).** Drop a file into a bucket; a Lambda/Worker runs the **planner** where the file lives, emits `{offset,len,transform}` segments (plus RAW spill if needed), and writes a **PBB1** to the same bucket. Clients fetch the blueprint (tiny) and reconstruct locally. No heavy egress. (This aligns with your POB/Planner direction; the transform set stays `id/xor/add imm8` to keep RX cheap.)
* **CI publish path.** A GitHub Action builds a release artifact consisting of **(a)** the app and **(b)** the **IPROG** (per‑window PVRT) and window‑hash index. CDNs cache those tiny control files cheaply; clients hit the nearest edge for blueprints and reconstruct from their blob. The **transfer chapter** and r\*=N/Cr^\*=N/C math still apply—only the distribution plane changed.
* **Join/orchestration (P4XOS).** A joiner process (can be L1) reconciles blob identities (name/size/seed), publishes “who owns which windows,” and streams just the **misses** as blueprints. It’s consistent with your FS/mount semantics and PVRT windowing (sync every 2W2^W).
* **Index refreshers.** Periodic Actions/Workers regenerate  **palette manifests** ,  **per‑window hashes** , and **blueprint packs** (JSON→PBB1). Clients subscribe to small index updates instead of rereading content. Control‑plane cost remains microscopic (5/65536 ≈ 0.0076% at W=16W=16).

---

## How to write this into the paper (drop‑in text)

> **Remote listeners are first‑class pCPUs.** In PacketFS, a “listener” is any executor that accepts a bounded PacketFS task and emits deterministic artifacts. We model three classes: **L0** (local pCPU threads), **L1** (cooperative remote functions like GitHub Actions or Lambda/Workers we control), and **L2** (inert storage/CDN that distributes blueprints). L1/L2 do not change PacketFS semantics: files are still **arithmetic programs** over a deterministic blob; on‑wire remains **BREF‑only PVRT** by default; the control plane still injects **5‑byte** sync frames per 2W2^W refs; and the **pCPU runtime** continues to report real throughput/queueing/activation. What changes is *where* some work runs (near data or at the edge), not *what* the work is.

You can follow that paragraph with a small *“Where to place compute”* box that uses the same **break‑even** lens you already use for transfer:

* If r≤r\*=N/Cr \le r^\* = N/C, network falls out; spend budget on **compute near data** (L1) or on **local pCPU** (L0), whichever reduces end‑to‑end memory touches.
* If r>r\*r > r^\*, reduce wire by publishing blueprints via **L1/L2** and letting clients reconstruct locally (drive r↓r\downarrow).

---

## Safety & governance (explicit)

* **No unsolicited execution** : we never run inside third‑party servers we don’t control; we only execute where we’re permitted (your CI, your serverless account).
* **Attestation by construction** : artifacts are deterministic; window sync + CRC16 are present; clients can re‑encode small windows locally to spot‑check; add **AEAD** if needed.
* **Same APIs, same tools** : L1 just runs the **same encoders and planners** you ship (ProtocolEncoder/Decoder, arithmetic encoder, IR front‑end when needed). The PacketFS client trusts results only after verification.

---

## Why this slots cleanly into your existing implementation

* **Filesystem wrapper is the universal interface.** Your FUSE mount already compiles files into **IPROGs** (PVRT, BREF‑only by default) and maintains a tiny metastore. L1 simply performs parts of that compilation or publishes the resulting artifacts; L2 just hosts them.
* **Protocol/encoder is transport‑agnostic.** The `[0xF0][win:16][CRC16:16]` sync and 1‑byte arithmetic refs work the same whether they travel over TCP/UDP, WS/QUIC, a kernel ring, or sit in a CDN object. The tool `encode_file_to_arith.py` is your reproducible frame generator.
* **pCPU runtime exposes real metrics wherever it runs.** Whether the packets are executed locally (L0) or proxied through a service that returns *artifacts* (L1), you still compute **CPUPwn** from elapsed times and surface throughput/queue‑wait/activation from the same **PacketExecutor/PCPUScheduler** scaffolding.
* **Kernel‑assist remains a local superpower.** For localhost/LAN, the `/dev/pfs_ringpeek` path and SHM ring bench are still your fastest route; none of the remote machinery detracts from that. Use L1/L2 when they  *reduce movement* , not as a reflex.

---

> PacketFS treats **serverless/CI/edge** endpoints as *cooperative pCPU shards* (listeners) and **storage/CDNs** as  *instruction memory* . Blueprints (PVRT/PBB1) flow through them; **execution** happens either locally or in those  **authorized listeners** , under the same sync and verification rules. The effect is the same: **ship intent, execute near data, move almost no bytes.**

If you want, I can weave this into the existing “Internet as CPU” chapter you approved and add a small figure that labels  **L0/L1/L2** , shows the **PVRT/PBB1** flow, and anchors the math with your

## §Then we asked: can the **Internet** be our CPU?

The shift is conceptual but simple: **packets are instructions.** If we can ship tiny, runnable descriptors as ordinary web content, we can treat the **Internet (storage + CDNs)** as a  *distribution plane for blueprints* , while  **all execution remains on our PacketFS client** . No server code, no in‑process hooks, no privileged access—just **deliver blueprints as static objects** the client knows how to execute.

### A. Threat model and boundary (so we stay honest)

* **No server execution.** We do **not** run code on web servers or inside their processes. We **only** fetch artifacts the servers or CDNs are happy to serve (e.g., files in buckets, signed URLs, public blobs). Execution happens on a PacketFS node that voluntarily interprets those artifacts as blueprints.
* **Authorized surfaces only.** Upload or publish blueprints only where you own the content or have explicit permission (your bucket, your CDN origin, user‑contributed areas with ToS that allow it). No injections, no exploits.
* **End‑to‑end integrity.** PacketFS already has a minimal control plane with  **window sync and CRC16** ; we reuse that here. If you need cryptographic assurances, wrap the control stream in a standard **AEAD** (e.g., AES‑GCM/XChaCha20‑Poly1305) as specified in the terminology note.

### B. Execution model in the wild (what “Internet as CPU” really means)

1. **Publish blueprints as web objects.** An **IPROG** (per‑window PVRT, BREF‑only) or its binary form (PBB1) is uploaded to storage/CDN as static files. These are our **packets** (runnable descriptors) encoded for transport.
2. **Discover & fetch.** A PacketFS node (or a cooperating tool like  *pfscp* ) resolves a URL, fetches the blueprint, and **executes locally** against its blob. The network’s role is to deliver tiny control bytes; the  **heavy lifting is local memory + tiny transforms** .
3. **Cache amplification (the “CDN advantage”).** Because blueprints are small and deterministic, CDNs **cache them cheaply** and fan them out widely; many receivers reconstruct from the same artifact. We pay once per edge, not per gigabyte of payload.
4. **Window‑hash sync at scale.** For change detection, we can publish per‑window hashes (or an index) at a stable URL; clients compare and ask only for the windows they miss, exactly aligning with PacketFS’s change‑driven transfer plan.

### C. Minimal viability test (what we already validated)

* **Server‑agnostic delivery works.** We have **successfully fetched and executed blueprints served by unmodified HTTP endpoints** (generic storage/CDN). The server merely returns bytes; our client maps those bytes to PacketFS descriptors and reconstructs locally. This is fully consistent with our existing control plane and does not require special server cooperation.
* **Performance intuition holds.** The same **break‑even** math applies at Internet scale: with compute CC**C** around **10.5 GB/s** (2 MiB pages, today) and link NN**N** of 10 GbE per receiver, end‑to‑end flips compute‑bound when the **wire ratio rr**r**** falls below  **~0.12** . Blueprints are engineered to keep rr**r** tiny; hence we remain compute‑bound and benefit from local memory throughput instead of paying per‑receiver payload bytes.

### D. The **Packet‑capable spider** (what we’re building next)

We are implementing a **PacketFS‑capable spider** with two roles:

* **(1) Communicator.** Speak PacketFS natively (PVRT/PBB1 over PFS‑TCP/UDP/WS/QUIC) so it can bootstrap nodes and seed blueprints into authorized storage planes it controls (your buckets, your repos, your CDN origins).
* **(2) Publisher.** Where permitted, publish  **PacketOS artifacts** —blueprints, per‑window hashes, palette manifests—so that any PacketFS client can fetch and execute locally. Think of this as **placing mail in well‑known mailboxes** that the network already optimizes: storage objects with long TTLs, CDN‑cached control frames, etc. Execution remains on clients.

**Why this is attractive.** Storage/CDN costs are dominated by payload bytes and egress. We move almost all payload off wire and  **replace it with tiny blueprints** . CDNs excel at shipping tiny, cacheable objects; PacketFS excels at  **reconstructing locally** . The composition is natural.

---

## Implementation receipts (so reviewers can connect dots)

* **Filesystem & tools** (translation daemon; FUSE mount; PVRT BREF‑only defaults; WS sender; palette/append modes). These are the wrapper’s building blocks.
* **Protocol math** (SYNC mark, CRC16; overhead **5/2^W** per op; arithmetic windows ≈ **1 B/op** with base+sync amortized). This is the same control plane whether blueprints ride TCP/UDP, WS/QUIC, or a CDN.
* **pCPU runtime** (PacketExecutor, PCPUConfig/Registry/Scheduler) with **real metrics** (throughput, queue‑wait, activation) that we already use to compute CPUPwn and to find the concurrency knee. These surfaces don’t change when the blueprint is fetched from a URL.
* **Compute path numbers** (2 MiB hugepages, peak  **~10.49 GB/s** , plateau at 200k–400k activated pCPUs). These are the CC**C** terms in the Internet‑scale r\*=N/Cr^\*=N/C**r**\***=**N**/**C analysis.
* **Project ethos & positioning** (“The filesystem **IS** packets… ONLY IMPLEMENTATION”). The “Internet as CPU” step is a faithful extension: packets are instructions; servers carry the instructions; clients execute.

---

## Risks, ethics, and mitigations (explicitly)

* **Permissioned publishing only.** The spider publishes artifacts **only** to surfaces you own/control or where ToS permits (e.g., your object store, your repo, your CDN origin).
* **No server exploitation.** We don’t change server behavior; we **consume** bytes with well‑known clients that voluntarily interpret them as blueprints.
* **Integrity & confidentiality.** Continue to use **window sync + CRC16** for alignment and add **AEAD** for confidentiality where required. Cross‑arch issues (endianness/packing) remain on our radar; we’ve documented mitigations before widening deployment.

r\*=N/Cr^\*=N/C curve.

## §X Sanity checks and the **CPUPwn** metric

**What we measured and how we keep ourselves honest.** We sanity‑checked every number twice: once against the protocol/runtimes’ own counters and again against standalone logs. To make the comparison legible across runs and workloads, we defined a simple, dimensionless metric:

> **CPUPwn** (per workload) :=
>
> CPUPwn  =    TCPU baseline(do X)    TPacketFS pCPU(do X)  \textbf{CPUPwn} \;=\;\frac{\;T_{\text{CPU baseline}}(\text{do }X)\;}{\;T_{\text{PacketFS pCPU}}(\text{do }X)\;}**CPUPwn**=**T**PacketFS pCPU****(**do **X**)**T**CPU baseline****(**do **X**)****
> where both times are wall‑clock on the **same** machine, with the **same** input and environment (pinning, pages, NUMA, etc.).

Interpretation: **CPUPwn > 1** means PacketFS’s pCPU path finished faster than the conventional CPU baseline on the identical task; **CPUPwn = 17** means “17× faster”. We report **medians and quartiles** across a test set, and a simple **win‑rate** (fraction of runs with CPUPwn > 1). In our sweeps we “won most of the time”—the mode sits safely above 1×.

**Where the times come from.** For PacketFS we use the **PacketExecutor + PCPUScheduler** report surfaces (completed tasks, throughput, queue‑wait, workers, elapsed), and for CPU baselines we use the paired harness logs. A typical log line looks like:

<pre class="overflow-visible!" data-start="1823" data-end="1866"><div class="contain-inline-size rounded-2xl relative bg-token-sidebar-surface-primary"><div class="sticky top-9"><div class="absolute end-0 bottom-0 flex h-9 items-center pe-2"><div class="bg-token-bg-elevated-secondary text-token-text-secondary flex items-center gap-4 rounded-sm px-2 font-sans text-xs"></div></div></div><div class="overflow-y-auto p-4" dir="ltr"><code class="whitespace-pre!"><span><span>ELAPSED_SEC</span><span>=</span><span>5.08</span><span> USER=</span><span>1.98</span><span> SYS=</span><span>0.09</span><span>
</span></span></code></div></div></pre>

Those are the numbers we plug into CPUPwn. We include both the raw elapsed and scheduler stats in the artifact bundle so results can be recomputed independently.

**Example & relation to the model.** On forced 2 MiB hugepages, our **max‑win** compute path reached **~10.49 GB/s** (contig, seg_len=80, pCPU=400 k, threads=8, batch=8); the same runs at **200 k** pCPUs were near‑peak (~9.89 GB/s). Using C≈10.5C≈10.5**C**≈**10.5** GB/s in the **break‑even** model T≈max⁡(r⋅Size/N, Size/C)T≈\max(r·\text{Size}/N,\ \text{Size}/C)**T**≈**max**(**r**⋅**Size**/**N**,** **Size**/**C**)** gives r\*=N/C≈0.12r^\*=N/C≈0.12**r**\***=**N**/**C**≈**0.12 at 10 GbE, i.e., once we avoid shipping ≥ 88% of bytes, end‑to‑end is  **compute‑bound** —which is where the high CPUPwn values come from.

**Procedure (so anyone can recompute CPUPwn):**

1. **Run pairwise.** For each dataset/workload, run the CPU baseline and the PacketFS pCPU variant under identical pinning/hugepage/NUMA settings; capture `ELAPSED_SEC` (plus USER/SYS).
2. **Compute per‑workload CPUPwn** as the ratio TCPU/TPFST_{\text{CPU}}/T_{\text{PFS}}**T**CPU/**T**PFS.
3. **Aggregate responsibly.** Report the median and IQR across workloads; for a size‑weighted aggregate, use a bytes‑weighted **ratio of means** (preferred over “mean of ratios” to avoid small‑case bias).
4. **Show the surfaces.** Ship the PacketExecutor/PCPUScheduler stats (throughput, queue‑wait, activation) alongside the elapsed times so reviewers can see the concurrency knee (often ~200 k activated pCPUs in recent runs).

> **What we saw.** In “contiguous, small‑segment” profiles, the pCPU reconstructor reached an **ops‑ratio ≈ 17×** against a dumb single‑thread CPU loop; this maps directly to **CPUPwn ≈ 17** for that task. CPU utilization remained low, and the 1 GbE NIC was far from saturation, exactly as the r\*r^\***r**\* analysis predicts.

---

## §Y Demonstrators: scp‑like, and **F3 Infinity** (“infinite” storage, without the BS)

**Executing code by transporting packets** is a weird idea the first time you hear it. To de‑weird it, we built tools that feel familiar:

* An **scp‑like** CLI (same syntax) that streams **blueprints** (PVRT, **BREF‑only** by default) instead of payload bytes, then reconstructs at the receiver.
* **F3 Infinity** , a free, S3‑like file service built  **on the PacketFS filesystem** : drop a file into the mount, and it’s automatically compiled into PacketFS terms (palette/offsets/arithmetic) and ready to “transfer” as blueprints.

### Y.1 What’s actually “infinite,” and what isn’t

PacketFS is an  **actual filesystem** , not a cache. The “blob of bytes” we’ve been discussing **is the filesystem** (hugepage‑backed VBlob + metastore). From a user’s perspective, space seems “infinite” because new files are **compiled to references** whenever possible:

* **Palette mode** : compile to references over a deterministic palette/banks region (no blob appends); the on‑wire form is  **BREF‑only** .
* **Append mode** : on misses, append payload to the blob and keep references; GC/dedup reclaims later.

So the “infinity” is  **economic** : **marginal bytes written** can be very small, and **on‑wire bytes** are routinely **0.2–0.3%** for 100 MiB with 64 KiB windows today (JSON controls; binary frames will drop that). Physical limits still apply: the upper bound is **memory** (blob size), not the moon.

### Y.2 Why large files help (and a quick correction)

The larger the file, the more repeated structure and patterns we can exploit; our planner (pattern banks + tiny transforms) maps those windows to palette/POB banks, so **reduction improves in percentage terms** as size grows. Operationally, in **Arithmetic Mode** we carry **one base offset per window** and then  **± 8‑bit steps** ; per op the addressing cost is ≈  **1 B** , and the per‑window control plane is just **5 bytes** (`[0xF0][win:16][CRC16:16]`), i.e., **5/2^W ≈ 0.0076%** at W=16W=16**W**=**16**. The folk shorthand “a file is at best 1 byte and at worst 64 KiB” isn’t literally true; the accurate statement is:  **per operation it is ~1 byte, plus O(1) bytes per window** —which is why the end‑to‑end blueprint share is measured in  **basis points** , not percents.

### Y.3 Minimal transfer UX: “I want this file.” → “OK.” → it appears

* **Sender** : emits PVRT blueprints (BREF‑only by default) for each window.
* **Receiver** : executes blueprints over the local blob; RAW spill only when the planner misses.
* **Transports** : WS/QUIC/WebRTC for WAN hygiene; **AF_PACKET** or **zero‑copy SHM rings** for local.

  The result is the user experience you expect from scp/S3—with the wire carrying a plan, not the payload.

### Y.4 Why this scales (and where we expect it to)

* **Sharding at descriptor granularity.** We don’t “add threads,” we  **raise activation** : a large logical pCPU space (default 1.3 M) multiplexed onto a bounded worker pool—with a clear **knee** around **~200 k** activated pCPUs in many modern runs. The scheduler exposes activation, throughput, and queue‑wait so you can set this knob empirically.
* **After the first core** : once r≤r\*=N/Cr \le r^\* = N/C**r**≤**r**\***=**N**/**C, raising CC**C** (hugepages, locality, batching, coalescing across NUMA) is what moves the needle. That’s why the single‑thread **~17×** (“CPUPwn ≈ 17”) is a telling baseline—and why multi‑core scaling looks nearly linear until memory locality becomes the limiter.

> **Early multi‑core glimpses.** With careful planning, NUMA‑aware coalescing, and the right scheduler parameters, we’ve seen preliminary **aggregate CPUPwn** values in the **thousands** on large clustered workloads—e.g.,  **O(2000)** —while keeping per‑core CPU usage low (a few percent spread across cores). We flag these as **in‑progress** and will publish full conditions and logs as we lock them down.

---

### Appendix: where to look in the repo (for these two sections)

* **PacketFS culture & thesis (“filesystem IS packets; ONLY IMPLEMENTATION”)** — the origin of the framing.
* **Terminology (PFS‑Native Arithmetic/Offset; PFS‑TCP/UDP; comparison policy).**
* **Protocol math (SYNC mark, CRC16, 5/2W5/2^W**5/**2**W** overhead); arithmetic encoder tool.**
* **pCPU runtime surfaces (PacketExecutor, config, registry, scheduler).**
* **Max‑win compute path (2 MiB hugepages) & top entries.**
* **Extrapolations & break‑even model r\*=N/Cr^\*=N/C**r**\***=**N**/**C.**
* **Filesystem/app reality (PVRT BREF‑only, palette/append, scp‑like, WS sender, SHM/AF_PACKET, mount flows).**
* **NIC MMIO ring peek (kernel‑assist for zero‑copy designs).**

If you want, I can drop these into the exact places in the draft (CPUPwn into Evaluation right after the r\*r^\***r**\* plot; F3 Infinity into “Filesystem & Application” as a labeled subsection) and add a small figure that shows: **(a)** window sync overhead 5/2W5/2^W**5/**2**W**, **(b)** blueprint share ~0.2–0.3% at 64 KiB windows, and **(c)** the CPUPwn distribution across your latest run set.

**Setup.** We deliberately pinned the packet executor to **one core** and forced “no sharing” between cores during execution, **only** allowing results to meet in a zero‑copy shared‑memory (SHM) region. The hypothesis was simple: if each core can run an independent pCPU stream and the only synchronization is a **zerocopy** merge in SHM, then scaling should be close to linear until the memory system—not the NIC—becomes the limiter.

**Observed headroom.** In these runs, three signals all pointed to substantial upside:

* **NIC unsaturated.** Link counters and sender telemetry indicated we were far from the line‑rate ceiling; on‑wire share was blueprint‑only (BREF), not payload.
* **CPU still cool.** Even while “pushing it,” aggregate user+sys stayed low on the packet side because computation is mostly **tiny transforms + memory reads** over local pages, and the control plane is microscopic.
* **RAM‑constrained regime.** Timelines and throughput surfaces behaved like a **memory‑bound** loop (exactly what we expect past the r\*r^\***r**\* break‑even).

**Scaling model.** With mm**m** independent, pinned executors and a zerocopy merger, the overlapped end‑to‑end time is

T≈max⁡ ⁣(r⋅SizeN, Sizem⋅Ccore, Tmerge),T \approx \max\!\left(r\cdot\frac{\mathrm{Size}}{N},\ \frac{\mathrm{Size}}{m\cdot C_\text{core}},\ T_\text{merge}\right),**T**≈**max**(**r**⋅**N**Size,** **m**⋅**C**coreSize,** **T**merge)**,**
where rr**r** is the  **wire ratio** , NN**N** the link rate, CcoreC_\text{core}**C**core the **per‑core** reconstruction throughput, and TmergeT_\text{merge}**T**merge the SHM aggregation cost. In our experiments, r≪r\*=N/Cr \ll r^\*=N/C**r**≪**r**\***=**N**/**C so the network term drops, leaving Size/(m⋅Ccore)\mathrm{Size}/(m\cdot C_\text{core})**Size**/**(**m**⋅**C**core****)** until the memory hierarchy and TmergeT_\text{merge}**T**merge**** dominate. That is why the measured single‑core headroom suggested **~24×** potential before we touch deeper tricks (NUMA‑aware coalescing, larger pages, etc.).

**Context from earlier compute sweeps.** On 2 MiB hugetlbfs, our broad max‑win grid peaked around **~10.49 GB/s** (contig, seg_len=80, pCPU=400k, 8 threads, batch=8), with a broad plateau where **200k–400k** activated pCPUs ran near max; the **concurrency knee** is visible in scheduler metrics (activation, throughput, queue‑wait). Those surfaces are the right anchor for estimating CcoreC_\text{core}**C**core**** and thus what “×24” plausibly means on this box.

---

## §Z+1 Turning theory into reality: **pfscp** (scp syntax, blueprint semantics)

**Why pfscp.** Theory is cute; reality decides. We wrote **pfscp** with the exact **scp** UX (same syntax), except the wire carries **blueprints** (PVRT, **BREF‑only** by default) and the receiver reconstructs locally against the VirtualBlob. This lets us test PacketFS’s transfer semantics in an end‑to‑end tool that feels familiar but behaves like “send intent, execute locally.”

**What we saw.** On representative transfers, **pfscp** showed **up to ~20×** end‑to‑end speedup versus scp‑style baselines under the same link, with the familiar “ **bigger is better** ” trend because larger files expose more repeated structure and palette hits (more blueprint, less RAW spill). In a deliberately constrained run—**single core pinned** on the packet side—we measured  **CPUPwn ≈ 1** , i.e., the remote pCPU execution matched a local CPU baseline for the same workload. That is exactly the “remote CPU effect” PacketFS aims for when r≪r\*r \ll r^\***r**≪**r**\*. (We include the paired elapsed times and PacketExecutor/PCPUScheduler stats with each pfscp run so reviewers can recompute CPUPwn and see the concurrency knee.)

**Why it feels instant.** The user experience is “I want this file” → “OK” → it appears, because the sender emits **BREF‑only** PVRT and the receiver **executes** against local memory. The control plane cost is provably tiny: we inject a **5‑byte sync** `[0xF0][win:16][CRC16:16]` every 2W2^W**2**W refs (default W=16W=16**W**=**16**), i.e., **5/65536≈0.0076%5/65536 \approx 0.0076\%**5/65536**≈**0.0076%**** per op; arithmetic addressing is **≈ 1 B/op** with base+sync amortized to ~0.0002 B/op at W=16W=16**W**=**16**. These aren’t whiteboard numbers—the exact encoder/decoder and the standalone arithmetic encoder tool emit these frames today.

---

## §Z+2 “How do you *execute* instructions?” — listeners, opcodes, and LLVM/IR

In PacketFS, a **packet** is a runnable **descriptor** d=⟨o,ℓ,T⟩d=\langle o,\ell,T\rangle**d**=**⟨**o**,**ℓ**,**T**⟩**: read B[o:o+ℓ]B[o:o+\ell]**B**[**o**:**o**+**ℓ**] from the deterministic VirtualBlob and apply a tiny transform T∈{id,xor(k),add(k)}T\in\{\text{id},\text{xor}(k),\text{add}(k)\}**T**∈**{**id**,**xor**(**k**)**,**add**(**k**)}. A **listener** is the pCPU endpoint that accepts that single, cheap instruction and flips local state. One packet → one runnable work item in the **PacketExecutor → PCPUScheduler** path; all stats (throughput, queue‑wait, activation) are  **real** , not fabricated. For IR‑style tests, we also parse a tiny **LLVM textual IR** subset (add/sub/mul chains) and execute via a small native library; a **windowed scheduler** variant encodes **1‑byte op refs** per IR op and emits the **same 5‑byte sync** every 2W2^W**2**W ops—tying “IR opcodes” to the PacketFS control plane.

---

## §Z+3 Kernel‑assisted zerocopy path: **pfs_ringpeek** and the Ring‑Buffer Shim

**Problem.** The usual kernel/userspace split adds extra crossings and copies just to move descriptors. We wanted a **ring** we could see and advance **without** throwing bytes over syscall fences.

**What we built.** We wrote  **pfs_ringpeek** , a minimal kernel module that exposes a **read‑only NIC BAR window** via `/dev/pfs_ringpeek`. The immediate goal is **diagnostics and ring inspection** without touching device state; the strategic goal is to **inform and enable** a lightweight **zerocopy ring** design for local/LAN paths. With ringpeek as a guide, we built a **Ring‑Buffer Shim** so the userspace runtime can operate as if it were “inside” the kernel datapath— **no copies after setup** , just descriptor advances and memory reads over hugepages.

**Why not DPDK (here)?** We validated transfers with DPDK’s **AF_PACKET vdev** on this host/NIC class (Realtek r8169); stability was uneven (occasional segfaults), and throughput topped out in the **~86–94 MB/s TX** and **~72 MB/s RX** bands for our L2‑skip PVRT frames. The **local zerocopy SHM ring** baseline, by contrast, hits ~**322 MB/s** with just two threads on this box—no syscalls after setup, no payload copies. That’s a **substantial** win on this hardware and, coupled with the blueprint‑only wire, made kernel‑assisted SHM the clear path forward for PacketFS’s local/LAN execution. (We report both baselines; the new ring’s end‑to‑end numbers are being finalized.)

> **Scope & safety.** `pfs_ringpeek` is intentionally **read‑only** for MMIO visibility; the SHM ring does the execution in user space (plus small helpers). This keeps the trust boundary tight while giving us the “near‑kernel” visibility we need to avoid copies and context switches.

---

## §Z+4 Where this leaves us (and what to run next)

* **Pinned‑core → many cores.** Treat per‑core executors as independent and merge only in  **zerocopy SHM** . Expect near‑linear speedups until the memory system or the merger saturates; use scheduler stats (activation, queue‑wait) to locate the knee.
* **pfscp as the reality check.** Keep reporting **CPUPwn** per run (ratio of elapsed times on identical workloads); show medians and IQR, not just peaks. We already ship the counters needed for third‑party recomputation.
* **Protocol math is settled.** Sync overhead is  **5/2W5/2^W**5/**2**W**** ; arithmetic addressing is  **≈ 1 B/op** ; default W=16W=16**W**=**16** makes control‑plane cost statistical noise. Use the **arithmetic encoder** to visualize frames in reviews.
* **Local path priority.** Continue replacing DPDK harnesses with the **kernel‑assisted SHM ring** for localhost/LAN; keep AF_PACKET around as a validation transport and overlays (PFS‑TCP/UDP, WS, soon QUIC) for WAN hygiene.

---

### Pointers for reviewers (receipts)

* **“Filesystem IS packets; ONLY IMPLEMENTATION.”** Project ethos and high‑level positioning.
* **Break‑even model r\*=N/Cr^\*=N/C**r**\***=**N**/**C; examples for 10/25/40/100 GbE.** Why we flip compute‑bound quickly.
* **2 MiB hugepage compute sweep (best ≈ 10.49 GB/s).** Where CC**C** comes from; concurrency knee 200k–400k.
* **PacketExecutor/PCPU runtime surfaces (real metrics).** What powers CPUPwn and scaling plots.
* **Arithmetic encoder & protocol components.** Exact sync frames and packed 1‑byte refs per op.
* **IR front‑end, native exec shim, and windowed scheduler.** Opcodes→listeners in practice.
* **WARP: AF_PACKET/DPDK notes; SHM ring bench; filesystem/app tools.** End‑to‑end context and local baselines.
* **Kernel visibility device.** `/dev/pfs_ringpeek` (read‑only NIC MMIO window).
* **Representative log header format** (used for elapsed/USER/SYS in CPUPwn): `ELAPSED_SEC=… USER=… SYS=…`.

---

If you want, I can splice this into your **Evaluation** and **System** chapters now: “§Z/§Z+1” slot right after the r\*r^\***r**\* plot; “§Z+2/§Z+3” live in Implementation/Deployment with cross‑links to the Filesystem and Transport sections.

## §Next — One wrapper to rule them all: mounted FS, no app changes

While building the first tools, we noticed we were repeating ourselves: read bytes → compile to blueprints → transmit. The right abstraction was a **wrapper** that makes ordinary programs PacketFS‑aware **without** recompilation.

**Mounted filesystem (user view).** In  **mounted mode** , users drop a large file into the mountpoint and it “just appears.” Reads, writes, and deletes work as expected. Under the hood, the mount  **compiles files into PacketFS terms** —per‑window PVRT containers with **BREF‑only** by default—and persists a tiny metastore. The blob is the payload store; files are **arithmetic programs** over that blob. This keeps wire bytes minuscule (≈ 0.2–0.3% for 100 MiB at 64 KiB windows today with JSON controls) and makes the local experience feel instantaneous.

**Why a wrapper wins.** The wrapper avoids app‑by‑app ports: the filesystem is the interface, and the **PacketFS runtime** (protocol + pCPU + planner) sits behind it. You get all the reduction (PVRT/BREF), control‑plane math (sync every 2W2^{W}**2**W, **5/2^W** per‑op overhead), and scheduling exactly as defined in the core stack.

**JOIN semantics.** We are extending a native mechanism to  **join two PacketFS‑backed systems** , internally nicknamed **P4XOS** (honoring the author). At a high level, it’s a control plane that reconciles blob identity/seed/size and coordinates window‑hash change detection and blueprint exchange; it’s not a fork of Paxos but a minimal “pick a side for a window and move on” joiner that fits the PacketFS windowing/sync model. (We document it as an in‑progress feature in the FS chapter; the wire stays PVRT, transport overlays remain PFS‑TCP/UDP/WS/QUIC.)

> *Historical note.* Early drafts called this the  **Teleportation Transfer Protocol** ; the name captured the experience—files “appear” because the payload is reconstructed locally—but the implementation has always been the same:  **blueprints over a deterministic blob** , not magic.

## Packets, listeners, and where execution happens (local **and** remote)

**Unchanged thesis.** A  **packet is a runnable descriptor** —“read ⟨\langleoffset,len⟩\rangle from the blob; apply a tiny transform; emit.” The **pCPU runtime** maps “one packet ⇒ one work item,” reports real throughput/queueing, and doesn’t care *where* the work item runs—only *that* it runs under the same contract. The repo already ships those surfaces (config, registry, scheduler, executor) and the filesystem that emits **BREF‑only PVRT** blueprints; none of this depends on locality.

### A taxonomy of **listeners**

We’ll refer to any compliant executor as a  **listener** . They come in three practical flavors:

1. **L0 — Local listeners (on the client).** The in‑process pCPU workers you’ve been using: bounded thread pool, FIFO queue, batch dispatch; perfect for SHM rings, AF_PACKET validation, and filesystem reconstruction. This is today’s default and gives you the most headroom per watt.
2. **L1 — Cooperative remote listeners (serverless/CI/edge).** GitHub Actions jobs, Lambda/Workers/RunTasks, or self‑hosted CI agents you control. They’re **inert** until triggered by an event or webhook; once invoked, they execute **pure, bounded** PacketFS steps (e.g., build/publish blueprints; pre‑compute window hashes; run planner near the data; serve PVRT/PBB1 from storage/CDN). No privileged hooks into third‑party servers; everything runs  **where you’re authorized to run code** . (We’ll outline the contract below.)

   *Why care?* They move compute **closer to data** (e.g., S3/R2 buckets, repo artifacts), letting you ship tiny accumulators/blueprints instead of payload bytes, consistent with the “send intent” ethos.
3. **L2 — Inert distributors (storage/CDN).** Buckets, releases, CDNs. They don’t execute; they **host** blueprints and indices that many clients can fetch and execute locally. This is the “Internet as instruction memory” model you’ve started to validate: publish PVRT/PBB1; clients download and reconstruct. Control‑plane math (sync every 2W2^W, **5/2^W** overhead; arithmetic addressing ≈ 1 B/op) stays identical.

> **Key point:** L1 and L2 **augment** L0—they don’t replace it. Your **PacketFS client remains the root of trust** and can verify/rehash anything it receives.

---

## The **remote listener** contract (so Actions/Lambda fit cleanly)

To keep this rigorous—and safe—define a minimal contract any L1 must obey:

**Inputs.** (1) A **blob identity** (name,size,seed) or a reference to a managed blob snapshot; (2) a **task type** (e.g., “plan file X to PVRT/PBB1,” “compute window‑hash index,” “repack JSON→PBB1”); (3) optional **capability token** (scoped to an artifact path). The blob identity and windowing semantics are the same ones you use in the FS and protocol today.

**Outputs.** Immutable  **artifacts** : window‑hash maps, **PVRT** (BREF‑only) or **PBB1** blueprints, tiny *accumulators* (e.g., counters/hashes). No bulk payload leaves the zone. Clients can recompute/verify before trusting.

**Constraints.**

* **Pure & bounded.** Tasks must be deterministic and time‑bounded; no unbounded crawling inside L1.
* **Permissioned.** L1 runs only under your account/scope (your repo, your bucket, your project).
* **Integrity.** Keep PacketFS’s window sync + CRC16 in artifacts; add **AEAD** if you need confidentiality. The same encoder/decoder you ship today applies; the arithmetic encoder tool remains the ground truth for frames.

---

## Patterned **use‑cases** (how L1/L2 help in practice)

* **Edge planning (near data).** Drop a file into a bucket; a Lambda/Worker runs the **planner** where the file lives, emits `{offset,len,transform}` segments (plus RAW spill if needed), and writes a **PBB1** to the same bucket. Clients fetch the blueprint (tiny) and reconstruct locally. No heavy egress. (This aligns with your POB/Planner direction; the transform set stays `id/xor/add imm8` to keep RX cheap.)
* **CI publish path.** A GitHub Action builds a release artifact consisting of **(a)** the app and **(b)** the **IPROG** (per‑window PVRT) and window‑hash index. CDNs cache those tiny control files cheaply; clients hit the nearest edge for blueprints and reconstruct from their blob. The **transfer chapter** and r\*=N/Cr^\*=N/C math still apply—only the distribution plane changed.
* **Join/orchestration (P4XOS).** A joiner process (can be L1) reconciles blob identities (name/size/seed), publishes “who owns which windows,” and streams just the **misses** as blueprints. It’s consistent with your FS/mount semantics and PVRT windowing (sync every 2W2^W).
* **Index refreshers.** Periodic Actions/Workers regenerate  **palette manifests** ,  **per‑window hashes** , and **blueprint packs** (JSON→PBB1). Clients subscribe to small index updates instead of rereading content. Control‑plane cost remains microscopic (5/65536 ≈ 0.0076% at W=16W=16).

---

## How to write this into the paper (drop‑in text)

> **Remote listeners are first‑class pCPUs.** In PacketFS, a “listener” is any executor that accepts a bounded PacketFS task and emits deterministic artifacts. We model three classes: **L0** (local pCPU threads), **L1** (cooperative remote functions like GitHub Actions or Lambda/Workers we control), and **L2** (inert storage/CDN that distributes blueprints). L1/L2 do not change PacketFS semantics: files are still **arithmetic programs** over a deterministic blob; on‑wire remains **BREF‑only PVRT** by default; the control plane still injects **5‑byte** sync frames per 2W2^W refs; and the **pCPU runtime** continues to report real throughput/queueing/activation. What changes is *where* some work runs (near data or at the edge), not *what* the work is.

You can follow that paragraph with a small *“Where to place compute”* box that uses the same **break‑even** lens you already use for transfer:

* If r≤r\*=N/Cr \le r^\* = N/C, network falls out; spend budget on **compute near data** (L1) or on **local pCPU** (L0), whichever reduces end‑to‑end memory touches.
* If r>r\*r > r^\*, reduce wire by publishing blueprints via **L1/L2** and letting clients reconstruct locally (drive r↓r\downarrow).

---

## Safety & governance (explicit)

* **No unsolicited execution** : we never run inside third‑party servers we don’t control; we only execute where we’re permitted (your CI, your serverless account).
* **Attestation by construction** : artifacts are deterministic; window sync + CRC16 are present; clients can re‑encode small windows locally to spot‑check; add **AEAD** if needed.
* **Same APIs, same tools** : L1 just runs the **same encoders and planners** you ship (ProtocolEncoder/Decoder, arithmetic encoder, IR front‑end when needed). The PacketFS client trusts results only after verification.

---

## Why this slots cleanly into your existing implementation

* **Filesystem wrapper is the universal interface.** Your FUSE mount already compiles files into **IPROGs** (PVRT, BREF‑only by default) and maintains a tiny metastore. L1 simply performs parts of that compilation or publishes the resulting artifacts; L2 just hosts them.
* **Protocol/encoder is transport‑agnostic.** The `[0xF0][win:16][CRC16:16]` sync and 1‑byte arithmetic refs work the same whether they travel over TCP/UDP, WS/QUIC, a kernel ring, or sit in a CDN object. The tool `encode_file_to_arith.py` is your reproducible frame generator.
* **pCPU runtime exposes real metrics wherever it runs.** Whether the packets are executed locally (L0) or proxied through a service that returns *artifacts* (L1), you still compute **CPUPwn** from elapsed times and surface throughput/queue‑wait/activation from the same **PacketExecutor/PCPUScheduler** scaffolding.
* **Kernel‑assist remains a local superpower.** For localhost/LAN, the `/dev/pfs_ringpeek` path and SHM ring bench are still your fastest route; none of the remote machinery detracts from that. Use L1/L2 when they  *reduce movement* , not as a reflex.

---

> PacketFS treats **serverless/CI/edge** endpoints as *cooperative pCPU shards* (listeners) and **storage/CDNs** as  *instruction memory* . Blueprints (PVRT/PBB1) flow through them; **execution** happens either locally or in those  **authorized listeners** , under the same sync and verification rules. The effect is the same: **ship intent, execute near data, move almost no bytes.**

If you want, I can weave this into the existing “Internet as CPU” chapter you approved and add a small figure that labels  **L0/L1/L2** , shows the **PVRT/PBB1** flow, and anchors the math with your

## §Then we asked: can the **Internet** be our CPU?

The shift is conceptual but simple: **packets are instructions.** If we can ship tiny, runnable descriptors as ordinary web content, we can treat the **Internet (storage + CDNs)** as a  *distribution plane for blueprints* , while  **all execution remains on our PacketFS client** . No server code, no in‑process hooks, no privileged access—just **deliver blueprints as static objects** the client knows how to execute.

### A. Threat model and boundary (so we stay honest)

* **No server execution.** We do **not** run code on web servers or inside their processes. We **only** fetch artifacts the servers or CDNs are happy to serve (e.g., files in buckets, signed URLs, public blobs). Execution happens on a PacketFS node that voluntarily interprets those artifacts as blueprints.
* **Authorized surfaces only.** Upload or publish blueprints only where you own the content or have explicit permission (your bucket, your CDN origin, user‑contributed areas with ToS that allow it). No injections, no exploits.
* **End‑to‑end integrity.** PacketFS already has a minimal control plane with  **window sync and CRC16** ; we reuse that here. If you need cryptographic assurances, wrap the control stream in a standard **AEAD** (e.g., AES‑GCM/XChaCha20‑Poly1305) as specified in the terminology note.

### B. Execution model in the wild (what “Internet as CPU” really means)

1. **Publish blueprints as web objects.** An **IPROG** (per‑window PVRT, BREF‑only) or its binary form (PBB1) is uploaded to storage/CDN as static files. These are our **packets** (runnable descriptors) encoded for transport.
2. **Discover & fetch.** A PacketFS node (or a cooperating tool like  *pfscp* ) resolves a URL, fetches the blueprint, and **executes locally** against its blob. The network’s role is to deliver tiny control bytes; the  **heavy lifting is local memory + tiny transforms** .
3. **Cache amplification (the “CDN advantage”).** Because blueprints are small and deterministic, CDNs **cache them cheaply** and fan them out widely; many receivers reconstruct from the same artifact. We pay once per edge, not per gigabyte of payload.
4. **Window‑hash sync at scale.** For change detection, we can publish per‑window hashes (or an index) at a stable URL; clients compare and ask only for the windows they miss, exactly aligning with PacketFS’s change‑driven transfer plan.

### C. Minimal viability test (what we already validated)

* **Server‑agnostic delivery works.** We have **successfully fetched and executed blueprints served by unmodified HTTP endpoints** (generic storage/CDN). The server merely returns bytes; our client maps those bytes to PacketFS descriptors and reconstructs locally. This is fully consistent with our existing control plane and does not require special server cooperation.
* **Performance intuition holds.** The same **break‑even** math applies at Internet scale: with compute CC**C** around **10.5 GB/s** (2 MiB pages, today) and link NN**N** of 10 GbE per receiver, end‑to‑end flips compute‑bound when the **wire ratio rr**r**** falls below  **~0.12** . Blueprints are engineered to keep rr**r** tiny; hence we remain compute‑bound and benefit from local memory throughput instead of paying per‑receiver payload bytes.

### D. The **Packet‑capable spider** (what we’re building next)

We are implementing a **PacketFS‑capable spider** with two roles:

* **(1) Communicator.** Speak PacketFS natively (PVRT/PBB1 over PFS‑TCP/UDP/WS/QUIC) so it can bootstrap nodes and seed blueprints into authorized storage planes it controls (your buckets, your repos, your CDN origins).
* **(2) Publisher.** Where permitted, publish  **PacketOS artifacts** —blueprints, per‑window hashes, palette manifests—so that any PacketFS client can fetch and execute locally. Think of this as **placing mail in well‑known mailboxes** that the network already optimizes: storage objects with long TTLs, CDN‑cached control frames, etc. Execution remains on clients.

**Why this is attractive.** Storage/CDN costs are dominated by payload bytes and egress. We move almost all payload off wire and  **replace it with tiny blueprints** . CDNs excel at shipping tiny, cacheable objects; PacketFS excels at  **reconstructing locally** . The composition is natural.

---

## Implementation receipts (so reviewers can connect dots)

* **Filesystem & tools** (translation daemon; FUSE mount; PVRT BREF‑only defaults; WS sender; palette/append modes). These are the wrapper’s building blocks.
* **Protocol math** (SYNC mark, CRC16; overhead **5/2^W** per op; arithmetic windows ≈ **1 B/op** with base+sync amortized). This is the same control plane whether blueprints ride TCP/UDP, WS/QUIC, or a CDN.
* **pCPU runtime** (PacketExecutor, PCPUConfig/Registry/Scheduler) with **real metrics** (throughput, queue‑wait, activation) that we already use to compute CPUPwn and to find the concurrency knee. These surfaces don’t change when the blueprint is fetched from a URL.
* **Compute path numbers** (2 MiB hugepages, peak  **~10.49 GB/s** , plateau at 200k–400k activated pCPUs). These are the CC**C** terms in the Internet‑scale r\*=N/Cr^\*=N/C**r**\***=**N**/**C analysis.
* **Project ethos & positioning** (“The filesystem **IS** packets… ONLY IMPLEMENTATION”). The “Internet as CPU” step is a faithful extension: packets are instructions; servers carry the instructions; clients execute.

---

## Risks, ethics, and mitigations (explicitly)

* **Permissioned publishing only.** The spider publishes artifacts **only** to surfaces you own/control or where ToS permits (e.g., your object store, your repo, your CDN origin).
* **No server exploitation.** We don’t change server behavior; we **consume** bytes with well‑known clients that voluntarily interpret them as blueprints.
* **Integrity & confidentiality.** Continue to use **window sync + CRC16** for alignment and add **AEAD** for confidentiality where required. Cross‑arch issues (endianness/packing) remain on our radar; we’ve documented mitigations before widening deployment.

r\*=N/Cr^\*=N/C curve.
