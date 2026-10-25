#!/usr/bin/env python3
"""make_xbox_pack: turns Ship of Harkinian texture/model mods (.otr or .o2r) into .o2r archives the Xbox 360 port loads
from game:\\mods, with high-resolution textures scaled down to what the console holds.

    make_xbox_pack.py [--scale 2] [--max-side 256] MODS_DIR OUT_DIR [--only SUBSTRING ...]

Every archive under MODS_DIR (subfolders too) becomes OUT_DIR/<short name>.o2r. Names are short (the Xbox 360's FATX
takes 42 characters) and numbered in the order the archives should apply, as the port loads mods sorted by name and a
later archive wins: Djipi's 3DS Experience first, then Skilar's Art Plus Link, then translations. Left out: the
"Original N64 HUD" option (the port shows Xbox 360 buttons) and 3DE's Link textures, which Art Plus replaces.

What changes, resource by resource:
- a texture loaded as raw RGBA32 (Ship of Harkinian's high-resolution textures, flag 1) whose pixel scale over the
  N64's is above --scale, or whose side is above --max-side, is scaled down by powers of two (box filter, as the
  texture would be mipmapped) until neither holds, and its header's scales follow;
- everything else (display lists and vertices, often as XML, collision, skeletons, original-size textures) is copied
  byte for byte.

The mods' contents are their authors' work: the output stays on the player's own machine and console, never in Git
(the repository's .gitignore and pre-commit hook refuse archives) or any release.
"""
import argparse
import json
import os
import struct
import sys
import time
import zipfile

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mpq  # noqa: E402

TEX_FLAG_LOAD_AS_RAW = 1
SKIP = ("Original N64 HUD", "02 Link's Textures")


def short_name(path):
    """A FATX-safe name that sorts in load order."""
    base = os.path.splitext(os.path.basename(path))[0]
    keep = "".join(c if c.isalnum() or c in " -_." else "" for c in base)
    if base.startswith("Djipi's 3DE - "):
        rest = keep[len("Djipis 3DE - "):]
        name = "A " + rest
    elif base.startswith("Art Plus - "):
        name = "B " + keep[len("Art Plus - "):]
    elif "pt_br" in base.lower() or "pt-br" in base.lower():
        name = "C PT-BR " + keep
    else:
        name = "D " + keep
    name = name.replace("(OPTIONAL)", "").replace("OPTIONAL", "").replace("  ", " ").strip()
    return name[:38].rstrip(" .") + ".o2r"


class Source:
    """The files of an .otr or .o2r, by name in a fixed order, read one at a time."""

    def __init__(self, path):
        if path.lower().endswith(".otr"):
            self.mpq = mpq.Mpq(path)
            self.zip = None
            self.names = sorted(n for n in self.mpq.names() if not n.startswith("("))
        else:
            self.mpq = None
            self.zip = zipfile.ZipFile(path)
            self.names = sorted(i.filename for i in self.zip.infolist() if not i.is_dir())

    def read(self, name):
        try:
            return self.mpq.read(name) if self.mpq else self.zip.read(name)
        except KeyError:
            return None


def shrink_texture(data, scale_limit, max_side, stats):
    """The texture resource with its raw RGBA32 pixels halved until within limits, or None to keep it."""
    if len(data) < 0x58 or data[4:8] != b"XETO":
        return None
    version = struct.unpack_from("<I", data, 8)[0]
    if version < 1:
        return None
    tex_type, width, height, flags, h_scale, v_scale, size = struct.unpack_from("<IIIIffI", data, 0x40)
    if not flags & TEX_FLAG_LOAD_AS_RAW or size != width * height * 4 or len(data) < 0x5C + size:
        return None
    halvings = 0
    w, h, vs, hs = width, height, v_scale, h_scale
    while (vs > scale_limit or max(w, h) > max_side) and w % 2 == 0 and h % 2 == 0 and w >= 2 and h >= 2 and vs > 1.0:
        w, h, vs, hs = w // 2, h // 2, vs / 2, hs / 2
        halvings += 1
    if not halvings:
        return None
    pixels = data[0x5C:0x5C + size]
    img = Image.frombytes("RGBA", (width, height), pixels)
    # Box filter on premultiplied colour, so transparent texels' colour doesn't bleed into edges.
    small = img.convert("RGBa").resize((w, h), Image.BOX).convert("RGBA")
    out = bytearray(data[:0x40])
    out += struct.pack("<IIIIffI", tex_type, w, h, flags, hs, vs, w * h * 4)
    out += small.tobytes()
    out += data[0x5C + size:]
    stats["shrunk"] += 1
    stats["saved"] += size - w * h * 4
    return bytes(out)


