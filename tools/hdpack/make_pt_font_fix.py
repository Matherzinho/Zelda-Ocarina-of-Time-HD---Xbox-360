#!/usr/bin/env python3
"""make_pt_font_fix: high-resolution versions of the Portuguese letters and pictures that the HD texture packs cover with
other ones, as a patch archive for game:\\mods that loads after them.

    make_pt_font_fix.py --interface "A2 Interface 4x.o2r" --pt "C1 PT-BR Interface 4x.o2r" --ptbr ptbr.o2r OUT.o2r

ptbr.o2r (tools/ptbr, from the player's translated ROM) puts the Portuguese letters in the NTSC font's accented
slots, redrawn, under the plain paths; with alternate assets on, a texture pack's alt/ version of a slot wins over it.
EduardoA's Portuguese pack (C) has HD letters for most of those slots, but not all, and one in another slot:
    slot   ptbr.o2r  C       3DS Experience (A)
    0x81   Á         -       Î        -> Á: C's own Á (its slot 0x8B)
    0x8B   Õ         Á       ö        -> Õ: A's O with C's tilde (from its Ã)
    0x8D   Ü         -       û        -> Ü: A's U with A's diaeresis (from its Ä)
    0x8E   Ú         -       ü        -> Ú: A's U with C's acute (from its Ó)
    0x9D   ü         -       û        -> ü: A's ü (its slot 0x9E)
so with the packs a Portuguese text showed Î for Á, Á for Õ, û for Ü and ü, ü for Ú. The glyphs here are the packs'
own (at 4x, 64x64, white with the coverage in alpha, as the packs draw them), put together where no pack has one.
Pictures ptbr.o2r translates that no Portuguese pack has in HD (the file select's "Are you sure?") are its own,
scaled up 4x (Lanczos, on premultiplied colour), in place of the English ones.

Everything here comes from the packs and the player's own ROM: the output stays on the player's own machine and
console, never in Git or any release.
"""
import argparse
import struct
import zipfile

from PIL import Image

FONT = "alt/textures/nes_font_static/gMsgChar{}Tex"
SLOT = {
    0x41: "41LatinCapitalLetterA", 0x4F: "4FLatinCapitalLetterO", 0x55: "55LatinCapitalLetterU",
    0x81: "81LatinCapitalLetterIWithCircumflex", 0x83: "83LatinCapitalLetterAWithDiaeresis",
    0x8B: "8BLatinCapitalLetterOWithDiaeresis", 0x8C: "8CLatinCapitalLetterUWithGrave",
    0x8D: "8DLatinCapitalLetterUWithCircumflex", 0x8E: "8ELatinCapitalLetterUWithDiaeresis",
    0x9D: "9DLatinSmallLetterUWithCircumflex", 0x9E: "9ELatinSmallLetterUWithDiaeresis",
}
ACCENT_ROWS = 10  # at 4x the packs' capitals start at row 10 or 11, their accents end by row 9


def glyph(archive, slot):
    data = archive.read(FONT.format(SLOT[slot]))
    tex_type, w, h, flags, hs, vs, size = struct.unpack_from("<IIIIffI", data, 0x40)
    return data, Image.frombytes("RGBA", (w, h), data[0x5C:0x5C + size])


def resource(template, img):
    """A texture resource with template's headers and img's pixels (same size)."""
    tex_type, w, h, flags, hs, vs, size = struct.unpack_from("<IIIIffI", template, 0x40)
    assert img.size == (w, h)
    return template[:0x5C] + img.tobytes() + template[0x5C + size:]


def ink_columns(img, rows):
    a = img.getchannel("A")
    xs = [x for x in range(img.width) if any(a.getpixel((x, y)) > 24 for y in rows)]
    return (xs[0], xs[-1]) if xs else None


def with_accent(body, accent_from):
    """body's letter (rows from ACCENT_ROWS down) under accent_from's accent (rows above), centred over the letter."""
    out = Image.new("RGBA", body.size, (0, 0, 0, 0))
    out.paste(body.crop((0, ACCENT_ROWS, body.width, body.height)), (0, ACCENT_ROWS))
    accent = accent_from.crop((0, 0, accent_from.width, ACCENT_ROWS))
    body_x = ink_columns(body, range(ACCENT_ROWS, body.height))
    accent_x = ink_columns(accent_from, range(ACCENT_ROWS))
    shift = round((body_x[0] + body_x[1]) / 2 - (accent_x[0] + accent_x[1]) / 2) if body_x and accent_x else 0
    out.alpha_composite(accent, (shift, 0))
    return out


