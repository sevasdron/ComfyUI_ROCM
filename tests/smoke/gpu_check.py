"""Смоук-тест runtime: torch видит GPU gfx1151, matmul и SDPA считаются на GPU и дают верный результат.

Запуск: bash tools/runtime-test. Код выхода 0 — всё прошло. Печатает и скорость,
чтобы сравнивать наш образ с kyuz0 на одной машине.
"""
import os
import sys
import time

import torch
import torch.nn.functional as F

FAIL = []


def check(name, ok, detail=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name} {detail}")
    if not ok:
        FAIL.append(name)


def bench(fn, iters=20):
    fn()
    torch.cuda.synchronize()
    t = time.perf_counter()
    for _ in range(iters):
        fn()
    torch.cuda.synchronize()
    return (time.perf_counter() - t) / iters


print("torch      ", torch.__version__)
print("hip        ", torch.version.hip)
for var in ("TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL", "TORCH_BLAS_PREFER_HIPBLASLT"):
    print(f"{var}={os.environ.get(var)}")

check("cuda.is_available", torch.cuda.is_available())
if FAIL:
    sys.exit(1)

props = torch.cuda.get_device_properties(0)
arch = getattr(props, "gcnArchName", "")
print("device     ", torch.cuda.get_device_name(0), arch, f"{props.total_memory / 2**30:.1f} GiB")
check("arch gfx1151", arch.startswith("gfx1151"), arch)

# matmul bf16 на GPU против float32 на CPU
n = 4096
a = torch.randn(n, n, device="cuda", dtype=torch.bfloat16)
b = torch.randn(n, n, device="cuda", dtype=torch.bfloat16)
c = a @ b
ref = a.float().cpu() @ b.float().cpu()
err = (c.float().cpu() - ref).abs().max().item() / ref.abs().max().item()
check("matmul bf16 correct", err < 2e-2, f"rel_err={err:.2e}")
sec = bench(lambda: a @ b)
print(f"matmul {n}x{n} bf16: {2 * n**3 / sec / 1e12:.1f} TFLOPS")

# SDPA: результат по умолчанию против math-бэкенда
from torch.nn.attention import SDPBackend, sdpa_kernel

q, k, v = (torch.randn(1, 16, 2048, 64, device="cuda", dtype=torch.bfloat16) for _ in range(3))
out = F.scaled_dot_product_attention(q, k, v)
with sdpa_kernel(SDPBackend.MATH):
    ref = F.scaled_dot_product_attention(q, k, v)
diff = (out.float() - ref.float()).abs().max().item()
check("sdpa on gpu correct", out.is_cuda and diff < 2e-2, f"max_diff={diff:.2e}")
sec = bench(lambda: F.scaled_dot_product_attention(q, k, v))
print(f"sdpa 16h x 2048 x 64 bf16: {sec * 1e3:.2f} ms")
for name, backend in (("flash", SDPBackend.FLASH_ATTENTION), ("efficient", SDPBackend.EFFICIENT_ATTENTION)):
    try:
        with sdpa_kernel(backend):
            F.scaled_dot_product_attention(q, k, v)
        print(f"sdpa backend {name}: available")
    except Exception as e:  # noqa: BLE001
        print(f"sdpa backend {name}: not available ({type(e).__name__})")

# conv (MIOpen) — VAE и апскейлеры
x = torch.randn(1, 64, 256, 256, device="cuda", dtype=torch.bfloat16)
w = torch.randn(64, 64, 3, 3, device="cuda", dtype=torch.bfloat16)
y = F.conv2d(x, w, padding=1)
check("conv2d on gpu", y.is_cuda and torch.isfinite(y).all().item())

import triton  # noqa: E402
import torchvision  # noqa: E402
import torchaudio  # noqa: E402

print("triton     ", triton.__version__)
print("torchvision", torchvision.__version__)
print("torchaudio ", torchaudio.__version__)

print("RESULT:", "FAIL " + ", ".join(FAIL) if FAIL else "OK")
sys.exit(1 if FAIL else 0)