def convert(src, dst, scale_limit, max_side, deadline):
    """Converts src into dst, resuming where a run before stopped; False if the deadline came first. Deletes nothing
    (a connected folder may not allow it): the partial archive gets a name of its own, renamed to dst when whole."""
    state_path = dst + ".state"
    state = None
    if os.path.exists(state_path):
        with open(state_path) as f:
            state = json.load(f)
        if not os.path.exists(state.get("tmp", "")):
            state = None
    if state is None:
        n = 0
        while os.path.exists(f"{dst}.part{n}"):
            n += 1
        state = {"tmp": f"{dst}.part{n}", "done": 0, "files": 0, "shrunk": 0, "saved": 0, "bytes": 0}
    tmp = state["tmp"]
    source = Source(src)
    finished = True
    with zipfile.ZipFile(tmp, "a" if state["done"] else "w", zipfile.ZIP_DEFLATED, compresslevel=6) as out:
        for i in range(state["done"], len(source.names)):
            if time.time() > deadline:
                finished = False
                break
            name = source.names[i]
            data = source.read(name)
            if data is not None:
                new = shrink_texture(data, scale_limit, max_side, state)
                if new is not None:
                    data = new
                out.writestr(name, data)
                state["files"] += 1
                state["bytes"] += len(data)
            state["done"] = i + 1
    if finished:
        os.replace(tmp, dst)
    with open(state_path, "w") as f:
        json.dump(state, f)
    return finished, state, len(source.names)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mods_dir")
    ap.add_argument("out_dir")
    ap.add_argument("--scale", type=float, default=2.0, help="highest pixel scale over the N64's texture (default 2)")
    ap.add_argument("--max-side", type=int, default=256, help="longest side a texture keeps (default 256)")
    ap.add_argument("--only", nargs="*", default=[], help="convert only archives whose name holds one of these")
    ap.add_argument("--budget", type=float, default=0, help="stop after this many seconds, to resume on the next run")
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    sources = []
    for root, _, files in os.walk(args.mods_dir):
        for f in files:
            if f.lower().endswith((".otr", ".o2r")) and f != "soh.o2r" and not any(s in f for s in SKIP):
                sources.append(os.path.join(root, f))
    sources.sort()
    if args.only:
        sources = [s for s in sources if any(o in s for o in args.only)]
    deadline = time.time() + args.budget if args.budget else float("inf")
    for src in sources:
        dst = os.path.join(args.out_dir, short_name(src))
        if os.path.exists(dst):
            continue
        t = time.time()
        finished, st, count = convert(src, dst, args.scale, args.max_side, deadline)
        if not finished:
            print(f"{os.path.basename(dst)}: {st['done']} of {count} files so far; run again to go on", flush=True)
            sys.exit(2)
        print(f"{os.path.basename(dst)}: {st['files']} files, {st['shrunk']} textures scaled down "
              f"({st['saved'] / 1e6:.1f} MB less), {st['bytes'] / 1e6:.1f} MB unpacked, archive "
              f"{os.path.getsize(src) / 1e6:.1f} -> {os.path.getsize(dst) / 1e6:.1f} MB, {time.time() - t:.0f} s",
              flush=True)
    print("all done")


if __name__ == "__main__":
    main()
