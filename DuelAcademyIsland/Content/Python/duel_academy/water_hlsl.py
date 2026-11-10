"""
HLSL for M_DA_Water's Custom nodes (no `unreal` import: unit-tested from Tools/tests).

The sea is a sum of Gerstner waves (WAVES): a long swell plus shorter wind waves, travelling roughly the same
way, with deep-water dispersion (w = sqrt(g k)), so long waves run faster than short ones as they do at sea.
Every wave is scaled per point by

  * the water depth (T_WaterField R): the swell keeps its height into the shallows and sharpens as it
    shoals (more chop, more whitecaps), then dies out over the last ~1.6 m of depth - the breaking limit -
    instead of running up the beach,
  * the exposure (B): sheltered water (the harbour behind its breakwater) is calmer than the open coast,
  * what can be drawn: the vertex offset drops waves shorter than ~4 mesh cells (the ocean clipmap's cells
    grow with distance from the camera), the per-pixel normal drops waves shorter than ~2 pixels -
    so nothing aliases and far water keeps its waves in the shading only.

Steepness is shared out so the sum never folds over (sum of Q k A = 0.46 Choppy Height shoaling, capped at 0.93); the Jacobian
of the horizontal displacement drives the whitecaps (it drops towards 0 at sharp crests; CapsAt is where they
start - 0.75 whitens the sharpest few percent of a moderate sea).

All lengths are metres inside the code; positions come in as Unreal centimetres.
"""

import math

G = 9.81

# wavelength (m), amplitude (m), heading (deg, Unreal world XY: 0 = +X), steepness (0..1), phase (rad)
WAVES = (
    (61.0, 0.30, 32.0, 0.30, 0.0),
    (37.0, 0.19, 52.0, 0.40, 1.7),
    (23.0, 0.12, 14.0, 0.45, 4.1),
    (14.5, 0.075, 68.0, 0.50, 2.6),
    (9.2, 0.045, -4.0, 0.55, 5.3),
    (6.1, 0.028, 41.0, 0.55, 0.9),
    (3.9, 0.016, 21.0, 0.50, 3.4),
)

# cap on Choppy * Height * shoaling: the shares q sum to 0.464, so the total steepness stays below 0.93
QS_MAX = 2.0

# T_WaterField encoding (Tools/dai/water.py)
FIELD_DEPTH = 40.0
SHORE_MIN, SHORE_MAX = -50.0, 500.0

_COMMON_IN = ("P", "T", "Field", "Cam", "Height", "Len", "Choppy", "Wind", "Spacing", "Clip")


def wave_constants(waves=WAVES):
    """[(L, A, dx, dy, k, w, q, phase)] - q is the share of the steepness (Q k A of the wave at full size)."""
    n = len(waves)
    out = []
    for L, A, deg, steep, ph in waves:
        k = 2.0 * math.pi / L
        a = math.radians(deg)
        out.append((L, A, math.cos(a), math.sin(a), k, math.sqrt(G * k), steep / n, ph))
    return out


def _f(x):
    return f"{x:.7g}"


def _prologue():
    return (
        "float2 p = P.xy * 0.01;\n"
        "float depth = Field.x * " + _f(FIELD_DEPTH) + ";\n"
        "float expo = lerp(0.5, 1.0, Field.z);\n"
        "float shoal = saturate(depth / 1.6);            // breaking limit: full swell until ~1.6 m deep\n"
        "float steep = 1.0 + 0.8 * (1.0 - saturate(depth / 8.0));   // shoaling waves sharpen\n"
        "float qs = min(Choppy * Height * steep, " + _f(QS_MAX) + ");   // total steepness < 1: never folds\n"
        "float dist = length(P - Cam) * 0.01;\n"
        "float wr = radians(Wind);\n"
        "float2 wc = float2(cos(wr), sin(wr));\n"
        "float2 pr = float2(p.x * wc.x + p.y * wc.y, -p.x * wc.y + p.y * wc.x);   // into the wind frame\n"
    )


def _wave_head(c, fade):
    """Shared per-wave lines: L, k, w, amplitude A (with fades), phase th. `fade` is the resolution fade."""
    L, A, dx, dy, k, w, q, ph = c
    return (
        "{\n"
        f"  const float2 D = float2({_f(dx)}, {_f(dy)});\n"
        f"  float L = {_f(L)} * Len;\n"
        "  float k = 6.2831853 / L;\n"
        "  float w = sqrt(9.81 * k);\n"
        f"  float f = shoal * expo * {fade};\n"
        f"  float A = {_f(A)} * Len * Height * f;\n"
        f"  float H = qs * {_f(q)} / k * f;               // horizontal amplitude (Q A)\n"
        f"  float th = k * dot(D, pr) - w * T + {_f(ph)};\n"
        "  float s = sin(th), c = cos(th);\n"
    )


def wpo_code(waves=WAVES):
    """Custom node -> float3 world position offset (cm). Inputs: _COMMON_IN."""
    body = [_prologue(),
            "float sp = max(Spacing, dist * Clip);          // mesh cell size here (m)\n",
            "float3 o = 0;\n"]
    for c in wave_constants(waves):
        body.append(_wave_head(c, "saturate(L / (4.0 * sp) - 1.0)"))
        body.append("  o.xy += D * (H * c);\n  o.z += A * s;\n}\n")
    body.append("o.xy = float2(o.x * wc.x - o.y * wc.y, o.x * wc.y + o.y * wc.x);   // back to world\n")
    body.append("return o * 100.0;\n")
    return "".join(body)


