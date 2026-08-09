#!/usr/bin/env python3
"""PROBE NEW-08: does an SSE/APM layer over a non-SSE backend-analogue recover >=2%?

Models (all figures are PROBE size models, ideal -log2(p) bits, not the codec):
  mr : med16 residual stream (faithful port of med16_detect_width + med16_forward
       from codec.rs @ d212c1c), coded by an adaptive order-1 bitwise counter
       model (analogue of the rail's adaptive CM-class coder; the real nested
       winner is BWT+geomix, symbol-level -- noted as fidelity limit).
  sao: raw record stream (width 28), coded by an adaptive bitwise model keyed on
       (offset-in-record, byte-at-i-28, c0) -- control arm only; the shipped
       record_cm already contains 4 APM stages + competed per-offset SSE.

Arms per file: base vs base+APM(SSE), each continuous and 64KB-reset.
APM: 33-knot interpolated table keyed on quantized stretch(p) x small context,
initialised to identity (no-op untrained), learned ONLINE (transient charged).
Final blend p = (p_base + 3*p_apm) >> 2 (same shape codec.rs uses for apm5).
"""
import math, sys, time

PSCALE = 4096

def build_tables():
    log2 = [0.0] * PSCALE
    for p in range(1, PSCALE):
        log2[p] = -math.log2(p / PSCALE)
    # stretch table: st(p) in [-2047,2047] scaled ln(p/(1-p)) * 256
    st = [0] * PSCALE
    for p in range(1, PSCALE):
        x = math.log(p / (PSCALE - p)) * 256.0
        st[p] = max(-2047, min(2047, int(round(x))))
    st[0] = -2047
    # squash inverse for APM knot init: knot i -> stretch value -> p
    knots = []
    for i in range(33):
        x = (i * 2 * 2048) / 32.0 - 2048.0  # -2048..2048
        p = PSCALE / (1.0 + math.exp(-x / 256.0))
        knots.append(max(1, min(PSCALE - 1, int(round(p)))))
    return log2, st, knots

LOG2, ST, KNOTS = build_tables()

def med16_predict(a, b, c):
    mn, mx = (a, b) if a < b else (b, a)
    if c >= mx:
        return mn
    if c <= mn:
        return mx
    return (a + b - c) & 0xFFFF

