#!/usr/bin/env python3
"""Reads a frame capture the Xenos renderer writes (game:\\oot360_capture_<frame>.bin, L3+R3 on the console).

    xenoscap.py CAPTURE OUTDIR

writes OUTDIR/draws.txt (the frame's trace and every draw: shader ids, variant, state, combiner constants, the first
vertices) and OUTDIR/tex_<id>.png for each texture the frame drew with, OUTDIR/screen.png for the picture.

A capture holds the game's textures: keep captures and their output outside the repository (the pre-commit hook
refuses images and game data anyway).
"""
import os
import struct
import sys

from PIL import Image

DRAW_FIELDS = ("index id0hi id0lo id1hi id1lo variant numFloats numTris numInputs used0 used1 texId0 texId1 texW0 texW1 "
               "texH0 texH1 linear0 linear1 threePoint0 threePoint1 addrU0 addrU1 addrV0 addrV1 depthKey useAlpha "
               "decal fb vp0 vp1 vp2 vp3 sc0 sc1 sc2 sc3 twoCycle mayKill vboFloats").split()
DRAW_SIGNED = {"depthKey", "useAlpha", "decal", "fb", "vp0", "vp1", "vp2", "vp3", "sc0", "sc1", "sc2", "sc3"}
# Version 1 captures (tests 6-11): fast3d.frag's weights per cycle and channel set over 16 sources.
CONST_NAMES_V1 = []
for cyc in ("color0", "alpha0", "color1", "alpha1"):
    for part in ("ab", "c", "d"):
        for i in range(4):
            CONST_NAMES_V1.append(f"{cyc}.{part}[{i}]")
CONST_NAMES_V1 += ["opts0", "opts1", "clamps", "sizes", "misc"]
# Version 2 (test 12 on): the pixel shader's constants, then the vertex shader's (gfx_xenos.h, XenosPixelConstants
# and XenosVertexConstants); each weight rgb colour, a alpha.
OPERANDS = ("ab0", "c0", "d0", "ab1", "c1", "d1")
PIXEL_SOURCES = ("tex0", "tex0a", "tex1", "tex1a", "comb", "noise")
VERTEX_SOURCES = ("in1", "in2", "in3", "in4", "in5", "in6", "in7", "one")
CONST_NAMES_V2 = ["sizes", "misc", "opts0", "opts1", "clamps"] + [f"{o}.{s}" for o in OPERANDS for s in PIXEL_SOURCES]
VERTEX_NAMES_V2 = ["prim"] + [f"{o}.{s}" for o in OPERANDS for s in VERTEX_SOURCES]
ALWAYS = {"opts0", "opts1", "clamps", "sizes", "misc", "prim"}


def records(data):
    if data[:8] != b"OOTCAP01":
        raise SystemExit("not a capture")
    pos = 8
    while pos + 8 <= len(data):
        kind, size = struct.unpack_from(">II", data, pos)
        pos += 8
        yield kind, data[pos:pos + size]
        pos += size


def main():
    src, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    data = open(src, "rb").read()
    lines = []
    const_bytes = vertex_bytes = 0
    names, vertex_names = CONST_NAMES_V1, []
    for kind, body in records(data):
        if kind == 0:
            const_bytes, frame, version = struct.unpack(">III", body[:12])
            if version >= 2:
                vertex_bytes = struct.unpack(">I", body[12:16])[0]
                names, vertex_names = CONST_NAMES_V2, VERTEX_NAMES_V2
            lines.append(f"capture of frame {frame}, version {max(version, 1)}, constants {const_bytes} + "
                         f"{vertex_bytes} bytes")
        elif kind == 1:
            lines.append(body.decode("latin-1"))
        elif kind == 2:
            n = len(DRAW_FIELDS)
            raw = struct.unpack_from(">" + "".join("i" if f in DRAW_SIGNED else "I" for f in DRAW_FIELDS), body)
            d = dict(zip(DRAW_FIELDS, raw))
            consts = struct.unpack_from(f">{const_bytes // 4}f", body, n * 4)
            vconsts = struct.unpack_from(f">{vertex_bytes // 4}f", body, n * 4 + const_bytes)
            vbo = struct.unpack_from(f">{d['vboFloats']}f", body, n * 4 + const_bytes + vertex_bytes)
            lines.append(f"DRAW {d['index']}: shader {d['id0hi']:08x}{d['id0lo']:08x}:{d['id1hi']:08x}{d['id1lo']:08x} "
                         f"variant {d['variant']} inputs {d['numInputs']} floats {d['numFloats']} tris {d['numTris']}")
            for t in range(2):
                if d[f"used{t}"]:
                    lines.append(f"  tex{t}: id {d[f'texId{t}']:d} {d[f'texW{t}']}x{d[f'texH{t}']} linear "
                                 f"{d[f'linear{t}']} 3point {d[f'threePoint{t}']} address {d[f'addrU{t}']},"
                                 f"{d[f'addrV{t}']}")
            lines.append(f"  depth {d['depthKey']} alpha {d['useAlpha']} decal {d['decal']} fb {d['fb']} viewport "
                         f"{d['vp0']},{d['vp1']} {d['vp2']}x{d['vp3']} scissor {d['sc0']},{d['sc1']} "
                         f"{d['sc2']}x{d['sc3']} 2cyc {d['twoCycle']} kill {d['mayKill']}")
            for table, values, stage in ((names, consts, "ps"), (vertex_names, vconsts, "vs")):
                for i, name in enumerate(table):
                    v = values[i * 4:i * 4 + 4]
                    if any(v) or name in ALWAYS:
                        lines.append(f"  {stage} {name:14s} " + " ".join(f"{x:8.3f}" for x in v))
            nf = d["numFloats"]
            for vtx in range(min(6, len(vbo) // max(nf, 1))):
                lines.append("  v%d: " % vtx + " ".join(f"{x:.4f}" for x in vbo[vtx * nf:(vtx + 1) * nf]))
        elif kind == 3:
            tid, w, h, k = struct.unpack(">IIII", body[:16])
            px = body[16:16 + w * h * 4]
            if k == 0:
                img = Image.frombytes("RGBA", (w, h), px)
                name = f"tex_{tid}.png"
            else:
                argb = Image.frombytes("RGBA", (w, h), px)
                a, r, g, b = argb.split()
                img = Image.merge("RGB", (r, g, b))
                name = "screen.png"
            img.save(os.path.join(out, name))
            lines.append(f"texture {tid} {w}x{h} kind {k} -> {name}")
    open(os.path.join(out, "draws.txt"), "w").write("\n".join(lines) + "\n")
    print(f"{len(lines)} lines into {out}/draws.txt")


if __name__ == "__main__":
    main()
