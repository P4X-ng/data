from __future__ import annotations

import time
from fastapi import APIRouter, Body, HTTPException

from app.services.gpu.accelerate import gpu_capabilities, counteq_stream
from app.services.pfs_reader import stream_window, pin_cpu_if_requested

router = APIRouter()

ALIGN = 1 << 20  # 1 MiB
CHUNK = 4 << 20  # 4 MiB


@router.get("/gpu/status")
async def gpu_status():
    caps = gpu_capabilities()
    return {"gpu": caps}


@router.post("/gpu/program")
async def gpu_program(
    body: dict = Body(..., description="{ data_url, program:[{op, imm?}], offset?, length?, gpu_device? }"),
):
    data_url = body.get("data_url")
    program = body.get("program")
    offset = body.get("offset")
    length = body.get("length")
    gpu_device = body.get("gpu_device")

    if not isinstance(data_url, str) or not data_url:
        raise HTTPException(status_code=400, detail="missing data_url")
    if not isinstance(program, list) or not program:
        raise HTTPException(status_code=400, detail="missing program")

    from app.services.gpu.accelerate import program_execute_stream

    t0 = time.time()
    with pin_cpu_if_requested():
        # Optional GPU device selection (CuPy)
        if gpu_device is not None:
            try:
                import cupy as cp  # type: ignore
                with cp.cuda.Device(int(gpu_device)):
                    acc, metrics = program_execute_stream(
                        stream_window(data_url, offset, length, align=ALIGN, chunk=CHUNK), program
                    )
            except Exception:
                # Fallback without explicit device
                acc, metrics = program_execute_stream(
                    stream_window(data_url, offset, length, align=ALIGN, chunk=CHUNK), program
                )
        else:
            acc, metrics = program_execute_stream(
                stream_window(data_url, offset, length, align=ALIGN, chunk=CHUNK), program
            )
    elapsed_ms = (time.time() - t0) * 1000.0
    elapsed_s = max(elapsed_ms / 1000.0, 1e-9)
    bytes_processed = metrics.get("bytes_processed", 0) or 0
    cpupwn_gbps = (bytes_processed / elapsed_s) / (1024**3)

    return {
        "success": True,
        "acc": acc,
        "metrics": {**metrics, "elapsed_ms": float(elapsed_ms), "cpupwn_gbps": float(cpupwn_gbps)},
    }


@router.post("/gpu/compute")
async def gpu_compute(
    body: dict = Body(..., description="{ data_url, op='counteq', imm?, offset?, length? }"),
):
    data_url = body.get("data_url")
    op = str(body.get("op", "counteq"))
    imm = body.get("imm", 0)
    offset = body.get("offset")
    length = body.get("length")

    if not isinstance(data_url, str) or not data_url:
        raise HTTPException(status_code=400, detail="missing data_url")
    if op != "counteq":
        # For MVP, only counteq is GPU-accelerated; others can be added later.
        raise HTTPException(status_code=400, detail="unsupported op (only 'counteq' supported)")

    t0 = time.time()
    with pin_cpu_if_requested():
        total, backend, processed = counteq_stream(
            stream_window(data_url, offset, length, align=ALIGN, chunk=CHUNK), int(imm)
        )
    elapsed_ms = (time.time() - t0) * 1000.0

    # CPUpwn metric: effective GB/s vs single CPU linear baseline
    elapsed_s = max(elapsed_ms / 1000.0, 1e-9)
    cpupwn_gbps = (processed / elapsed_s) / (1024**3)

    return {
        "success": True,
        "op": op,
        "value": int(total),
        "elapsed_ms": float(elapsed_ms),
        "bytes_processed": int(processed),
        "gpu_backend": backend,
        "gpu_available": backend in ("cupy", "numba"),
        "cpupwn_gbps": float(cpupwn_gbps),
    }
