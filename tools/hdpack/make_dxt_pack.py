#!/usr/bin/env python3
"""make_dxt_pack: the world's HD textures of the console's 2x pack ("A 3DS Experience.o2r", make_xbox_pack.py) compressed
for the Xbox 360's GPU, as a patch archive the port (test 23 on) loads over it.

    make_dxt_pack.py [--lib dxtenc.so] [--min-side 32] [--budget SECONDS] OUT.o2r PACK.o2r [PACK.o2r...]

Into OUT go the PACKs' raw RGBA32 textures (Ship of Harkinian's high-resolution textures, flag 1) of the scenes and
objects, at the size they are, as DXT1 (every texel opaque) or DXT5 blocks with all their mip levels
(TEX_FLAG_XENOS_DXT1/5, libultraship's Texture.h, dxtenc.c). Left out: the interface and Link (their 4x patches A2
and B1 win anyway), the skies (A1 Skybox Fix has them with their frames filled), palette types and textures smaller
than --min-side on both sides (little to save). The name "A0 ..." sorts after "A 3DS Experience" and before "A1 ...",
so the port's alternate assets take these over the pack's RGBA ones.

Why: a texture in RGBA32 takes 4 bytes a texel in the resource cache and as much again on the GPU; DXT1 takes half a
byte, DXT5 one, so a scene's HD textures take a sixth to a quarter of the memory of the 512 MB console (test 22 closed
soon after starting, and memory is the first suspect), and the GPU fetches less.

Resumable in time slices (--budget: the device's shell stops background work) and deletes nothing: the partial archive
has a name of its own, renamed to OUT.o2r when whole. The mods' contents are their authors' work: the output stays on
the player's own machine and console, never in Git or any release.
"""
import argparse
import ctypes
import json
import os
import struct
import sys
import time
import zipfile

TEX_FLAG_LOAD_AS_RAW = 1
TEX_FLAG_XENOS_DXT1 = 1 << 8
TEX_FLAG_XENOS_DXT5 = 1 << 9
PALETTE_TYPES = (3, 4)

UI = (
    "textures/parameter_static/", "textures/do_action_static/", "textures/icon_item_", "textures/item_name_static/",
    "textures/map_name_static/", "textures/map_grand_static/", "textures/map_i_static/", "textures/map_48x85_static/",
    "textures/nes_font_static/", "textures/message_static/", "textures/message_texture_static/",
    "textures/title_static/", "textures/nintendo_rogo_static/", "textures/g_pn_", "textures/place_title_cards/",
    "textures/object_", "objects/object_mag/", "overlays/ovl_kaleido_scope/", "overlays/ovl_file_choose/",
    "overlays/ovl_End_Title/",
)
LINK = ("objects/object_link_boy/", "objects/object_link_child/")


def is_world(name):
    plain = name[4:] if name.startswith("alt/") else name
    if plain.startswith(LINK) or plain.startswith(UI) or (plain.startswith("objects/") and "TitleCard" in plain):
        return False
    return "Skybox" not in plain


def load_lib(path):
    lib = ctypes.CDLL(path)
    lib.hd_dxt_bound.argtypes = (ctypes.c_int, ctypes.c_int)
    lib.hd_dxt_bound.restype = ctypes.c_size_t
    lib.hd_dxt_encode.argtypes = (ctypes.c_char_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                  ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_int),
                                  ctypes.POINTER(ctypes.c_int))
    lib.hd_dxt_encode.restype = ctypes.c_size_t
    return lib