def med16_detect_width(samples):
    n = len(samples)
    if n < 8192:
        return None
    sample_n = min(n, 1 << 13)
    wmax = min(n // 8, 4096)
    if wmax < 256:
        return None
    costs = []
    best_w, best_cost = 0, None
    for w in range(256, wmax + 1):
        cost = 0
        for i in range(w, sample_n):
            cost += abs(samples[i] - samples[i - w])
        cnt = max(sample_n - w, 1)
        avg = cost // cnt
        costs.append(avg)
        if best_cost is None or avg < best_cost:
            best_cost, best_w = avg, w
    costs.sort()
    median = costs[len(costs) // 2]
    if best_cost * 100 < median * 80:
        return best_w
    return None

def med16_forward(samples, w):
    n = len(samples)
    out = [0] * n
    for i in range(n):
        x = i % w
        a = samples[i - 1] if x > 0 else 0
        b = samples[i - w] if i >= w else 0
        c = samples[i - w - 1] if (i >= w and x > 0) else 0
        out[i] = (samples[i] - med16_predict(a, b, c)) & 0xFFFF
    return out

class Apm:
    __slots__ = ("t", "nctx")
    def __init__(self, nctx):
        self.nctx = nctx
        self.t = []
        for _ in range(nctx):
            self.t.extend(KNOTS)  # identity init: untrained APM is a no-op

    def refine(self, p, ctx):
        v = ST[p] + 2048  # 0..4095
        pos = v * 32
        lo = pos >> 12
        if lo > 31:
            lo = 31
        wfrac = pos - (lo << 12)  # 0..4095
        base = ctx * 33 + lo
        t = self.t
        pa = (t[base] * (4096 - wfrac) + t[base + 1] * wfrac) >> 12
        if pa < 1:
            pa = 1
        elif pa > PSCALE - 1:
            pa = PSCALE - 1
        return pa, base, wfrac

    def update(self, base, wfrac, bit):
        t = self.t
        g = (bit << 12)
        # update both knots, weighted toward the nearer one (rate 7)
        t[base] += (g - t[base]) * (4096 - wfrac) >> (12 + 7 - 5)  # ~rate 7 scaled
        t[base + 1] += (g - t[base + 1]) * wfrac >> (12 + 7 - 5)
        if t[base] < 1: t[base] = 1
        if t[base] > PSCALE - 1: t[base] = PSCALE - 1
        if t[base + 1] < 1: t[base + 1] = 1
        if t[base + 1] > PSCALE - 1: t[base + 1] = PSCALE - 1

def code_stream(stream, ctx_fn, nctx_model, use_apm, apm_nctx, apm_ctx_fn,
                reset_every=None):
    """Adaptive order-N bitwise counter model; returns total ideal bits.
    ctx_fn(i, prev_bytes, c0) -> model row; apm_ctx_fn(i, prev_bytes) -> apm row.
    reset_every: reset ALL adaptive state every N input bytes (models 64KB rail
    chunking; learning transient charged per chunk)."""
    n = len(stream)
    bits = 0.0
    def fresh():
        return [2048] * (nctx_model * 256), (Apm(apm_nctx) if use_apm else None)
    model, apm = fresh()
    log2 = LOG2
    prev = 0
    prev_rec = stream  # alias; sao ctx uses stream[i - width] directly
    for i in range(n):
        if reset_every is not None and i > 0 and i % reset_every == 0:
            model, apm = fresh()
        byte = stream[i]
        row = ctx_fn(i, prev) << 8
        if use_apm:
            actx = apm_ctx_fn(i, prev)
        c0 = 1
        for k in range(7, -1, -1):
            bit = (byte >> k) & 1
            idx = row | c0
            p = model[idx]
            if use_apm:
                pa, base, wfrac = apm.refine(p, actx)
                pf = (p + 3 * pa) >> 2
                if pf < 1: pf = 1
                elif pf > PSCALE - 1: pf = PSCALE - 1
            else:
                pf = p
            bits += log2[pf] if bit else log2[PSCALE - pf]
            if bit:
                model[idx] = p + ((PSCALE - p) >> 5)
            else:
                model[idx] = p - (p >> 5)
            if use_apm:
                apm.update(base, wfrac, bit)
            c0 = (c0 << 1) | bit
        prev = byte
    return bits

def run_file(name, stream, ctx_fn, nctx_model, apm_nctx, apm_ctx_fn):
    out = {}
    for regime, reset in (("continuous", None), ("64KB-reset", 65536)):
        for use_apm in (False, True):
            t0 = time.time()
            bits = code_stream(stream, ctx_fn, nctx_model, use_apm,
                               apm_nctx, apm_ctx_fn, reset)
            sz = bits / 8.0
            tag = f"{name} {regime} {'base+SSE' if use_apm else 'base    '}"
            out[(regime, use_apm)] = sz
            print(f"PROBE {tag}: {sz:,.0f} B  ({time.time()-t0:.0f}s)", flush=True)
        b, s = out[(regime, False)], out[(regime, True)]
        print(f"PROBE {name} {regime} SSE delta: {(b-s)/b*100:+.3f}%", flush=True)
    return out

def main():
    SL = 2 * 1024 * 1024  # 2 MB slices
    # ---- mr: med16 residual stream ----
    with open("/home/dev/cubr-cubecore-research/corpus-silesia/mr", "rb") as f:
        raw = f.read()
    off = 2 * 1024 * 1024
    sl = raw[off:off + SL]
    samples = [sl[2 * i] | (sl[2 * i + 1] << 8) for i in range(len(sl) // 2)]
    w = med16_detect_width(samples)
    print(f"mr slice [{off}:{off+SL}] detect_width -> {w}", flush=True)
    if w is None:
        w = 512  # fall back to a swept width from encode_med16's list
        print("mr: detector declined on slice; using swept width 512", flush=True)
    res = med16_forward(samples, w)
    stream = []
    for r in res:
        stream.append(r & 0xFF); stream.append(r >> 8)
    # Arm A (weak base): model ctx = prev byte only; APM ctx = (parity, prev).
    # APM here ADDS context the base lacks -> upper-hint, overstates pure SSE.
    run_file("mr/med16-res armA-weakbase", stream,
             lambda i, prev: prev, 256,
             512, lambda i, prev: ((i & 1) << 8) | prev)
    # Arm B (strong base): model ctx = (parity, prev); APM ctx identical subset
    # -> measures CALIBRATION only, the honest SSE-over-existing-backend figure.
    run_file("mr/med16-res armB-strongbase", stream,
             lambda i, prev: ((i & 1) << 8) | prev, 512,
             512, lambda i, prev: ((i & 1) << 8) | prev)

    # ---- sao: record stream, width 28 ----
    with open("/home/dev/cubr-cubecore-research/corpus-silesia/sao", "rb") as f:
        raw = f.read()
    sl = raw[1024 * 1024:1024 * 1024 + SL]
    stream = list(sl)
    W = 28
    sref = stream
    def sao_ctx(i, prev, _s=sref, _W=W):
        offs = i % _W
        pb = _s[i - _W] if i >= _W else 0
        return offs * 256 + pb
    run_file("sao/records", stream, sao_ctx, 28 * 256,
             28, lambda i, prev, _W=W: i % _W)

if __name__ == "__main__":
    main()
