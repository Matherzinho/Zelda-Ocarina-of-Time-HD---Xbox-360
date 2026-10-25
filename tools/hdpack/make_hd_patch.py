#!/usr/bin/env python3
"""make_hd_patch: the interface's or Link's textures of Ship of Harkinian texture mods at up to 4x the N64's, as a patch
archive the Xbox 360 port loads from game:\\mods after the console pack make_xbox_pack.py made (everything at 2x).

    make_hd_patch.py --group ui|link [--scale 4] [--max-side N] [--except ARCHIVE...] [--budget SECONDS] \
        OUT.o2r SOURCE...

SOURCE archives (.otr or .o2r) come in the order the game would load them, a later one's file winning. Into the patch
go the group's textures loaded as raw RGBA32 (Ship of Harkinian's high-resolution textures, flag 1) that the console
pack scaled down, that is whose pixel scale over the N64's is above 2, resized to --scale times the N64's size at most
(and to --max-side texels), with their header's scales following. The patch's name sorts after the pack's
("A2 ..." after "A 3DS Experience.o2r"), so the port's alternate assets take these instead.

Why: the console shows the N64's 320x240 at 1280x720, three times over. The interface (hearts, buttons, item icons and
names, the text's font, the pause screens, title cards) and Link are always on screen and close: at 2x they are
magnified and soft, at 4x drawn a little smaller than they are, sharp (zeldaMM's HD pack v2 did the same for
Majora's Mask). The scenes stay at 2x: at 4x a dungeon's textures alone would take 50 to 100 MB of the console's 512
(oot360 tools, measured on the converted pack).

The resize is a box filter on premultiplied colour (transparent texels' colour doesn't bleed into edges) to any size,
not only by halving: EduardoA's Portuguese pack has quest icons and the small key counter at 937x937 texels for 24x24
and 16x16 N64 icons, which halving left whole (odd sides), 3.5 MB each.

Group ui: textures/{parameter,do_action,item_name,map_name,map_grand,map_i,map_48x85,nes_font,message,
message_texture,title,nintendo_rogo}_static, textures/icon_item_*, the place and boss title cards, objects/object_mag
(the title logo) and the pause and file select overlays; German and French versions are left out (the console plays in
English or Portuguese). Group link: objects/object_link_boy and objects/object_link_child.

Left out too: the files of the --except archives, that must win whatever the order the port loads the mods in
(Z Xbox Buttons.o2r's controller glyphs). The port loads game:\mods in the order its mod list keeps, where archives
new to it go last: an archive added after the patches would otherwise come before them.

Resumable in time slices (--budget: the device's shell stops background work) and deletes nothing: the partial archive
has a name of its own, renamed to OUT.o2r when whole. The mods' contents are their authors' work: the output stays on
the player's own machine and console, never in Git (the repository's .gitignore and pre-commit hook refuse archives) or
any release.
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
# libultraship's TextureType -> bytes a texel of the N64's own texture took
BYTES_PER_TEXEL = {1: 4.0, 2: 2.0, 3: 0.5, 4: 1.0, 5: 0.5, 6: 1.0, 7: 0.5, 8: 1.0, 9: 2.0}

UI = (
    "textures/parameter_static/", "textures/do_action_static/", "textures/icon_item_", "textures/item_name_static/",
    "textures/map_name_static/", "textures/map_grand_static/", "textures/map_i_static/", "textures/map_48x85_static/",
    "textures/nes_font_static/", "textures/message_static/", "textures/message_texture_static/",
    "textures/title_static/", "textures/nintendo_rogo_static/", "textures/g_pn_", "textures/place_title_cards/",
    "textures/object_", "objects/object_mag/", "overlays/ovl_kaleido_scope/", "overlays/ovl_file_choose/",
    "overlays/ovl_End_Title/",
)
LINK = ("objects/object_link_boy/", "objects/object_link_child/")
OTHER_LANGUAGES = ("textures/icon_item_ger_static/", "textures/icon_item_fra_static/")


def in_group(plain, group):
    if group == "link":
        return plain.startswith(LINK)
    if plain.startswith(OTHER_LANGUAGES) or plain.endswith(("GERTex", "FRATex", "GER", "FRA")):
        return False
    # the boss title cards live in each boss's object
    return plain.startswith(UI) or (plain.startswith("objects/") and "TitleCard" in plain)


class Source:
    """The files of an .otr or .o2r, read one at a time."""

    def __init__(self, path):
        self.path = path
        if path.lower().endswith(".otr"):
            self.mpq = mpq.Mpq(path)
            self.zip = None
            self.names = [n for n in self.mpq.names() if not n.startswith("(")]
        else:
            self.mpq = None
            self.zip = zipfile.ZipFile(path)
            self.names = [i.filename for i in self.zip.infolist() if not i.is_dir()]

    def read(self, name):
        try:
            return self.mpq.read(name) if self.mpq else self.zip.read(name)
        except KeyError:
            return None


def resized(data, scale_limit, max_side, stats):
    """The texture resource at most scale_limit times the N64's size and max_side texels a side, or None when it's a
    texture the console pack left as it was (not raw RGBA32, or at 2x or less)."""
    if len(data) < 0x5C or data[4:8] != b"XETO":
        return None
    if struct.unpack_from("<I", data, 8)[0] < 1:
        return None
    tex_type, width, height, flags, h_scale, v_scale, size = struct.unpack_from("<IIIIffI", data, 0x40)
    if not flags & TEX_FLAG_LOAD_AS_RAW or size != width * height * 4 or len(data) < 0x5C + size:
        return None
    bpt = BYTES_PER_TEXEL.get(tex_type)
    if bpt is None or h_scale <= 0 or v_scale <= 0:
        return None
    # The header's horizontal scale is in bytes (an RGBA32 texel is 4 of the N64 format's), the vertical in texels.
    px_h = h_scale * bpt / 4.0
    px_v = v_scale
    if max(px_h, px_v) <= 2.01:
        return None
    n64_w, n64_h = width / px_h, height / px_v
    w = max(1, round(n64_w * min(px_h, scale_limit)))
    h = max(1, round(n64_h * min(px_v, scale_limit)))
    if max(w, h) > max_side:
        f = max_side / max(w, h)
        w, h = max(1, round(w * f)), max(1, round(h * f))
    out = bytearray(data[:0x40])
    if (w, h) == (width, height):
        stats["kept"] += 1
        out += data[0x40:]
        return bytes(out)
    img = Image.frombytes("RGBA", (width, height), data[0x5C:0x5C + size])
    small = img.convert("RGBa").resize((w, h), Image.BOX).convert("RGBA")
    out += struct.pack("<IIIIffI", tex_type, w, h, flags, h_scale * w / width, v_scale * h / height, w * h * 4)
    out += small.tobytes()
    out += data[0x5C + size:]
    stats["resized"] += 1
    stats["saved"] += size - w * h * 4
    return bytes(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("sources", nargs="+")
    ap.add_argument("--group", choices=("ui", "link"), required=True)
    ap.add_argument("--scale", type=float, default=4.0)
    ap.add_argument("--max-side", type=int, default=0, help="longest side (default 1024 for ui, 512 for link)")
    ap.add_argument("--except", dest="except_", nargs="*", default=[],
                    help="archives whose files are left out (they must win)")
    ap.add_argument("--budget", type=float, default=0, help="stop after this many seconds, to resume on the next run")
    args = ap.parse_args()
    excluded = set()
    for path in args.except_:
        with zipfile.ZipFile(path) as z:
            excluded.update(i.filename for i in z.infolist() if not i.is_dir())
    max_side = args.max_side or (1024 if args.group == "ui" else 512)
    deadline = time.time() + args.budget if args.budget else float("inf")
    if os.path.exists(args.out):
        print(f"{os.path.basename(args.out)} is already whole")
        return
    state_path = args.out + ".state"
    state = None
    if os.path.exists(state_path):
        with open(state_path) as f:
            state = json.load(f)
        if not os.path.exists(state.get("tmp", "")):
            state = None
    if state is None:
        n = 0
        while os.path.exists(f"{args.out}.part{n}"):
            n += 1
        state = {"tmp": f"{args.out}.part{n}", "done": 0, "files": 0, "resized": 0, "kept": 0, "saved": 0,
                 "bytes": 0}
    sources = [Source(p) for p in args.sources]
    # path -> the source that wins it, in a fixed order
    owner = {}
    for k, src in enumerate(sources):
        for name in src.names:
            plain = name[4:] if name.startswith("alt/") else name
            if in_group(plain, args.group) and name not in excluded:
                owner[name] = k
    items = sorted(owner.items())
    finished = True
    with zipfile.ZipFile(state["tmp"], "a" if state["done"] else "w", zipfile.ZIP_DEFLATED, compresslevel=6) as out:
        for i in range(state["done"], len(items)):
            if time.time() > deadline:
                finished = False
                break
            name, k = items[i]
            data = sources[k].read(name)
            new = resized(data, args.scale, max_side, state) if data is not None else None
            if new is not None:
                out.writestr(name, new)
                state["files"] += 1
                state["bytes"] += len(new)
            state["done"] = i + 1
    if finished:
        os.replace(state["tmp"], args.out)
    with open(state_path, "w") as f:
        json.dump(state, f)
    if not finished:
        print(f"{os.path.basename(args.out)}: {state['done']} of {len(items)} so far; run again to go on", flush=True)
        sys.exit(2)
    print(f"{os.path.basename(args.out)}: {state['files']} textures of {len(items)} {args.group} files "
          f"({state['resized']} resized, {state['kept']} as they were), {state['bytes'] / 1e6:.1f} MB unpacked, "
          f"{os.path.getsize(args.out) / 1e6:.1f} MB", flush=True)


if __name__ == "__main__":
    main()