def normal_code(waves=WAVES):
    """Custom node -> float3 world normal of the waves; extra output Crest (Jacobian, 1 = flat, < 0.4 = crest).
    Inputs: _COMMON_IN (Spacing / Clip unused - the pixel fade uses the pixel footprint instead)."""
    body = [_prologue(),
            "float px = max(dist * 0.0012, 0.001);         // ~ one pixel (m) at this distance\n",
            "float3 n = float3(0, 0, 1);\n",
            "float jxx = 1, jyy = 1, jxy = 0;\n"]
    for c in wave_constants(waves):
        body.append(_wave_head(c, "saturate(L / (6.0 * px) - 1.0)"))
        body.append("  n.xy -= D * (k * A * c);\n"
                    "  float qk = H * k * s;\n"
                    "  n.z -= qk;\n"
                    "  jxx -= qk * D.x * D.x;  jyy -= qk * D.y * D.y;  jxy -= qk * D.x * D.y;\n"
                    "}\n")
    body.append("n.xy = float2(n.x * wc.x - n.y * wc.y, n.x * wc.y + n.y * wc.x);\n")
    body.append("Crest = jxx * jyy - jxy * jxy;\n")
    body.append("return normalize(n);\n")
    return "".join(body)


FOAM_IN = ("Field", "T", "Crest", "Churn", "Breakup", "Foam", "Surf", "SurfSpacing", "SurfPeriod", "SurfWidth", "CapsAt")


def foam_code():
    """Custom node -> foam coverage 0..1 (surf bands rolling onto the beach, a lapping rim at the waterline,
    whitecaps on steep crests), broken up by the churned foam texture."""
    return (
        "float sd = Field.y * " + _f(SHORE_MAX - SHORE_MIN) + " + " + _f(SHORE_MIN) + ";   // m from the shore\n"
        "float expo = Field.z;\n"
        "float rim = (1.0 - smoothstep(0.0, 2.5, sd)) * smoothstep(-1.5, 0.0, sd);\n"
        "float ph = sd / SurfSpacing + T / SurfPeriod + Breakup * 1.7;\n"
        "float band = pow(saturate(sin(6.2831853 * ph)), 3.0);\n"
        "float env = saturate(1.0 - sd / SurfWidth) * smoothstep(0.5, 3.0, sd) * lerp(0.45, 1.0, expo);\n"
        "float caps = saturate((CapsAt - Crest) * 6.0) * lerp(0.3, 1.0, expo);\n"
        "float f = rim * 0.85 + band * env * Surf + caps;\n"
        "float lace = saturate(Churn * 1.8 - 0.35 + f * 0.35);\n"
        "return saturate(f * lace * Foam);\n"
    )


DETAIL_IN = ("P", "T", "Scale", "Speed", "Flow")


def detail_uv_code():
    """Custom node -> float2 UV of detail layer 1; extra outputs UV2 (finer, crossing) and UV3 (macro, breaks
    the tiling far out). Flow (m/s, world XY) drags the ripples downstream in rivers."""
    return (
        "float2 p = P.xy * 0.01;\n"
        "float2 fl = Flow.xy * T;\n"
        "UV2 = (p - fl) * Scale * 2.7 + T * Speed * float2(-0.021, 0.034);\n"
        "UV3 = (p - fl * 0.5) * Scale * 0.11 + T * Speed * float2(0.004, 0.0025);\n"
        "return (p - fl) * Scale + T * Speed * float2(0.03, 0.017);\n"
    )


def gerstner(px, py, t, depth=40.0, expo=1.0, height=1.0, length=1.0, choppy=1.0, wind=0.0, waves=WAVES):
    """numpy mirror of wpo_code/normal_code (no resolution fades): returns (offset xyz m, normal, crest).
    Used by the tests (no fold-over, crest range) and for preview renders."""
    import numpy as np
    px, py = np.asarray(px, np.float64), np.asarray(py, np.float64)
    wr = math.radians(wind)
    wc = (math.cos(wr), math.sin(wr))
    prx, pry = px * wc[0] + py * wc[1], -px * wc[1] + py * wc[0]
    e = 0.5 + 0.5 * np.asarray(expo, np.float64)
    d = np.asarray(depth, np.float64)
    shoal = np.clip(d / 1.6, 0, 1)
    steep = 1.0 + 0.8 * (1.0 - np.clip(d / 8.0, 0, 1))
    o = np.zeros(px.shape + (3,))
    n = np.zeros(px.shape + (3,))
    n[..., 2] = 1.0
    jxx, jyy, jxy = np.ones(px.shape), np.ones(px.shape), np.zeros(px.shape)
    for L0, A0, dx, dy, k0, w0, q, ph in wave_constants(waves):
        L = L0 * length
        k = 2 * math.pi / L
        w = math.sqrt(G * k)
        f = shoal * e
        A = A0 * length * height * f
        H = np.minimum(choppy * height * steep, QS_MAX) * q / k * f
        th = k * (dx * prx + dy * pry) - w * t + ph
        s, c = np.sin(th), np.cos(th)
        o[..., 0] += dx * H * c
        o[..., 1] += dy * H * c
        o[..., 2] += A * s
        n[..., 0] -= dx * k * A * c
        n[..., 1] -= dy * k * A * c
        qk = H * k * s
        n[..., 2] -= qk
        jxx -= qk * dx * dx
        jyy -= qk * dy * dy
        jxy -= qk * dx * dy
    ox, oy = o[..., 0].copy(), o[..., 1].copy()
    o[..., 0], o[..., 1] = ox * wc[0] - oy * wc[1], ox * wc[1] + oy * wc[0]
    nx, ny = n[..., 0].copy(), n[..., 1].copy()
    n[..., 0], n[..., 1] = nx * wc[0] - ny * wc[1], nx * wc[1] + ny * wc[0]
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return o, n, jxx * jyy - jxy * jxy