def converted(lib, data, min_side, stats):
    """The texture resource as DXT blocks, or None to leave it to the pack."""
    if len(data) < 0x5C or data[4:8] != b"XETO" or struct.unpack_from("<I", data, 8)[0] < 1:
        return None
    tex_type, width, height, flags, h_scale, v_scale, size = struct.unpack_from("<IIIIffI", data, 0x40)
    if not flags & TEX_FLAG_LOAD_AS_RAW or flags & (TEX_FLAG_XENOS_DXT1 | TEX_FLAG_XENOS_DXT5):
        return None
    if size != width * height * 4 or len(data) < 0x5C + size or tex_type in PALETTE_TYPES:
        return None
    if width < min_side and height < min_side:
        return None
    cap = lib.hd_dxt_bound(width, height)
    buf = ctypes.create_string_buffer(cap)
    dxt5 = ctypes.c_int(0)
    framed = ctypes.c_int(0)
    n = lib.hd_dxt_encode(bytes(data[0x5C:0x5C + size]), width, height, width, height, 0, buf, cap,
                          ctypes.byref(dxt5), ctypes.byref(framed))
    if n == 0:
        stats["failed"] += 1
        return None
    flags |= TEX_FLAG_XENOS_DXT5 if dxt5.value else TEX_FLAG_XENOS_DXT1
    out = bytearray(data[:0x40])
    out += struct.pack("<IIIIffI", tex_type, width, height, flags, h_scale, v_scale, n)
    out += buf.raw[:n]
    out += data[0x5C + size:]
    stats["dxt5" if dxt5.value else "dxt1"] += 1
    stats["rgba_bytes"] += size
    stats["dxt_bytes"] += n
    return bytes(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("packs", nargs="+")
    ap.add_argument("--lib", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "dxtenc.so"))
    ap.add_argument("--min-side", type=int, default=32)
    ap.add_argument("--budget", type=float, default=0, help="stop after this many seconds, to resume on the next run")
    args = ap.parse_args()
    deadline = time.time() + args.budget if args.budget else float("inf")
    if os.path.exists(args.out):
        print(f"{os.path.basename(args.out)} is already whole")
        return
    lib = load_lib(args.lib)
    state_path = args.out + ".state"
    state = None
    if os.path.exists(state_path):
        with open(state_path) as f:
            state = json.load(f)
        if not os.path.exists(state.get("tmp", "")) and state.get("done", 0):
            state = None
    if state is None:
        n = 0
        while os.path.exists(f"{args.out}.part{n}"):
            n += 1
        state = {"tmp": f"{args.out}.part{n}", "done": 0, "files": 0, "dxt1": 0, "dxt5": 0, "failed": 0,
                 "rgba_bytes": 0, "dxt_bytes": 0}
    packs = [zipfile.ZipFile(p) for p in args.packs]
    owner = {}
    for k, z in enumerate(packs):
        for i in z.infolist():
            if not i.is_dir() and i.file_size >= 0x5C and is_world(i.filename):
                owner[i.filename] = k
    items = sorted(owner.items())
    finished = True
    with zipfile.ZipFile(state["tmp"], "a" if state["done"] else "w", zipfile.ZIP_DEFLATED, compresslevel=6) as out:
        for i in range(state["done"], len(items)):
            if time.time() > deadline:
                finished = False
                break
            name, k = items[i]
            new = converted(lib, packs[k].read(name), args.min_side, state)
            if new is not None:
                out.writestr(name, new)
                state["files"] += 1
            state["done"] = i + 1
    if finished:
        os.replace(state["tmp"], args.out)
    with open(state_path, "w") as f:
        json.dump(state, f)
    if not finished:
        print(f"{os.path.basename(args.out)}: {state['done']} of {len(items)} so far; run again to go on", flush=True)
        sys.exit(2)
    print(f"{os.path.basename(args.out)}: {state['files']} textures ({state['dxt1']} DXT1, {state['dxt5']} DXT5, "
          f"{state['failed']} failed), {state['rgba_bytes'] / 1e6:.1f} MB of RGBA as {state['dxt_bytes'] / 1e6:.1f} MB, "
          f"archive {os.path.getsize(args.out) / 1e6:.1f} MB", flush=True)


if __name__ == "__main__":
    main()
