#!/usr/bin/env python3
"""make_ptbr_o2r: builds ptbr.o2r, the optional Brazilian Portuguese text for oot360, from the player's own ROM.

    make_ptbr_o2r.py ROM OUT.o2r

ROM is the player's Ocarina of Time USA 1.0 already patched with the PT-BR v1.8 translation (joao13traducoes /
Patcher64+, the official BPS). The archive holds what Ship of Harkinian reads in place of oot.o2r's files:

  override/text/nes_message_data_static/ptbr             every dialogue, sign and item text, in Portuguese; Ship
                                                          of Harkinian replaces oot.o2r's messages of the same ids
                                                          with these (z_message_OTR.cpp, OTRMessage_LoadCustom), so
                                                          PAL-only ones such as 0xFFFC (the file select's ordered
                                                          font, which the game reads without a null check) stay
  textures/nes_font_static/gMsgChar..Tex                  the 14 glyphs the translation redrew for its accents
                                                          (0x93 is a-tilde, 0x94 c-cedilla, 0x97 e-circumflex...)

Copy it next to soh.xex; Settings > Languages turns it on and off (from the next start). The translation's text and
glyphs are its authors' work and the player's ROM data: the output stays on the player's machine, outside Git (the
repository's .gitignore and pre-commit hook refuse .o2r files), and this tool never writes inside the repository.
"""
import hashlib
import os
import struct
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "romtool"))
import romtool  # noqa: E402

PTBR_SHA1 = "db757847a2a506d9012c104c7ac2b10c87026cb5"
# dmadata indexes in USA 1.0 (the translation keeps the file table's order).
FILE_FONT = 21
FILE_MESSAGES = 22
FILE_CODE = 27
GLYPH_BYTES = 16 * 16 // 2  # I4 16x16
FIRST_GLYPH = 0x20
# Glyph names in Ship of Harkinian's archive (soh/assets/xml/.../nes_font_static.xml) for the ones the translation
# redrew; the rest are the same as English.
REDRAWN = {
    0x81: "gMsgChar81LatinCapitalLetterIWithCircumflexTex",
    0x83: "gMsgChar83LatinCapitalLetterAWithDiaeresisTex",
    0x89: "gMsgChar89LatinCapitalLetterIWithDiaeresisTex",
    0x8B: "gMsgChar8BLatinCapitalLetterOWithDiaeresisTex",
    0x8C: "gMsgChar8CLatinCapitalLetterUWithGraveTex",
    0x8D: "gMsgChar8DLatinCapitalLetterUWithCircumflexTex",
    0x8E: "gMsgChar8ELatinCapitalLetterUWithDiaeresisTex",
    0x8F: "gMsgChar8FLatinSmallLetterSharpSTex",
    0x93: "gMsgChar93LatinSmallLetterAWithDiaeresisTex",
    0x99: "gMsgChar99LatinSmallLetterIWithDiaeresisTex",
    0x9B: "gMsgChar9BLatinSmallLetterOWithDiaeresisTex",
    0x9C: "gMsgChar9CLatinSmallLetterUWithGraveTex",
    0x9D: "gMsgChar9DLatinSmallLetterUWithCircumflexTex",
    0x9E: "gMsgChar9ELatinSmallLetterUWithDiaeresisTex",
}


def header(kind: bytes, version: int) -> bytes:
    """Ship of Harkinian's binary resource header: little-endian, type, version, 0xDEADBEEFDEADBEEF, to 0x40."""
    h = bytearray(0x40)
    h[0] = 0  # little-endian
    h[4:8] = kind[::-1]  # stored as a little-endian uint32 of the ASCII tag
    struct.pack_into("<I", h, 8, version)
    struct.pack_into("<Q", h, 12, 0xDEADBEEFDEADBEEF)
    return bytes(h)


def message_table(code: bytes):
    """The NTSC message table in code: 8-byte entries (id, type/position, segment 0x07 offset), 0xFFFF last."""
    for pos in range(0, len(code) - 16, 4):
        if code[pos:pos + 2] == b"\x00\x01" and code[pos + 4:pos + 8] == b"\x07\x00\x00\x00":
            entries = []
            p = pos
            while p + 8 <= len(code):
                tid, type_pos, _, seg = struct.unpack_from(">HBBI", code, p)
                entries.append((tid, type_pos, seg))
                p += 8
                if tid == 0xFFFF:
                    return entries
    raise SystemExit("no message table found in code")


def text_resource(entries, data: bytes) -> bytes:
    out = bytearray(header(b"OTXT", 0))
    messages = []
    for i, (tid, type_pos, seg) in enumerate(entries[:-1]):
        start = seg & 0xFFFFFF
        end = entries[i + 1][2] & 0xFFFFFF if entries[i + 1][2] else len(data)
        msg = data[start:end]
        cut = msg.find(b"\x02")
        if cut >= 0:
            msg = msg[:cut + 1]  # through the end code, without the alignment padding
        messages.append((tid, type_pos >> 4, type_pos & 0xF, msg))
    out += struct.pack("<I", len(messages))
    for tid, box, ypos, msg in messages:
        out += struct.pack("<HBB", tid, box, ypos)
        out += struct.pack("<I", len(msg)) + msg
    return bytes(out), len(messages)


def texture_resource(i4: bytes) -> bytes:
    # Texture v0: type 5 (I4), 16 x 16, then the bytes.
    return header(b"OTEX", 0) + struct.pack("<IIII", 5, 16, 16, len(i4)) + i4


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    rom_path, out_path = sys.argv[1], sys.argv[2]
    if romtool.inside_repo(out_path):
        raise SystemExit("refusing to write game data inside the repository: " + out_path)
    rom, order = romtool.load(rom_path)

    sha1 = hashlib.sha1(rom).hexdigest()
    if sha1 != PTBR_SHA1:
        print(f"warning: {sha1} is not the PT-BR v1.8 USA 1.0 ROM this was made for; going on", file=sys.stderr)
    table = romtool.dmatable(rom)
    code = romtool.file_data(rom, table[FILE_CODE])
    messages = romtool.file_data(rom, table[FILE_MESSAGES])
    font = romtool.file_data(rom, table[FILE_FONT])

    text, count = text_resource(message_table(code), messages)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        # Not in place of the whole table: an NTSC table has no 0xFFFC, and the game crashed at the title (test 10).
        z.writestr("override/text/nes_message_data_static/ptbr", text)
        for glyph, name in REDRAWN.items():
            off = (glyph - FIRST_GLYPH) * GLYPH_BYTES
            z.writestr("textures/nes_font_static/" + name, texture_resource(font[off:off + GLYPH_BYTES]))
    print(f"{out_path}: {count} messages, {len(REDRAWN)} glyphs")


if __name__ == "__main__":
    main()