def n64_to_rgba(data):
    """An N64 texture resource (version 0) as an RGBA image: intensity and intensity-alpha formats."""
    tex_type, w, h, size = struct.unpack_from("<IIII", data, 0x40)
    px = data[0x50:0x50 + size]
    out = bytearray()
    for i in range(w * h):
        if tex_type == 8:  # IA8
            b = px[i]
            v, a = (b >> 4) * 17, (b & 15) * 17
        elif tex_type == 7:  # IA4
            b = (px[i // 2] >> (4 if i % 2 == 0 else 0)) & 15
            v, a = (b >> 1) * 36, (b & 1) * 255
        elif tex_type == 5:  # I4
            b = (px[i // 2] >> (4 if i % 2 == 0 else 0)) & 15
            v = a = b * 17
        elif tex_type == 6:  # I8
            v = a = px[i]
        elif tex_type == 9:  # IA16
            v, a = px[2 * i], px[2 * i + 1]
        else:
            raise ValueError(f"texture type {tex_type} not handled")
        out += bytes((min(v, 255), min(v, 255), min(v, 255), min(a, 255)))
    return Image.frombytes("RGBA", (w, h), bytes(out))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--interface", required=True, help="the 3DS Experience's interface at 4x (make_hd_patch.py)")
    ap.add_argument("--pt", required=True, help="EduardoA's Portuguese interface at 4x (make_hd_patch.py)")
    ap.add_argument("--ptbr", required=True, help="ptbr.o2r (tools/ptbr), the game's Portuguese text and pictures")
    args = ap.parse_args()
    a = zipfile.ZipFile(args.interface)
    c = zipfile.ZipFile(args.pt)
    ptbr = zipfile.ZipFile(args.ptbr)
    out = {}

    a81, _ = glyph(a, 0x81)
    _, c_a_acute = glyph(c, 0x8B)
    out[FONT.format(SLOT[0x81])] = resource(a81, c_a_acute)

    a8b, _ = glyph(a, 0x8B)
    _, a_o = glyph(a, 0x4F)
    _, c_a_tilde = glyph(c, 0x83)
    out[FONT.format(SLOT[0x8B])] = resource(a8b, with_accent(a_o, c_a_tilde))

    a8d, _ = glyph(a, 0x8D)
    _, a_u = glyph(a, 0x55)
    _, a_a_diaeresis = glyph(a, 0x83)
    out[FONT.format(SLOT[0x8D])] = resource(a8d, with_accent(a_u, a_a_diaeresis))

    a8e, _ = glyph(a, 0x8E)
    _, c_o_acute = glyph(c, 0x8C)
    out[FONT.format(SLOT[0x8E])] = resource(a8e, with_accent(a_u, c_o_acute))

    a9d, _ = glyph(a, 0x9D)
    _, a_u_diaeresis = glyph(a, 0x9E)
    out[FONT.format(SLOT[0x9D])] = resource(a9d, a_u_diaeresis)

    # ptbr.o2r's pictures that the English interface covers and no Portuguese pack has: its own, 4x
    cn = set(c.namelist())
    for name in ptbr.namelist():
        alt = "alt/" + name
        if not name.startswith("textures/") or "nes_font_static" in name or alt in cn or alt not in a.namelist():
            continue
        if name.endswith(("GERTex", "FRATex")):
            continue
        template = a.read(alt)
        tex_type, w, h, flags, hs, vs, size = struct.unpack_from("<IIIIffI", template, 0x40)
        img = n64_to_rgba(ptbr.read(name))
        big = img.convert("RGBa").resize((w, h), Image.LANCZOS).convert("RGBA")
        out[alt] = resource(template, big)

    with zipfile.ZipFile(args.out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for name in sorted(out):
            z.writestr(name, out[name])
    print(f"{args.out}: {len(out)} files: " + ", ".join(n.split("/")[-1] for n in sorted(out)))


if __name__ == "__main__":
    main()
