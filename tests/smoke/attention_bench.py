"""Аттеншен-бэкенды на этой машине: что доступно, что быстрее, насколько расходится с эталоном.

    podman exec comfy-main python - < tests/smoke/attention_bench.py
    (или bash tools/comfy attn-bench)

Сравниваем на форме MiniMax H3 (bf16, head_dim 128):
  - pytorch attention (SDPA, backend по умолчанию ComfyUI);
  - comfy kitchen attention (INT8, нода Model Attention Backend) — на AMD идёт через WMMA-ядра HIP;
  - sol-attn (нода Block Sparse Attention, method=sol-attn) — разреженный, на длинных последовательностях.
Эталон — SDPA в float32; расхождение считаем как косинусную близость и максимум модуля разницы.
"""
import time

import torch

import comfy_kitchen as ck

DEV = "cuda"
DTYPE = torch.bfloat16
HEADS = 8
DIM = 128
SEQS = (2048, 8192, 16384, 32768)
WARMUP, ITERS = 2, 5


def bench(fn, *a, **kw):
    """(мс на вызов, пик доп. памяти в МиБ, результат)."""
    for _ in range(WARMUP):
        fn(*a, **kw)
    torch.cuda.synchronize()
    base = torch.cuda.memory_allocated()
    torch.cuda.reset_peak_memory_stats()
    t0 = time.perf_counter()
    for _ in range(ITERS):
        out = fn(*a, **kw)
    torch.cuda.synchronize()
    peak = (torch.cuda.max_memory_allocated() - base) / 2 ** 20
    return (time.perf_counter() - t0) / ITERS * 1000, peak, out


def quality(out, ref):
    o, r = out.float().flatten(), ref.float().flatten()
    cos = torch.nn.functional.cosine_similarity(o, r, dim=0).item()
    return cos, (o - r).abs().max().item()


def main():
    print(f"GPU: {torch.cuda.get_device_properties(0).gcnArchName} | torch {torch.__version__}")
    print(f"comfy-kitchen бэкенды: {[n for n, v in ck.list_backends().items() if v['available']]}")
    print(f"int8_attention доступен: {ck.int8_attention_is_available()}")
    sol = "sol_attn" in ck.list_backends().get("hip", {}).get("capabilities", [])
    print(f"sol_attn в HIP-бэкенде: {sol}")
    from comfy_kitchen.backends import hip as hip_backend

    def sol(q, k, v, tau=1.3):
        # sol_attn ждёт (B, T, H, D), SDPA даёт (B, H, T, D)
        out = hip_backend.sol_attn(q.transpose(1, 2).contiguous(), k.transpose(1, 2).contiguous(),
                                   v.transpose(1, 2).contiguous(), tau=tau)
        return out.transpose(1, 2)

    print(f"\n{'seq':>7}  {'бэкенд':<16} {'время':>9} {'к SDPA':>8} {'пик памяти':>11} {'cos к fp32':>11} {'max|Δ|':>8}")
    for seq in SEQS:
        g = torch.Generator(device=DEV).manual_seed(0)
        q, k, v = (torch.randn(1, HEADS, seq, DIM, generator=g, device=DEV, dtype=DTYPE) for _ in range(3))
        ref = torch.nn.functional.scaled_dot_product_attention(q.float(), k.float(), v.float())
        t_sdpa, m_sdpa, o_sdpa = bench(torch.nn.functional.scaled_dot_product_attention, q, k, v)
        rows = [("pytorch SDPA bf16", t_sdpa, m_sdpa, o_sdpa)]
        for name, fn in (("kitchen INT8", ck.int8_attention), ("sol-attn tau 1.3", sol)):
            try:
                t, m, o = bench(fn, q, k, v)
                rows.append((name, t, m, o))
            except Exception as e:                   # noqa: BLE001 — интересует любая причина отказа
                rows.append((name, None, None, e))
        for name, t, m, o in rows:
            if t is None:
                print(f"{seq if name == rows[0][0] else '':>7}  {name:<16} {'отказ: ' + type(o).__name__:>9}")
                continue
            cos, dmax = quality(o, ref)
            print(f"{seq if name == rows[0][0] else '':>7}  {name:<16} {t:>7.1f}мс {t_sdpa / t:>7.2f}x {m:>9.0f}МиБ {cos:>11.5f} {dmax:>8.4f}")
        del q, k, v, ref, rows
        torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
